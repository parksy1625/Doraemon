import os,sys,json
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from datasets import load_dataset
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mini200_ci'))
from mini200_v053 import Mini200V053,Mini200V053Config
from run_experiment_v054 import transplant,load_sidecar,last_depths,label_ids,fmt_mcq
MODEL='HuggingFaceTB/SmolLM2-135M-Instruct'; SIDE='../mini200_eval_artifact/mini200_ci_out/sidecar_fp16.pt'; D=(1,2,4,8)
torch.set_num_threads(4); tok=AutoTokenizer.from_pretrained(MODEL); hf=AutoModelForCausalLM.from_pretrained(MODEL,torch_dtype=torch.float32,low_cpu_mem_usage=True).eval(); m=Mini200V053(Mini200V053Config()).float().eval(); transplant(hf,m); load_sidecar(m,SIDE); del hf
te=load_dataset('cais/mmlu','management',split='test').select(range(30)); dev=list(load_dataset('cais/mmlu','management',split='dev'))[:5]; labs=['A','B','C','D']; lids=label_ids(tok)
ctx='The following are multiple choice questions (with answers) about management.\n\n'+''.join(fmt_mcq(x,x['answer']) for x in dev)
dummy={'question':'N/A','choices':['N/A']*4}; did=tok(ctx+fmt_mcq(dummy),return_tensors='pt').input_ids; pri=last_depths(m,did,D)
res={str(d):{'raw_ok':0,'cal_ok':0,'raw_count':{x:0 for x in labs},'cal_count':{x:0 for x in labs}} for d in D}
for r in te:
  ids=tok(ctx+fmt_mcq(r),return_tensors='pt').input_ids; lg=last_depths(m,ids,D); gold=int(r['answer'])
  for d in D:
    raw=lg[d][0,lids].float(); prior=pri[d][0,lids].float(); ri=int(raw.argmax()); ci=int((torch.log_softmax(raw,0)-torch.log_softmax(prior,0)).argmax()); z=res[str(d)]; z['raw_ok']+=ri==gold; z['cal_ok']+=ci==gold; z['raw_count'][labs[ri]]+=1; z['cal_count'][labs[ci]]+=1
for d in D: res[str(d)]['raw_acc']=res[str(d)]['raw_ok']/30; res[str(d)]['cal_acc']=res[str(d)]['cal_ok']/30
print('RESULT',json.dumps(res),flush=True); Path('management_cal.json').write_text(json.dumps(res,indent=2))
