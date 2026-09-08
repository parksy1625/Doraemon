import os, re, json, math, random, time, gc
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from mini200_v053 import Mini200V053, Mini200V053Config

SEED=int(os.getenv('SEED','20260909'))
STEPS=int(os.getenv('STEPS','100'))
GSM_GEN_N=int(os.getenv('GSM_GEN_N','6'))
GSM_NLL_N=int(os.getenv('GSM_NLL_N','30'))
MMLU_N=int(os.getenv('MMLU_N','30'))
LR=float(os.getenv('LR','0.00025'))
MODEL_ID=os.getenv('MODEL_ID','HuggingFaceTB/SmolLM2-135M-Instruct')
OUT=Path(os.getenv('OUTDIR','mini200_ci_out')); OUT.mkdir(parents=True,exist_ok=True)
random.seed(SEED); torch.manual_seed(SEED); torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))

def p(x): print(x,flush=True)

def keymap(k):
    fixed={'model.embed_tokens.weight':'embed_tokens.weight','model.norm.weight':'norm.weight','lm_head.weight':'lm_head.weight'}
    if k in fixed: return fixed[k]
    if not k.startswith('model.layers.'): return None
    z=k.split('.'); i=z[2]; tail='.'.join(z[3:])
    return {'input_layernorm.weight':f'layers.{i}.n1.weight','post_attention_layernorm.weight':f'layers.{i}.n2.weight','self_attn.q_proj.weight':f'layers.{i}.a.q.weight','self_attn.k_proj.weight':f'layers.{i}.a.k.weight','self_attn.v_proj.weight':f'layers.{i}.a.v.weight','self_attn.o_proj.weight':f'layers.{i}.a.o.weight','mlp.gate_proj.weight':f'layers.{i}.m.g.weight','mlp.up_proj.weight':f'layers.{i}.m.u.weight','mlp.down_proj.weight':f'layers.{i}.m.d.weight'}.get(tail)

def transplant_from_hf(hf,m):
    src=hf.state_dict(); dst=m.state_dict(); copied=0
    with torch.no_grad():
        for sk,sv in src.items():
            dk=keymap(sk)
            if dk and dk in dst:
                if dst[dk].shape!=sv.shape: raise RuntimeError(f'{sk}->{dk}: {sv.shape} != {dst[dk].shape}')
                dst[dk].copy_(sv.to(dst[dk].dtype)); copied+=1
        m.lm_head.weight.copy_(m.embed_tokens.weight)
    return copied

def prompt(tok,q):
    msgs=[{'role':'user','content':f'Solve this problem and give only the final numeric answer.\n\n{q}'}]
    try: return tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True)
    except Exception: return f'Question: {q}\nGive only the final numeric answer.\nAnswer:'

def final_answer(a):
    m=re.search(r'####\s*([^\n]+)',a); s=(m.group(1) if m else a.splitlines()[-1]).strip().replace(',','').replace('$',''); m2=re.search(r'-?\d+(?:\.\d+)?',s); return m2.group(0) if m2 else s

def values(a):
    out=[]
    for v in re.findall(r'<<[^<>]*=([^<>]+)>>',a):
        try: out.append(float(v.strip().replace(',','').replace('$','').replace('%','')))
        except: pass
    return out

def slog(v): return math.copysign(math.log1p(abs(float(v))),float(v))

def anchor(m,ids):
    x=m.embed_tokens(ids)
    for i,b in enumerate(m.layers):
        x=b(x)
        if i+1==m.cfg.insert_after_layer: return x,i+1
    raise RuntimeError

def states(m,a,R):
    s=m.sidecar; seed=s.seed_proj(s.anchor_norm(a[:,-1:])); w=s.slots.expand(a.size(0),-1,-1)+s.cfg.workspace_init_scale*seed; out=[]
    for _ in range(R):
        for b in s.blocks: w=b(w,a)
        out.append(w[:,0])
    return out

def logits(m,a,start,state):
    s=m.sidecar; d=s.read_proj(s.read_norm(state)); h=a.clone(); h[:,-1]=h[:,-1]+torch.tanh(s.read_gate)*d
    for j in range(start,len(m.layers)): h=m.layers[j](h)
    return m.lm_head(m.norm(h[:,-1]))

def last_depths(m,ids,depths):
    with torch.no_grad():
        a,start=anchor(m,ids); ss=states(m,a,max(depths)); return {d:logits(m,a,start,ss[d-1]) for d in depths}

def parity(tok,hf,m):
    rows=[]
    with torch.no_grad():
        for t in ['The capital of France is','2 + 3 =','A train travels 60 miles in']:
            ids=tok(t,return_tensors='pt',add_special_tokens=True).input_ids; x=hf(ids).logits.float(); y=m(ids,1).float(); z=m(ids,8).float()
            rows.append({'text':t,'max_abs':float((x-y).abs().max()),'mean_abs':float((x-y).abs().mean()),'argmax_equal':bool(torch.equal(x.argmax(-1),y.argmax(-1))),'r1_r8_gate0':float((y-z).abs().max())})
    return rows

def gen(m,tok,q,d,max_new=8):
    pr=prompt(tok,q); ids=tok(pr,return_tensors='pt',add_special_tokens=True).input_ids; n=ids.shape[1]; cur=ids
    for _ in range(max_new):
        lg=last_depths(m,cur,(d,))[d]; nxt=lg.argmax(-1,keepdim=True); cur=torch.cat([cur,nxt],1); txt=tok.decode(cur[0,n:],skip_special_tokens=True)
        if '\n' in txt or len(txt)>=20: break
    txt=tok.decode(cur[0,n:],skip_special_tokens=True).strip(); nums=re.findall(r'-?\d+(?:\.\d+)?',txt.replace(',','')); return (nums[-1] if nums else ''),txt

def gsm_nll(m,tok,rows,limit=30,depths=(1,2,4,8)):
    ls={d:[] for d in depths}; hit={d:0 for d in depths}; used=0
    for r in rows[:limit]:
        gold=final_answer(r['answer']); aids=tok(gold,add_special_tokens=False).input_ids
        if not aids: continue
        ids=torch.tensor([tok(prompt(tok,r['question']),add_special_tokens=True).input_ids]); lgs=last_depths(m,ids,depths); target=torch.tensor([aids[0]])
        for d in depths: ls[d].append(float(F.cross_entropy(lgs[d],target))); hit[d]+=int(int(lgs[d].argmax(-1))==aids[0])
        used+=1
    return {'n':used,'nll':{str(d):sum(ls[d])/len(ls[d]) for d in depths},'first_token_acc':{str(d):hit[d]/used for d in depths}}

def gsm_exact(m,tok,rows,limit=6,depths=(1,2,4,8)):
    z={str(d):{'correct':0,'details':[]} for d in depths}
    for i,r in enumerate(rows[:limit]):
        gold=final_answer(r['answer'])
        for d in depths:
            pred,text=gen(m,tok,r['question'],d); z[str(d)]['correct']+=int(pred==gold); z[str(d)]['details'].append({'i':i,'gold':gold,'pred':pred,'text':text})
    for d in depths: z[str(d)]['accuracy']=z[str(d)]['correct']/limit
    return z

def mmlu(m,tok,limit=30,depths=(1,2,4,8)):
    ds=load_dataset('cais/mmlu','management',split='test'); lab=['A','B','C','D']; lids=[]
    for x in lab:
        ids=tok(x,add_special_tokens=False).input_ids
        if len(ids)!=1: ids=tok(' '+x,add_special_tokens=False).input_ids
        lids.append(ids[-1])
    corr={str(d):0 for d in depths}; cnt={str(d):{x:0 for x in lab} for d in depths}; details=[]
    for i,r in enumerate(ds.select(range(min(limit,len(ds))))):
        c=r['choices']; pr=f"Question: {r['question']}\nA. {c[0]}\nB. {c[1]}\nC. {c[2]}\nD. {c[3]}\nAnswer: "; ids=tok(pr,return_tensors='pt',add_special_tokens=True).input_ids; lgs=last_depths(m,ids,depths); gold=int(r['answer']); row={'i':i,'gold':lab[gold],'pred':{}}
        for d in depths:
            pi=int(lgs[d][0,lids].argmax()); pred=lab[pi]; corr[str(d)]+=int(pi==gold); cnt[str(d)][pred]+=1; row['pred'][str(d)]=pred
        details.append(row)
    n=len(details); return {'n':n,'accuracy':{str(d):corr[str(d)]/n for d in depths},'prediction_counts':cnt,'rows':details}

def train(m,tok,rows):
    for q in m.parameters(): q.requires_grad=False
    for q in m.sidecar.parameters(): q.requires_grad=True
    aux=nn.Sequential(nn.LayerNorm(m.cfg.hidden_size),nn.Linear(m.cfg.hidden_size,1)); params=list(m.sidecar.parameters())+list(aux.parameters()); opt=torch.optim.AdamW(params,lr=LR,weight_decay=.01); rng=random.Random(SEED+77); logs=[]; t=time.time(); m.train()
    for step in range(1,STEPS+1):
        r=rows[rng.randrange(len(rows))]; gold=final_answer(r['answer']); aid=tok(gold,add_special_tokens=False).input_ids
        if not aid: continue
        k=rng.randrange(min(len(aid),4)); pre=tok(prompt(tok,r['question']),add_special_tokens=True).input_ids+aid[:k]; pre=pre[-192:]; ids=torch.tensor([pre]); target=torch.tensor([aid[k]])
        with torch.no_grad(): a,start=anchor(m,ids)
        ss=states(m,a,4); vs=values(r['answer']); traj=[vs[min(i,len(vs)-1)] for i in range(4)] if vs else [float(gold) if re.fullmatch(r'-?\d+(?:\.\d+)?',gold) else 0.0]*4
        al=torch.tensor(0.0)
        for i in range(4): al+=F.smooth_l1_loss(aux(ss[i]).squeeze(-1),torch.tensor([slog(traj[i])],dtype=ss[i].dtype))
        al/=4; lm=F.cross_entropy(logits(m,a,start,ss[3]),target); loss=lm+0.15*al; opt.zero_grad(set_to_none=True); loss.backward(); gn=torch.nn.utils.clip_grad_norm_(params,1.0); opt.step()
        if step==1 or step%10==0 or step==STEPS:
            item={'step':step,'loss':float(loss),'lm':float(lm),'aux':float(al),'grad_norm':float(gn),'read_gate':float(m.sidecar.read_gate)}; logs.append(item); p('TRAIN '+json.dumps(item))
    return logs,time.time()-t

def main():
    t=time.time(); p('LOAD '+MODEL_ID); tok=AutoTokenizer.from_pretrained(MODEL_ID); hf=AutoModelForCausalLM.from_pretrained(MODEL_ID,torch_dtype=torch.float32,low_cpu_mem_usage=True).eval(); m=Mini200V053(Mini200V053Config()).float().eval(); copied=transplant_from_hf(hf,m); p(f'COPIED {copied} PARAMS {sum(x.numel() for x in m.parameters())}'); par=parity(tok,hf,m); p('PARITY '+json.dumps(par)); del hf; gc.collect()
    ds=load_dataset('openai/gsm8k','main'); tr=list(ds['train']); te=list(ds['test']); base_nll=gsm_nll(m,tok,te); base_exact=gsm_exact(m,tok,te,depths=(1,)); base_mmlu=mmlu(m,tok,depths=(1,)); p('BASE '+json.dumps({'nll':base_nll,'gsm':{k:v['accuracy'] for k,v in base_exact.items()},'mmlu':base_mmlu['accuracy'],'counts':base_mmlu['prediction_counts']}))
    logs,secs=train(m,tok,tr); m.eval(); post_nll=gsm_nll(m,tok,te); post_exact=gsm_exact(m,tok,te); post_mmlu=mmlu(m,tok); p('POST '+json.dumps({'nll':post_nll,'gsm':{k:v['accuracy'] for k,v in post_exact.items()},'mmlu':post_mmlu['accuracy'],'counts':post_mmlu['prediction_counts']}))
    torch.save({'sidecar_state_dict':{k:v.detach().cpu().half() for k,v in m.sidecar.state_dict().items()},'config':m.cfg.__dict__,'source':MODEL_ID},OUT/'sidecar_fp16.pt')
    res={'version':'Mini-200 V0.5.3 actual SmolLM2 CI','parameters':sum(x.numel() for x in m.parameters()),'parity':par,'training':{'steps':STEPS,'seconds':secs,'log':logs,'objective':'real GSM8K intermediate trajectory at R1..R4, final LM answer only R4; R8 unseen'},'baseline':{'gsm_nll':base_nll,'gsm_exact':base_exact,'mmlu':base_mmlu},'post':{'gsm_nll':post_nll,'gsm_exact':post_exact,'mmlu':post_mmlu},'total_seconds':time.time()-t,'note':'Real benchmark slices, not full leaderboard scores.'}; (OUT/'results.json').write_text(json.dumps(res,indent=2)); p('FINAL '+json.dumps({'gsm':{k:v['accuracy'] for k,v in post_exact.items()},'mmlu':post_mmlu['accuracy'],'nll':post_nll,'seconds':res['total_seconds']}))
if __name__=='__main__': main()
