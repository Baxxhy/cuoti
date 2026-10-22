"""Decode both final films, audit subtitles, and extract a frame from every chapter."""
from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,re,hashlib,sys
from compose import R,O,FF,font,dur

D=R/'docs/competition/deliverables/演示视频';Q=O/'quality';Q.mkdir(exist_ok=True)
results=json.loads((D/'视频文件校验.json').read_text()) if (D/'视频文件校验.json').exists() else []
for mode,name in [('landscape','错题帮_完整作品演示_手机实录'),('portrait','错题帮_手机竖屏完整演示')]:
    if len(sys.argv)>1 and mode!=sys.argv[1]:continue
    movie=D/(name+'.mp4');timeline=json.loads((O/f'final-timeline-{mode}.json').read_text())
    info=subprocess.run([FF,'-hide_banner','-i',str(movie)],capture_output=True,text=True).stderr
    (Q/f'{mode}-streams.txt').write_text(info)
    assert 'h264' in info and 'aac' in info
    assert ('1920x1080' if mode=='landscape' else '1080x2400') in info
    assert '48000 Hz' in info and '25 fps' in info
    decode=subprocess.run([FF,'-v','error','-i',str(movie),'-f','null','-'],capture_output=True,text=True)
    (Q/f'{mode}-decode.txt').write_text(decode.stderr)
    assert decode.returncode==0 and not decode.stderr.strip(),decode.stderr
    volume=subprocess.run([FF,'-hide_banner','-i',str(movie),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True)
    (Q/f'{mode}-volume.txt').write_text(volume.stderr)
    peak=re.search(r'max_volume: ([\-\d.]+) dB',volume.stderr)
    mean=re.search(r'mean_volume: ([\-\d.]+) dB',volume.stderr)
    assert peak and -15<float(peak[1])<0
    assert mean and -38<float(mean[1])<-8
    def sec(s):
        h,m,t=s.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(t)
    srt=(D/(name+'.srt')).read_text(encoding='utf-8-sig')
    times=re.findall(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',srt)
    previous=0
    for a,b in times:
        a,b=sec(a),sec(b)
        assert a>=previous-.002 and b>a and b<dur(movie)+.1
        previous=b
    # Every scene is represented in the final mux, including intro and document preview.
    chapters=len(re.findall(r'Chapter #',info));assert chapters==len(timeline),(chapters,len(timeline))
    contacts=[]
    for i,c in enumerate(timeline):
        p=Q/f'{mode}-{i+1:02}-{c["id"]}.png';t=c['film_start']+c['actual_seconds']*.57
        if not p.exists() or p.stat().st_mtime<movie.stat().st_mtime:
            subprocess.run([FF,'-v','error','-y','-ss',str(t),'-i',str(movie),'-frames:v','1',str(p)],check=True)
        im=Image.open(p).convert('RGB');assert im.getextrema()!=( (0,0),(0,0),(0,0) )
        if mode=='landscape':
            im.thumbnail((480,270));tile=Image.new('RGB',(480,305),'white');tile.paste(im,(0,32))
            ImageDraw.Draw(tile).text((7,5),f'{i+1:02} '+c['title'],font=font(16),fill='black');contacts.append(tile)
    if contacts:
        for n in range(0,len(contacts),16):
            sheet=Image.new('RGB',(1920,1220),'#D6DDE8')
            for j,tile in enumerate(contacts[n:n+16]):sheet.paste(tile,((j%4)*480,(j//4)*305))
            sheet.save(Q/f'contact-{n//16+1}.png')
    results=[x for x in results if x['mode']!=mode]
    results.append({'mode':mode,'file':movie.name,'seconds':dur(movie),'bytes':movie.stat().st_size,'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'chapters':chapters,'caption_segments':len(times),'full_decode':'passed','mean_db':float(mean[1]),'peak_db':float(peak[1])})
    print(mode,'passed',flush=True)
(D/'视频文件校验.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
