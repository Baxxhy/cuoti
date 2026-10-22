import asyncio,json
from pathlib import Path
import edge_tts
B=Path(__file__).resolve().parent;O=B.parents[2]/'.runtime/competition-video/voices';O.mkdir(parents=True,exist_ok=True)
async def main():
 data=json.loads((B/'narration.json').read_text());sem=asyncio.Semaphore(2)
 async def one(k,v):
  p=O/(k+'.mp3')
  if p.exists() and p.stat().st_size>1000:return
  async with sem:
   for attempt in range(3):
    try:
     await asyncio.wait_for(edge_tts.Communicate(v['text'],'zh-CN-YunxiNeural',rate='+0%').save(str(p)),timeout=80)
     print(k,p.stat().st_size,flush=True);return
    except Exception as e:
     if attempt==2:raise
     await asyncio.sleep(1)
 await asyncio.gather(*(one(k,v) for k,v in data.items()))
asyncio.run(main())
