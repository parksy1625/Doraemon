import os,json,gc,time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from datasets import load_dataset
from mini200_v053 import Mini200V053,Mini200V053Config
from run_experiment_v054 import transplant,load_sidecar,gsm_nll,gsm_exact,train
MODEL=os.getenv('MODEL_ID','HuggingFaceTB/SmolLM2-135M-Instruct'); SIDE=os.getenv('INIT_SIDECAR','prev_artifact/mini200_ci_out/sidecar_fp16.pt'); OUT=Path('mini200_quick_out'); OUT.mkdir(exist_ok=True)
torch.set_num_threads(4); t=time.time(); print('LOAD',MODEL,flush=True)
tok=AutoTokenizer.from_pretrained(MODEL); hf=AutoModelForCausalLM.from_pretrained(MODEL,torch_dtype=torch.float32,low_cpu_mem_usage=True).eval(); m=Mini200V053(Mini200V053Config()).float().eval(); transplant(hf,m); load_sidecar(m,SIDE); del hf; gc.collect()
ds=load_dataset('openai/gsm8k','main'); tr=list(ds['train']); te=list(ds['test']); base=gsm_nll(m,tok,te,40); print('BASE_NLL',json.dumps(base),flush=True)
logs,secs=train(m,tok,tr); m.eval(); post=gsm_nll(m,tok,te,40); exact=gsm_exact(m,tok,te,4,depths=(1,2,4,8)); result={'base_nll':base,'post_nll':post,'exact':exact,'training_seconds':secs,'total_seconds':time.time()-t,'train_log':logs}; (OUT/'quick.json').write_text(json.dumps(result,indent=2)); torch.save({'sidecar_state_dict':{k:v.detach().cpu().half() for k,v in m.sidecar.state_dict().items()}},OUT/'sidecar_quick.pt'); print('FINAL',json.dumps({'nll':post,'exact':{k:v['accuracy'] for k,v in exact.items()},'secs':result['total_seconds']}),flush=True)
