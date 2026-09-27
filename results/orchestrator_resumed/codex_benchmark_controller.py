import os,sys,json,time,signal,subprocess,pathlib,fcntl,socket
ROOT=pathlib.Path('<server-root>'); ORCH=ROOT/'outputs/orchestrator'; LOG=ORCH/'logs'; LOG.mkdir(parents=True,exist_ok=True)
LOCK=ORCH/'codex_lock.json'; FD=ORCH/'codex_benchmark.lock'
models=[
 ('AhmedZaky1/DIMI-Arabic-OCR-V2',['--chat-style','raw_text','--base-repo','Qwen/Qwen2.5-VL-7B-Instruct']),
 ('hastyle/olmOCR-arabic-lora-v2',['--chat-style','raw_text','--base-repo','allenai/olmOCR-2-7B-1025','--processor-repo','allenai/olmOCR-2-7B-1025']),
 ('loay/Arabic-OCR-DeepSeek-OCR-2',['--chat-style','no_template','--processor-repo','unsloth/DeepSeek-OCR-2']),
 ('sherif1313/Arabic-GLM-OCR-v2',['--chat-style','raw_text'])]
with open(FD,'w') as f:
 fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 meta={'owner':'CODEX','pid':os.getpid(),'hostname':socket.gethostname(),'acquired_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'models':[m for m,_ in models],'duplicate_launch_protection':True,'scope':'full_462','timing_class':'CONTENDED_NON_CANONICAL'}
 LOCK.write_text(json.dumps(meta,indent=2))
 # refuse duplicate live model workers
 ps=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout
 for m,_ in models:
  if any('run_official.py' in line and m in line for line in ps.splitlines()):
   raise SystemExit(f'DUPLICATE_REFUSED {m}')
 children=[]
 status={'owner_pid':os.getpid(),'started_at':meta['acquired_at'],'models':{m:{'status':'LAUNCHING','pid':None,'log':None} for m,_ in models},'timing_class':'CONTENDED_NON_CANONICAL'}
 (ORCH/'codex_benchmark_status.json').write_text(json.dumps(status,indent=2))
 try:
  for model,flags in models:
   slug=model.replace('/','__').replace('-','_')
   lp=LOG/f'codex_{slug}.log'; lf=open(lp,'a',buffering=1)
   cmd=[str(ROOT/'.venv-gpu/bin/python'),str(ROOT/'scripts/run_official.py'),'--model-id',model,'--scope','full']+flags
   p=subprocess.Popen(cmd,cwd=str(ROOT),stdout=lf,stderr=subprocess.STDOUT,start_new_session=True)
   children.append((model,p,lf)); status['models'][model].update(status='ACTIVE',pid=p.pid,log=str(lp)); (ORCH/'codex_benchmark_status.json').write_text(json.dumps(status,indent=2))
  while children:
   for model,p,lf in list(children):
    rc=p.poll()
    if rc is not None:
     status['models'][model].update(status='COMPLETE' if rc==0 else 'FAILED',returncode=rc,finished_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())); lf.close(); children.remove((model,p,lf)); (ORCH/'codex_benchmark_status.json').write_text(json.dumps(status,indent=2))
   time.sleep(10)
 finally:
  status['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); (ORCH/'codex_benchmark_status.json').write_text(json.dumps(status,indent=2)); LOCK.unlink(missing_ok=True)