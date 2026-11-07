"""One synthetic image through real OCR, confirmation, analysis and diagnosis."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import re
import time
from PIL import Image,ImageDraw,ImageFont
from sczx_api.database import Database
from sczx_api.storage import read_media


def verify_live_model(http,base,headers,owner,artifacts):
    stages=[]
    def record(stage,**values):
        stages.append({'stage':stage,**values})
        (artifacts/'live-model-progress.json').write_text(json.dumps(stages,ensure_ascii=False,indent=2)+'\n')
        print('LIVE model stage passed: '+stage,flush=True)
    image=Image.new('RGB',(900,220),'white')
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',38)
    ImageDraw.Draw(image).text((40,70),'Solve: 2x + 3 = 11',font=font,fill='black')
    output=io.BytesIO();image.save(output,format='PNG');original=output.getvalue()
    (artifacts/'live-model-question.png').write_bytes(original)
    uploaded=http.post(base+'/api/v1/questions/ingest',headers=headers,files={'file':('synthetic-equation.png',original,'image/png')},timeout=30)
    assert uploaded.status_code==200,('live image upload status',uploaded.status_code)
    queued=uploaded.json()['data'];qid=queued['question_id'];job_id=queued['job_id']
    assert job_id and queued['status']=='pending'
    deadline=time.monotonic()+240
    while True:
        response=http.get(base+'/api/v1/jobs/'+job_id,headers=headers)
        assert response.status_code==200
        job=response.json()['data']
        if job['status'] in ['completed','failed','cancelled']:break
        if time.monotonic()>deadline:raise TimeoutError('live recognition did not finish within 240 seconds')
        time.sleep(.5)
    assert job['status']=='completed',('live recognition job',job['status'])
    path=base+'/api/v1/questions/'+qid
    detail=http.get(path,headers=headers).json()['data']
    text=detail['question_text'];normalized=re.sub(r'[\s$\\{}]','',text)
    assert '2x+3=11' in normalized,('recognized synthetic equation',text)
    assert detail['status']=='needs_confirmation' and not detail['confirmed']
    assert detail['ocr']['status']=='completed'
    assert detail['student_answer'] in [None,''] and detail['student_steps']==[], 'OCR fabricated student work on a question-only image'
    with Database.from_environment() as db:
        rows=db.query("SELECT path,sha256 FROM question_assets WHERE question_id=? AND kind='uploaded_original'",[qid]).rows
        assert len(rows)==1 and rows[0]['sha256']==hashlib.sha256(original).hexdigest()
        assert read_media(rows[0]['path'])==original
    record('real OCR and original-byte persistence',question_text=text,confidence=detail['ocr']['confidence'],question_id=qid)
    browser_mode=os.environ.get('SCZX_LIVE_MODEL_BROWSER')=='1'
    if browser_mode:
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node',str(root/'scripts/live_model_browser.mjs')],input=json.dumps({'base':base,'token':headers['Authorization'].removeprefix('Bearer '),'question_id':qid,'artifacts':str(artifacts)}),text=True,capture_output=True,timeout=300,cwd=root)
        (artifacts/'live-model-browser.log').write_text(result.stdout+'\n'+result.stderr)
        assert result.returncode==0,'live model browser failed; inspect live-model-browser.log'
        current=http.get(path,headers=headers).json()['data']
        record('real browser confirmation, analysis, diagnosis and refresh',request_mocks=False)
        analysis=current['analysis'];analysis['reference_steps']=[step['text'] for step in current['reference_steps']]
    else:
        confirmed=http.post(path+'/confirm',headers=headers,json={'question_text':text,'subject':'数学','grade':'初一','student_answer':'x=7','student_steps':['2x=14','x=7']})
        assert confirmed.status_code==200,('live confirmation status',confirmed.status_code)
        record('student confirmation')
        analyzed=http.post(path+'/analyze',headers=headers,json={},timeout=240)
        assert analyzed.status_code==200,('live analysis status',analyzed.status_code)
        analysis=analyzed.json()['data']
    assert analysis['verified'] and '4' in analysis['final_answer'] and analysis['reference_steps']
    fallback=analysis['reference_steps']==['方程的实数解为：'+analysis['final_answer']]
    assert not fallback,'analysis used the local fallback; not evidence of live structured analysis'
    record('live structured analysis and SymPy answer verification',final_answer=analysis['final_answer'],reference_steps=analysis['reference_steps'],local_fallback=fallback)
    if browser_mode:
        diagnosis=current['diagnosis']
    else:
        diagnosed=http.post(path+'/diagnose',headers=headers,json={},timeout=240)
        assert diagnosed.status_code==200,('live diagnosis status',diagnosed.status_code)
        diagnosis=diagnosed.json()['data']
    assert diagnosis['first_error_step']==0 and diagnosis['error_type']!='exact'
    assert '14' in diagnosis['first_error_text']
    restored=http.get(path,headers=headers).json()['data']
    assert restored['diagnosis']['id']==diagnosis['id']
    assert restored['analysis']['id']==analysis['id']
    with Database.from_environment() as db:
        assert db.query('SELECT user_id FROM questions WHERE id=?',[qid]).rows[0]['user_id']==owner
        assert len(db.query('SELECT id FROM ocr_runs WHERE question_id=?',[qid]).rows)==1
    record('live diagnosis and persisted detail recovery',first_error_step=diagnosis['first_error_step'],first_error_text=diagnosis['first_error_text'],error_type=diagnosis['error_type'])
    return {'sample':'synthetic 2x+3=11 image; confirmed synthetic incorrect steps 2x=14, x=7','stages':stages,'scope':'one equation; not a broad OCR or diagnostic accuracy evaluation'}
