import json,subprocess,os,hashlib
from pathlib import Path
import imageio_ffmpeg
out=Path('/tmp/sczx-step20');f=json.loads((out/'private.json').read_text());base=Path(f['base'])/'recordings';dest=Path('docs/demos/20261111_v1');dest.mkdir(parents=True,exist_ok=True);ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();report={'source':'Chrome DevTools Page.startScreencast live JPEG frames','stillsSlideshow':False,'sound':'无音轨；实际网页操作录制','segments':[]}
for name in ['teacher-student','repair-feedback-final','offline-final-0','offline-final-1','offline-formal-final']:
 folder=base/name;frames=json.loads((folder/'frames.json').read_text());assert len(frames)>10;concat=folder/'frames.txt';lines=[]
 for i,frame in enumerate(frames):
  duration=(frames[i+1]['timestamp']-frame['timestamp']) if i+1<len(frames) else .7
  # Real frame timings retained, only clamp identical timestamps to valid codec minimum.
  lines += ["file '"+str(folder/frame['file'])+"'",'duration '+str(max(.04,duration))]
 lines+=["file '"+str(folder/frames[-1]['file'])+"'"];concat.write_text('\n'.join(lines)+'\n');target=dest/(name+'.mp4')
 command=[ffmpeg,'-y','-f','concat','-safe','0','-i',str(concat),'-vf','scale=1440:810:force_original_aspect_ratio=decrease,pad=1440:810:(ow-iw)/2:(oh-ih)/2,format=yuv420p','-vsync','vfr','-c:v','libx264','-preset','fast','-crf','26','-movflags','+faststart',str(target)]
 with (out/(name+'-encode.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=log,check=True)
 verify=subprocess.run([ffmpeg,'-v','error','-i',str(target),'-f','null','-'],capture_output=True,text=True);assert verify.returncode==0,verify.stderr
 report['segments'].append({'file':target.name,'frames':len(frames),'actualSeconds':round(frames[-1]['timestamp']-frames[0]['timestamp'],3),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'fullDecodePassed':True})
concat=base/'clips.txt';concat.write_text('\n'.join("file '"+str((dest/x['file']).resolve())+"'" for x in report['segments'])+'\n');target=dest/'师承智学实际操作演示.mp4';subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(target)],capture_output=True,check=True);subprocess.run([ffmpeg,'-v','error','-i',str(target),'-f','null','-'],capture_output=True,check=True)
report.update(combined=target.name,combinedBytes=target.stat().st_size,combinedSha256=hashlib.sha256(target.read_bytes()).hexdigest(),fullDecodePassed=True);(out/'video-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
