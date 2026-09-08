import os, re, json, math, random, time, gc
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from mini200_v053 import Mini200V053, Mini200V053Config

SEED=int(os.getenv('SEED','20260909'))
STEPS=int(os.getenv('STEPS','500'))
GSM_GEN_N=int(os.getenv('GSM_GEN_N','20'))
GSM_NLL_N=int(os.getenv('GSM_NLL_N','80'))
MMLU_N=int(os.getenv('MMLU_N','100'))
LR=float(os.getenv('LR','0.00012'))
MODEL_ID=os.getenv('MODEL_ID','HuggingFaceTB/SmolLM2-135M-Instruct')
INIT_SIDECAR=os.getenv('INIT_SIDECAR','')
OUT=Path(os.getenv('OUTDIR','mini200_ci_out_v054')); OUT.mkdir(parents=True,exist_ok=True)
random.seed(SEED); torch.manual_seed(SEED); torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))

def p(x): print(x,flush=True)

def keymap(k):
    fixed={'model.embed_tokens.weight':'embed_tokens.weight','model.norm.weight':'norm.weight','lm_head.weight':'lm_head.weight'}
    if k in fixed:return fixed[k]
    if not k.startswith('model.layers.'):return None
    z=k.split('.'); i=z[2]; tail='.'.join(z[3:])
    return {'input_layernorm.weight':f'layers.{i}.n1.weight','post_attention_layernorm.weight':f'layers.{i}.n2.weight','self_attn.q_proj.weight':f'layers.{i}.a.q.weight','self_attn.k_proj.weight':f'layers.{i}.a.k.weight','self_attn.v_proj.weight':f'layers.{i}.a.v.weight','self_attn.o_proj.weight':f'layers.{i}.a.o.weight','mlp.gate_proj.weight':f'layers.{i}.m.g.weight','mlp.up_proj.weight':f'layers.{i}.m.u.weight','mlp.down_proj.weight':f'layers.{i}.m.d.weight'}.get(tail)

def transplant(hf,m):
    src=hf.state_dict(); dst=m.state_dict(); n=0
    with torch.no_grad():
        for sk,sv in src.items():
            dk=keymap(sk)
            if dk and dk in dst:
                if dst[dk].shape!=sv.shape: raise RuntimeError(f'{sk}->{dk}: {sv.shape}!={dst[dk].shape}')
                dst[dk].copy_(sv.to(dst[dk].dtype)); n+=1
        m.lm_head.weight.copy_(m.embed_tokens.weight)
    return n

def load_sidecar(m,path):
    if not path or not Path(path).exists(): return False
    ck=torch.load(path,map_location='cpu')
    sd=ck.get('sidecar_state_dict',ck)
    m.sidecar.load_state_dict(sd,strict=True)
    p('RESUMED_SIDECAR '+path+' gate='+str(float(m.sidecar.read_gate.detach())))
    return True

def prompt_final(tok,q):
    msgs=[{'role':'user','content':f'Solve the problem carefully. Show the calculation briefly, then end with exactly #### followed by the final numeric answer.\n\n{q}'}]
    try:return tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True)
    except:return f'Question: {q}\nSolve step by step and end with #### <number>.\nAnswer:\n'

def clean_trace(a):
    return re.sub(r'<<[^<>]*>>','',a).strip()

def final_answer(a):
    m=re.search(r'####\s*([^\n]+)',a); s=(m.group(1) if m else a.splitlines()[-1]).strip().replace(',','').replace('$','')
    m2=re.search(r'-?\d+(?:\.\d+)?',s); return m2.group(0) if m2 else s

def values(a):
    out=[]
    for v in re.findall(r'<<[^<>]*=([^<>]+)>>',a):
        try: out.append(float(v.strip().replace(',','').replace('$','').replace('%','')))
        except: pass
    return out

def slog(v):return math.copysign(math.log1p(abs(float(v))),float(v))

def anchor(m,ids):
    x=m.embed_tokens(ids)
    for i,b in enumerate(m.layers):
        x=b(x)
        if i+1==m.cfg.insert_after_layer:return x,i+1
    raise RuntimeError

def states(m,a,R):
    s=m.sidecar; seed=s.seed_proj(s.anchor_norm(a[:,-1:])); w=s.slots.expand(a.size(0),-1,-1)+s.cfg.workspace_init_scale*seed; out=[]
    for _ in range(R):
        for b in s.blocks:w=b(w,a)
        out.append(w[:,0])
    return out

def logits(m,a,start,state):
    s=m.sidecar; d=s.read_proj(s.read_norm(state)); h=a.clone(); h[:,-1]=h[:,-1]+torch.tanh(s.read_gate)*d
    for j in range(start,len(m.layers)):h=m.layers[j](h)
    return m.lm_head(m.norm(h[:,-1]))

def last_depths(m,ids,depths):
    with torch.no_grad():
        a,start=anchor(m,ids); ss=states(m,a,max(depths)); return {d:logits(m,a,start,ss[d-1]) for d in depths}

def parity(tok,hf,m):
    rows=[]
    with torch.no_grad():
        for t in ['The capital of France is','2 + 3 =','A train travels 60 miles in']:
            ids=tok(t,return_tensors='pt',add_special_tokens=True).input_ids; x=hf(ids).logits.float(); y=m(ids,1).float(); z=m(ids,8).float()
            rows.append({'text':t,'max_abs':float((x-y).abs().max()),'mean_abs':float((x-y).abs().mean()),'argmax_equal':bool(torch.equal(x.argmax(-1),y.argmax(-1))),'r1_r8':float((y-z).abs().max())})
    return rows

def gen(m,tok,q,d,max_new=72):
    pr=prompt_final(tok,q); ids=tok(pr,return_tensors='pt',add_special_tokens=True).input_ids; n=ids.shape[1]; cur=ids
    for _ in range(max_new):
        lg=last_depths(m,cur,(d,))[d]; nxt=lg.argmax(-1,keepdim=True); cur=torch.cat([cur,nxt],1)
        txt=tok.decode(cur[0,n:],skip_special_tokens=True)
        if '####' in txt:
            tail=txt.split('####',1)[1]
            if re.search(r'-?\d+(?:\.\d+)?(?:\s|$)',tail):break
    txt=tok.decode(cur[0,n:],skip_special_tokens=True).strip(); m4=re.search(r'####\s*(-?\d+(?:\.\d+)?)',txt.replace(',',''))
    if m4:return m4.group(1),txt
    nums=re.findall(r'-?\d+(?:\.\d+)?',txt.replace(',','')); return (nums[-1] if nums else ''),txt

def gsm_nll(m,tok,rows,limit,depths=(1,2,4,8)):
    ls={d:[] for d in depths}; hit={d:0 for d in depths}; used=0
    for r in rows[:limit]:
        gold=final_answer(r['answer']); aids=tok(gold,add_special_tokens=False).input_ids
        if not aids:continue
        ids=torch.tensor([tok(prompt_final(tok,r['question']),add_special_tokens=True).input_ids]); lgs=last_depths(m,ids,depths); target=torch.tensor([aids[0]])
        for d in depths:
            ls[d].append(float(F.cross_entropy(lgs[d],target))); hit[d]+=int(int(lgs[d].argmax(-1))==aids[0])
        used+=1
    return {'n':used,'nll':{str(d):sum(ls[d])/len(ls[d]) for d in depths},'first_token_acc':{str(d):hit[d]/used for d in depths}}

def gsm_exact(m,tok,rows,limit,depths=(1,2,4,8)):
    z={str(d):{'correct':0,'details':[]} for d in depths}
    for i,r in enumerate(rows[:limit]):
        gold=final_answer(r['answer'])
        for d in depths:
            pred,text=gen(m,tok,r['question'],d); z[str(d)]['correct']+=int(pred==gold); z[str(d)]['details'].append({'i':i,'gold':gold,'pred':pred,'text':text})
    for d in depths:z[str(d)]['accuracy']=z[str(d)]['correct']/limit
    return z

def fmt_mcq(r,ans=None):
    c=r['choices']; s=f"Question: {r['question']}\nA. {c[0]}\nB. {c[1]}\nC. {c[2]}\nD. {c[3]}\nAnswer:"
    if ans is not None:s+=' '+['A','B','C','D'][int(ans)]+'\n\n'
    return s

def label_ids(tok):
    out=[]
    for x in [' A',' B',' C',' D']:
        q=tok(x,add_special_tokens=False).input_ids
        if len(q)!=1:
            q=tok(x.strip(),add_special_tokens=False).input_ids
        out.append(q[-1])
    return out

def subject_rows(limit):
    # "all" provides a broad MMLU sample and a subject field in current CAIS dataset.
    try:
        test=load_dataset('cais/mmlu','all',split='test'); dev=load_dataset('cais/mmlu','all',split='dev')
        rng=random.Random(SEED+313); idx=list(range(len(test))); rng.shuffle(idx); test=test.select(idx[:min(limit,len(idx))])
        dev_by={}
        for r in dev:dev_by.setdefault(r.get('subject','all'),[]).append(r)
        return list(test),dev_by
    except Exception:
        test=load_dataset('cais/mmlu','management',split='test'); dev=list(load_dataset('cais/mmlu','management',split='dev'))
        return list(test.select(range(min(limit,len(test))))),{'management':dev,'all':dev}

def mmlu5(m,tok,limit,depths=(1,2,4,8)):
    rows,dev_by=subject_rows(limit); labs=['A','B','C','D']; lids=label_ids(tok)
    corr={str(d):0 for d in depths}; ccorr={str(d):0 for d in depths}; cnt={str(d):{x:0 for x in labs} for d in depths}; ccnt={str(d):{x:0 for x in labs} for d in depths}; details=[]
    prior_cache={}
    for i,r in enumerate(rows):
        subj=r.get('subject','management'); demos=dev_by.get(subj,dev_by.get('all',[]))[:5]
        head=f'The following are multiple choice questions (with answers) about {subj.replace("_"," ")}.\n\n'
        ctx=head+''.join(fmt_mcq(x,x['answer']) for x in demos)
        pr=ctx+fmt_mcq(r)
        ids=tok(pr,return_tensors='pt',add_special_tokens=True).input_ids; lgs=last_depths(m,ids,depths); gold=int(r['answer']); row={'i':i,'subject':subj,'gold':labs[gold],'raw':{},'cal':{}}
        if subj not in prior_cache:
            dummy={'question':'N/A','choices':['N/A','N/A','N/A','N/A']}; dids=tok(ctx+fmt_mcq(dummy),return_tensors='pt',add_special_tokens=True).input_ids; prior_cache[subj]=last_depths(m,dids,depths)
        for d in depths:
            raw=lgs[d][0,lids].float(); prior=prior_cache[subj][d][0,lids].float(); pi=int(raw.argmax()); ci=int((F.log_softmax(raw,0)-F.log_softmax(prior,0)).argmax())
            corr[str(d)]+=int(pi==gold); ccorr[str(d)]+=int(ci==gold); cnt[str(d)][labs[pi]]+=1; ccnt[str(d)][labs[ci]]+=1; row['raw'][str(d)]=labs[pi]; row['cal'][str(d)]=labs[ci]
        details.append(row)
    n=len(details); return {'n':n,'raw_accuracy':{str(d):corr[str(d)]/n for d in depths},'cal_accuracy':{str(d):ccorr[str(d)]/n for d in depths},'raw_counts':cnt,'cal_counts':ccnt,'rows':details}

def token_interest(tok,trace_ids):
    # Bias sampled positions toward numbers/final-answer region while retaining normal rationale tokens.
    weights=[]
    for i,t in enumerate(trace_ids):
        s=tok.decode([t]); w=1.0
        if any(ch.isdigit() for ch in s):w=4.0
        if i>=max(0,len(trace_ids)-12):w=max(w,5.0)
        weights.append(w)
    return weights

def train(m,tok,rows):
    for q in m.parameters():q.requires_grad=False
    for q in m.sidecar.parameters():q.requires_grad=True
    aux=nn.Sequential(nn.LayerNorm(m.cfg.hidden_size),nn.Linear(m.cfg.hidden_size,1)); params=list(m.sidecar.parameters())+list(aux.parameters()); opt=torch.optim.AdamW(params,lr=LR,weight_decay=.01); rng=random.Random(SEED+77); logs=[]; t=time.time(); m.train()
    for step in range(1,STEPS+1):
        r=rows[rng.randrange(len(rows))]; trace=clean_trace(r['answer']); tids=tok(trace,add_special_tokens=False).input_ids
        if not tids:continue
        weights=token_interest(tok,tids); k=rng.choices(range(len(tids)),weights=weights,k=1)[0]
        base=tok(prompt_final(tok,r['question']),add_special_tokens=True).input_ids; pre=(base+tids[:k])[-256:]; ids=torch.tensor([pre]); target=torch.tensor([tids[k]])
        with torch.no_grad():a,start=anchor(m,ids)
        ss=states(m,a,4); ces={d:F.cross_entropy(logits(m,a,start,ss[d-1]),target) for d in (1,2,4)}
        lm=.10*ces[1]+.25*ces[2]+.65*ces[4]
        rank=F.relu(ces[2]-ces[1]+0.01)+F.relu(ces[4]-ces[2]+0.01)
        vs=values(r['answer']); gold=final_answer(r['answer']); traj=[vs[min(i,len(vs)-1)] for i in range(4)] if vs else [float(gold) if re.fullmatch(r'-?\d+(?:\.\d+)?',gold) else 0.0]*4
        al=torch.tensor(0.0)
        for i in range(4):al+=F.smooth_l1_loss(aux(ss[i]).squeeze(-1),torch.tensor([slog(traj[i])],dtype=ss[i].dtype))
        al/=4; loss=lm+.10*al+.05*rank; opt.zero_grad(set_to_none=True); loss.backward(); gn=torch.nn.utils.clip_grad_norm_(params,1.0); opt.step()
        if step==1 or step%25==0 or step==STEPS:
            item={'step':step,'loss':float(loss.detach()),'ce1':float(ces[1].detach()),'ce2':float(ces[2].detach()),'ce4':float(ces[4].detach()),'aux':float(al.detach()),'rank':float(rank.detach()),'grad_norm':float(gn),'read_gate':float(m.sidecar.read_gate.detach())}; logs.append(item); p('TRAIN '+json.dumps(item))
    return logs,time.time()-t

def main():
    t=time.time(); p('LOAD '+MODEL_ID); tok=AutoTokenizer.from_pretrained(MODEL_ID); hf=AutoModelForCausalLM.from_pretrained(MODEL_ID,torch_dtype=torch.float32,low_cpu_mem_usage=True).eval(); m=Mini200V053(Mini200V053Config()).float().eval(); copied=transplant(hf,m); par0=parity(tok,hf,m); resumed=load_sidecar(m,INIT_SIDECAR); par=parity(tok,hf,m) if not resumed else par0; p('COPIED '+str(copied)+' PARAMS '+str(sum(x.numel() for x in m.parameters()))); p('PARITY '+json.dumps(par0)); del hf; gc.collect()
    ds=load_dataset('openai/gsm8k','main'); tr=list(ds['train']); te=list(ds['test']);
    base_nll=gsm_nll(m,tok,te,min(40,GSM_NLL_N)); base_exact=gsm_exact(m,tok,te,min(6,GSM_GEN_N),depths=(1,2,4,8)); base_mmlu=mmlu5(m,tok,min(50,MMLU_N)); p('BASE '+json.dumps({'nll':base_nll,'gsm':{k:v['accuracy'] for k,v in base_exact.items()},'mmlu_raw':base_mmlu['raw_accuracy'],'mmlu_cal':base_mmlu['cal_accuracy']}))
    logs,secs=train(m,tok,tr); m.eval(); post_nll=gsm_nll(m,tok,te,GSM_NLL_N); post_exact=gsm_exact(m,tok,te,GSM_GEN_N); post_mmlu=mmlu5(m,tok,MMLU_N); p('POST '+json.dumps({'nll':post_nll,'gsm':{k:v['accuracy'] for k,v in post_exact.items()},'mmlu_raw':post_mmlu['raw_accuracy'],'mmlu_cal':post_mmlu['cal_accuracy'],'raw_counts':post_mmlu['raw_counts'],'cal_counts':post_mmlu['cal_counts']}))
    torch.save({'sidecar_state_dict':{k:v.detach().cpu().half() for k,v in m.sidecar.state_dict().items()},'config':m.cfg.__dict__,'source':MODEL_ID},OUT/'sidecar_v054_fp16.pt')
    res={'version':'Mini-200 V0.5.4 actual SmolLM2 CI','parameters':sum(x.numel() for x in m.parameters()),'initial_parity':par0,'resumed':resumed,'training':{'steps':STEPS,'seconds':secs,'log':logs,'objective':'GSM8K rationale token SFT at R1/R2/R4 + numerical trajectory + depth ranking; R8 unseen'},'baseline':{'gsm_nll':base_nll,'gsm_exact':base_exact,'mmlu5':base_mmlu},'post':{'gsm_nll':post_nll,'gsm_exact':post_exact,'mmlu5':post_mmlu},'total_seconds':time.time()-t,'note':'Real benchmark slices. MMLU reports 5-shot raw and content-free calibrated label scoring; not a full leaderboard score.'}; (OUT/'results_v054.json').write_text(json.dumps(res,indent=2)); p('FINAL '+json.dumps({'gsm':{k:v['accuracy'] for k,v in post_exact.items()},'mmlu_raw':post_mmlu['raw_accuracy'],'mmlu_cal':post_mmlu['cal_accuracy'],'nll':post_nll,'seconds':res['total_seconds']}))
if __name__=='__main__':main()
