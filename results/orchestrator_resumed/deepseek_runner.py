import sys,time,pathlib,torch,os
os.chdir('<server-root>'); sys.path.insert(0,'<server-root>/scripts')
import transformers.models.deepseek_v2.modeling_deepseek_v2 as dm
if not hasattr(dm,'DeepseekV2MoE') and hasattr(dm,'DeepseekV2Moe'): dm.DeepseekV2MoE=dm.DeepseekV2Moe
from transformers import AutoModel,AutoTokenizer
class DeepSeekEngine:
 def __init__(self,*,model_id,model_revision,dtype='bfloat16',attn_implementation='sdpa',max_new_tokens=8192,model_class=None,generation_kwargs=None,chat_style='no_template',stop_tokens=None,device='cuda:0',base_repo=None,base_revision=None,processor_repo=None,processor_revision=None,think_end_marker=None): self.model_id=model_id; self.model_revision=model_revision; self.dtype_name='bfloat16'; self.max_new_tokens=max_new_tokens; self.device=device
 def load(self):
  self.tokenizer=AutoTokenizer.from_pretrained(self.model_id,revision=self.model_revision,trust_remote_code=True); self.model=AutoModel.from_pretrained(self.model_id,revision=self.model_revision,trust_remote_code=True,use_safetensors=True,_attn_implementation='sdpa',torch_dtype=torch.bfloat16,device_map='cuda:0'); self.model.eval()
 def transcribe(self,image_path,prompt,timeout_seconds):
  torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats(); outdir=pathlib.Path('<server-root>/outputs/diagnostics/deepseek_smoke'); outdir.mkdir(parents=True,exist_ok=True); result=self.model.infer(self.tokenizer,prompt='<image>\n'+prompt,image_file=str(image_path),output_path=str(outdir),base_size=1024,image_size=768,crop_mode=True,save_results=True); f=outdir/'result.mmd'; raw=f.read_text(encoding='utf8') if f.exists() else (result if isinstance(result,str) else ''); torch.cuda.synchronize(); return {'raw_output':raw.strip(),'dtype':'bfloat16','input_dimensions':{},'gpu_name':torch.cuda.get_device_name(0),'gpu_uuid_if_available':None,'peak_vram_mb':round(torch.cuda.max_memory_allocated()/(1024*1024),1)}
import run_official; run_official.HfVlmEngine=DeepSeekEngine; sys.argv=['run_official.py','--model-id','loay/Arabic-OCR-DeepSeek-OCR-2','--scope','smoke','--chat-style','no_template']; sys.exit(run_official.main())