import base64
import hashlib
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from .accounts import current_user,read_json,secret
from .algorithm import compute
from .database import Database
from .manual_questions import answer_text
from .papers import owned,paper_question
from .question_detail import query_array
from .rows import row_json
from .security import new_id,media_url
from .storage import read_media,write_media,remove_media


def export_questions(db,paper,include_images):
    result=[]
    for row in db.query('SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id',[paper['id']]).rows:
        question=paper_question(db,row['question_id'],paper['user_id']);question_id=question['id']
        analyses=db.query('SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id]).rows
        diagnoses=db.query('SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question_id]).rows
        analysis=row_json('problem_analyses',analyses[0]) if analyses else {};explanation=''
        if analyses:explanation='\n'.join(r['text'] for r in query_array(db,'reference_steps','SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index',analysis['id']))
        images=[]
        if include_images:
            for figure in db.query("SELECT path FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",[question_id]).rows:
                try:images.append(base64.b64encode(read_media(figure['path'])).decode())
                except HTTPException as error:
                    if error.status_code!=404:raise
        result.append({'question_text':question['question_text'],'answer':analysis.get('final_answer') or '','explanation':explanation,'subject':question['subject'],'score':row_json('paper_items',row)['score'],'formula':'；'.join(map(answer_text,question.get('formulas') or [])),'options':question['options'],'misconception':diagnoses[0]['root_misconception'] if diagnoses else '','figure_images':images})
    return result


async def export_paper(request):
    paper_id=request.path_params['paper_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request,default_empty=True);kind=body.get('kind','question')
        if not isinstance(kind,str) or kind not in ['question','answer','excel']:raise HTTPException(422,'不支持的导出格式')
        with db.transaction():
            paper=owned(db,paper_id,user['id']);questions=export_questions(db,paper,kind!='excel')
            if kind=='answer':
                for index,item in enumerate(questions):
                    if not item['answer'].strip() or not item['explanation'].strip():raise HTTPException(409,f'第{index+1}题缺少答案或解析，请先补齐分析后再导出答案 PDF')
            rendered=await run_in_threadpool(compute,{'operation':'render_paper','paper_title':paper['title'],'paper_kind':kind,'paper_questions':questions})
            data=base64.b64decode(rendered['file_base64'],validate=True)
            if not data or len(data)>64*1024*1024 or hashlib.sha256(data).hexdigest()!=rendered['sha256']:raise HTTPException(503,'导出文件校验失败')
            job_id=new_id();suffix='xlsx' if kind=='excel' else 'pdf';path=f'reports/{paper_id}-{kind}-{job_id}.{suffix}';write_media(path,data)
            try:
                db.query("INSERT INTO export_jobs (id,paper_id,kind,status,path,created_at,updated_at) VALUES (?,?,?,'completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[job_id,paper_id,kind,path])
                result=row_json('export_jobs',db.query('SELECT * FROM export_jobs WHERE id=?',[job_id]).rows[0]);result['url']=media_url('/'+path,secret());return result
            except Exception:
                try:remove_media(path)
                except OSError:pass
                raise


async def download_paper(request):
    try:
        return _download_paper(request)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500,'导出文件暂时不可用') from None


def _download_paper(request):
    paper_id=request.path_params['paper_id'];kind=request.query_params.get('kind') or 'question'
    with Database.from_environment() as db:
        user=current_user(request,db);owned(db,paper_id,user['id'])
        jobs=db.query('SELECT * FROM export_jobs WHERE paper_id=? AND kind=? ORDER BY created_at DESC,id DESC LIMIT 1',[paper_id,kind]).rows
        if not jobs:raise HTTPException(404,'请先生成导出文件')
        data=read_media(jobs[0]['path']);suffix='xlsx' if kind=='excel' else 'pdf'
        return Response(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if kind=='excel' else 'application/pdf',headers={'Content-Disposition':f'attachment; filename="{paper_id}-{kind}.{suffix}"'})
