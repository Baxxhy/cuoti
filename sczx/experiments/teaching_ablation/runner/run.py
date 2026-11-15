"""Offline, append-only ablation runner. Never imports database or business ModelProvider."""
import argparse,asyncio,csv,hashlib,json,os,signal,subprocess,sys,tempfile,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];sys.path.insert(0,str(REPO/'backend-business'))
from sczx_business.retrieval import retrieve
from sczx_business.experience_policy import diagnose,match_experiences

def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def assets():return sorted([ROOT/'config.json',*list((ROOT/'scenarios').glob('*.json')),*list((ROOT/'prompts').glob('*.txt')),Path(__file__),ROOT/'evaluation/analyze.py',ROOT/'evaluation/RUBRIC.md',ROOT/'evaluation/report.py',ROOT/'runner/test_runner.py',REPO/'backend-business/sczx_business/retrieval.py',REPO/'backend-business/sczx_business/experience_policy.py'])
def integrity():
 manifest=json.loads((ROOT/'freeze.json').read_text())
 for p in assets():
  if manifest['files'].get(str(p.relative_to(REPO)))!=sha(p.read_bytes()):raise ValueError('Frozen input or implementation changed: '+str(p))
 return manifest

def build(s,g,cfg,corpus):
 # No rubric, expected strategy, independent answer, or author labels reach the model.
 data={k:s[k] for k in ('subject','grade','question','original_answer','difficulty','public_knowledge')}
 spec={'query':s['question']+' '+s['difficulty'],'filters':{'subject':s['subject'],'grade':s['grade'],'knowledgeIds':s['knowledge_ids']},'limit':cfg['candidate_budget']}
 candidates=retrieve(spec,corpus['documents'],corpus['knowledge'])['items'];meta={'candidateVersionIds':[d['versionId'] for d in candidates]}
 if g=='B':data['experiences']=candidates
 if g=='C':
  relevant=[h for h in s['history'] if h.get('subject',s['subject'])==s['subject'] and h.get('grade',s['grade'])==s['grade'] and set(h.get('knowledgeIds',s['knowledge_ids']))&set(s['knowledge_ids'])]
  diagnosis=diagnose(s['subject'],s['difficulty'],s['original_answer'],memory=relevant,evidence_id=s['scenario_id'])
  decision=match_experiences(candidates,diagnosis,s['subject'],s['grade'],s['knowledge_ids']);ids={x['versionId'] for x in decision['selected']}
  data.update(experiences=[d for d in candidates if d['versionId'] in ids],difficulty_evidence=diagnosis,learning_memory=relevant,decision=decision);meta['decision']=decision
 if g=='A':meta['candidateVersionIds']=[]
 prompt=(ROOT/'prompts/common.txt').read_text()+(ROOT/f'prompts/{g}.txt').read_text()+'\n输入：'+json.dumps(data,ensure_ascii=False)
 return prompt,data,meta
SCHEMA={'type':'object','additionalProperties':False,'properties':{'difficulty_assessment':{'type':'string'},'strategy':{'type':'string','enum':['hint','example','foundation','rephrase','try']},'hint':{'type':'string'},'steps':{'type':'array','items':{'type':'string'}},'question':{'type':'string'},'citations':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'versionId':{'type':'string'},'supports':{'type':'string'}},'required':['versionId','supports']}}},'required':['difficulty_assessment','strategy','hint','steps','question','citations']}
async def trial(folder,s,g,rep,cfg,corpus,mode):
 key=f"{s['scenario_id']}-{g}-{rep}";dest=folder/'trials'/key
 if dest.exists():return # Incomplete attempts also remain; retry needs a new run directory.
 dest.mkdir(parents=True)
 try:prompt,data,meta=build(s,g,cfg,corpus)
 except Exception as exc:
  write(dest/'result.json',{'status':'failed','error':'input preparation: '+str(exc),'output':None,'latency_seconds':0,'calls':0,'repairs':0,'mode':mode});return
 write(dest/'input.json',{'prompt':prompt,'data':data,'meta':meta,'group':g,'scenario_id':s['scenario_id'],'replicate':rep});start=time.monotonic();status='failed';error=None;output=None;version=None;usage=None
 try:
  if mode=='controlled':
   raw=json.dumps({'difficulty_assessment':'受控工程响应，不用于效果比较','strategy':'hint','hint':'请说明依据。','steps':[],'question':'哪步不确定？','citations':[]},ensure_ascii=False);(dest/'raw.txt').write_text(raw);output=json.loads(raw);status='succeeded'
  else:
   with tempfile.TemporaryDirectory(prefix='sczx-ablation-') as tmp:
    tmp=Path(tmp);sp=tmp/'schema.json';sp.write_text(json.dumps(SCHEMA));op=tmp/'output.json'
    args=['codex','exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(tmp),'-m',cfg['model'],'-c',f'model_reasoning_effort="{cfg["effort"]}"','-c','web_search="disabled"','-c','features.shell_tool=false','-c','features.apps=false','-c','features.plugins=false','-c','features.multi_agent=false','-c','project_doc_max_bytes=0','--color','never','--json','--output-schema',str(sp),'-o',str(op),'-']
    env=dict(os.environ)
    for k in ('CODEX_THREAD_ID','CODEX_SESSION_ID'):env.pop(k,None)
    with (dest/'events.jsonl').open('xb') as events,(dest/'stderr.log').open('xb') as errors:
     proc=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,stdout=events,stderr=errors,env=env,start_new_session=True)
     try:await asyncio.wait_for(proc.communicate(prompt.encode()),cfg['timeout_seconds'])
     except asyncio.TimeoutError:
      os.killpg(proc.pid,signal.SIGKILL);await proc.wait();raise TimeoutError('uniform wall-clock timeout')
    raw=op.read_text() if op.exists() else '';(dest/'raw.txt').write_text(raw)
    if proc.returncode:raise RuntimeError('CLI exited '+str(proc.returncode))
    for line in (dest/'events.jsonl').read_text().splitlines():
     e=json.loads(line);item=e.get('item',{})
     if item.get('type') in ('command_execution','file_change','mcp_tool_call','web_search'):raise RuntimeError('tool action rejected')
     if e.get('usage'):usage=e['usage']
     version=e.get('model',version)
    output=json.loads(raw)
    if any(not isinstance(output.get(k),str) for k in ('difficulty_assessment','strategy','hint','question')) or any(not isinstance(x,str) for x in output.get('steps',[])) or any(not isinstance(x,dict) or set(x)!= {'versionId','supports'} or not all(isinstance(v,str) for v in x.values()) for x in output.get('citations',[])) or set(output)!=set(SCHEMA['required']) or output['strategy'] not in SCHEMA['properties']['strategy']['enum'] or not isinstance(output['steps'],list) or not isinstance(output['citations'],list):raise ValueError('invalid shared schema')
    allowed={x['versionId'] for x in data.get('experiences',[])}
    if any(x.get('versionId') not in allowed for x in output['citations']):raise ValueError('citation outside supplied versions')
    status='succeeded'
 except Exception as exc:error=type(exc).__name__+': '+str(exc)
 write(dest/'result.json',{'status':status,'output':output,'error':error,'latency_seconds':time.monotonic()-start,'model_requested':cfg['model'],'model_returned':version,'effort':cfg['effort'],'repairs':0,'calls':0 if mode=='controlled' else 1,'usage':usage,'cost':None,'mode':mode})
async def main(a):
 manifest=integrity();cfg=json.loads((ROOT/'config.json').read_text());ss=json.loads((ROOT/cfg['dataset']).read_text())['scenarios'];corpus=json.loads((ROOT/cfg['corpus']).read_text())
 if a.mode=='real' and not a.pilot:raise SystemExit('Full real execution is deliberately disabled in this phase')
 chosen=[s for s in ss if not a.pilot or s['scenario_id'] in cfg['pilot_scenarios']];reps=cfg['pilot_replicates'] if a.pilot else cfg['replicates'];folder=ROOT/'results'/a.run
 if not a.run.replace('-','').replace('_','').isalnum():raise ValueError('simple run name required')
 signature={'manifestSha256':sha((ROOT/'freeze.json').read_bytes()),'mode':a.mode,'pilot':a.pilot,'config':cfg,'expectedTrials':len(chosen)*3*reps,'schedule':[f"{s['scenario_id']}-{g}-{r}" for r in range(reps) for s in chosen for g in ['ABC','BCA','CAB'][r]]}
 if folder.exists():
  if json.loads((folder/'run.json').read_text())!=signature:raise ValueError('resume configuration mismatch')
 else:
  folder.mkdir(parents=True);write(folder/'run.json',signature);(folder/'environment.json').write_text(json.dumps({'python':sys.version,'git_parent_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'cli':subprocess.run(['codex','--version'],capture_output=True,text=True).stdout.strip(),'temperature':'unsupported','random_seed':'unsupported'},indent=2))
 # Sequential interleaving avoids cross-trial scheduling and server load confounds.
 for r in range(reps):
  for s in chosen:
   for g in ['ABC','BCA','CAB'][r]:await trial(folder,s,g,r,cfg,corpus,a.mode)
 from importlib.util import spec_from_file_location,module_from_spec
 sp=spec_from_file_location('analyze',ROOT/'evaluation/analyze.py');m=module_from_spec(sp);sp.loader.exec_module(m);m.analyze(folder,ss)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['controlled','real'],default='controlled');p.add_argument('--pilot',action='store_true');p.add_argument('--run',required=True);asyncio.run(main(p.parse_args()))
