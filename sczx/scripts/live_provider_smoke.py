"""Explicit, bounded live-provider checks using synthetic samples, never student data.

Unlike integration_smoke.py, this command can call configured external services.
Reports contain only selected safe fields, not credentials or upstream exceptions.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'algorithms'))

async def main(args):
    os.chdir(ROOT)
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file,override=False)
    artifacts=ROOT/'.runtime/live-provider'/secrets.token_hex(4)
    artifacts.mkdir(parents=True)
    report={'sample':'synthetic math/Chinese speech only; no student data','checks':[]}
    async def check(name,operation,timeout):
        started=time.monotonic()
        try:
            result=await asyncio.wait_for(operation(),timeout)
            row={'name':name,'success':True,**result}
        except Exception as error:
            row={'name':name,'success':False,'error_type':type(error).__name__}
        row['elapsed_seconds']=round(time.monotonic()-started,3)
        report['checks'].append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        return row
    if args.pool_path:
        from learning_core.providers.api_pool import ApiPoolProvider
        provider=None
        async def probe():
            nonlocal provider
            provider=ApiPoolProvider(args.pool_path)
            if len(provider.entries)>args.max_entries:
                raise ValueError('configured pool exceeds explicit live probe limit')
            state=await provider.probe()
            if state['last_status']!='ok':
                raise RuntimeError('text and vision probe did not both succeed')
            return {key:state[key] for key in ['actual_models','total_entries','text_entries','vision_entries','last_status']}
        try:
            await check('live text and image provider',probe,args.timeout)
        finally:
            if provider is not None:await provider.close()
    if args.voice:
        from learning_core.services.voice import VoiceProvider
        voice=VoiceProvider()
        text='请先写出已知条件，再说明解题思路。'
        audio=artifacts/'synthetic-speech.mp3'
        async def synthesize():
            metadata=await voice.synthesize(text,audio)
            if audio.stat().st_size<100:raise ValueError('empty speech')
            return {'model':metadata['model'],'bytes':audio.stat().st_size,'text':text}
        synthesis=await check('live speech synthesis',synthesize,args.timeout)
        if synthesis['success']:
            async def transcribe():
                result,metadata=await voice.transcribe(audio)
                if not all(word in result for word in ['条件','解题']):raise ValueError('speech roundtrip missing expected words')
                return {'text':result,'metadata':metadata}
            await check('real speech roundtrip transcription',transcribe,args.stt_timeout)
        else:
            # A real decoder/model/VAD check remains useful if the remote TTS is down.
            # It is explicitly NOT evidence for recognition accuracy on spoken Chinese.
            silent=artifacts/'synthetic-silence.wav'
            with wave.open(str(silent),'wb') as output:
                output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(b'\0\0'*16000)
            async def silence():
                result,metadata=await voice.transcribe(silent)
                if result.strip():raise ValueError('silence produced text')
                return {'text':result,'metadata':metadata,'scope':'real model load, WAV decoding and silence handling only; no speech accuracy claim'}
            await check('real speech model silence handling',silence,args.stt_timeout)
    report['success']=bool(report['checks']) and all(row['success'] for row in report['checks'])
    (artifacts/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'success':report['success'],'report':str(artifacts/'report.json')},ensure_ascii=False),flush=True)
    return 0 if report['success'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool-path',type=lambda value:Path(value).resolve())
    parser.add_argument('--env-file',type=lambda value:Path(value).resolve())
    parser.add_argument('--voice',action='store_true')
    parser.add_argument('--timeout',type=float,default=45)
    parser.add_argument('--stt-timeout',type=float,default=120)
    parser.add_argument('--max-entries',type=int,default=1)
    args=parser.parse_args()
    if not args.pool_path and not args.voice:parser.error('choose --pool-path and/or --voice explicitly')
    raise SystemExit(asyncio.run(main(args)))
