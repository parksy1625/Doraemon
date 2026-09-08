import os, sys, json, gc
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mini200_ci'))
from mini200_v053 import Mini200V053, Mini200V053Config
from run_experiment_v054 import transplant, load_sidecar, mmlu5
MODEL_ID=os.getenv('MODEL_ID','HuggingFaceTB/SmolLM2-135M-Instruct')
SIDECAR=os.getenv('SIDECAR','../mini200_eval_artifact/mini200_ci_out/sidecar_fp16.pt')
N=int(os.getenv('MMLU_N','100'))
OUT=Path('eval_out'); OUT.mkdir(exist_ok=True)
torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
print('LOAD',MODEL_ID,flush=True)
tok=AutoTokenizer.from_pretrained(MODEL_ID)
hf=AutoModelForCausalLM.from_pretrained(MODEL_ID,torch_dtype=torch.float32,low_cpu_mem_usage=True).eval()
m=Mini200V053(Mini200V053Config()).float().eval(); transplant(hf,m)
base=mmlu5(m,tok,N,depths=(1,)); print('BASE',json.dumps({'raw':base['raw_accuracy'],'cal':base['cal_accuracy'],'raw_counts':base['raw_counts'],'cal_counts':base['cal_counts']}),flush=True)
load_sidecar(m,SIDECAR); m.eval(); post=mmlu5(m,tok,N,depths=(1,2,4,8)); print('POST',json.dumps({'raw':post['raw_accuracy'],'cal':post['cal_accuracy'],'raw_counts':post['raw_counts'],'cal_counts':post['cal_counts']}),flush=True)
res={'n':N,'base':base,'post_v053_500':post,'model':MODEL_ID,'sidecar':SIDECAR}
(OUT/'mmlu_calibrated.json').write_text(json.dumps(res,indent=2))
print('DONE',flush=True)
