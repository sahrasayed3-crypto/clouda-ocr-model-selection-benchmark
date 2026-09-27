import sys,os
os.chdir('<server-root>'); sys.path.insert(0,'<server-root>/scripts')
import run_official
Base=run_official.HfVlmEngine
class GLMEngine(Base):
 def __init__(self,**kw):
  if kw.get('dtype')=='auto': kw['dtype']='bfloat16'
  super().__init__(**kw)
run_official.HfVlmEngine=GLMEngine
sys.argv=['run_official.py','--model-id','sherif1313/Arabic-GLM-OCR-v2','--scope','smoke','--chat-style','raw_text']
sys.exit(run_official.main())