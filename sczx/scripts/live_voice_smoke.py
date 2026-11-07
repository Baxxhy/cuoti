"""Live voice HTTP acceptance, enabled explicitly by integration_smoke.py."""
import hashlib
import re
from sczx_api.database import Database
from sczx_api.storage import read_media


def verify_live_voice(http,base,headers,owner,question_id,artifacts):
    text='请先写出已知条件，再说明解题思路。'
    synthesized=http.post(base+'/api/v1/voice/synthesize',headers=headers,json={'text':text,'question_id':question_id},timeout=60)
    assert synthesized.status_code==200,('live speech synthesis status',synthesized.status_code)
    speech=synthesized.json()['data']
    assert speech['kind']=='tts' and speech['status']=='completed' and speech['browser_fallback'] is False
    assert speech['metadata']['model']=='edge-tts'
    audio=http.get(base+speech['audio_url'])
    assert audio.status_code==200 and len(audio.content)>100
    assert audio.headers['content-type'].startswith('audio/')
    chunk=http.get(base+speech['audio_url'],headers={'Range':'bytes=0-63'})
    assert chunk.status_code==206 and chunk.content==audio.content[:64]
    (artifacts/'live-speech.mp3').write_bytes(audio.content)
    transcribed=http.post(base+'/api/v1/voice/transcribe',params={'question_id':question_id},headers=headers,files={'file':('synthetic-speech.mp3',audio.content,'audio/mpeg')},timeout=120)
    assert transcribed.status_code==200,('live speech transcription status',transcribed.status_code)
    result=transcribed.json()['data']
    assert result['kind']=='stt' and result['status']=='completed' and result['editable'] is True
    assert result['metadata']['model']=='faster-whisper-small'
    assert all(word in result['text'] for word in ['条件','解题'])
    assert http.get(base+result['audio_url']).content==audio.content
    with Database.from_environment() as db:
        records=db.query('SELECT id,user_id,question_id,kind,status,audio_path,transcript FROM voice_records WHERE id IN (?,?)',[speech['id'],result['id']]).rows
        assert len(records)==2
        for record in records:
            assert record['user_id']==owner and record['question_id']==question_id and record['status']=='completed'
            assert read_media(record['audio_path'])==audio.content
        assert next(row for row in records if row['kind']=='stt')['transcript']==result['text']
    normalize=lambda value:re.sub(r'[^\w]','',value)
    return {'provider':'live edge-tts and real local faster-whisper; no voice mocks','reference_text':text,'transcript':result['text'],'exact_text_match':normalize(text)==normalize(result['text']),'audio_bytes':len(audio.content),'audio_sha256':hashlib.sha256(audio.content).hexdigest(),'persisted_records':2,'signed_media_and_range':True,'scope':'one synthetic Chinese sentence; not general speech accuracy'}
