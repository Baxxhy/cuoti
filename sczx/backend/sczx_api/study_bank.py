import re
import time
from fastapi import HTTPException
from .accounts import current_user
from .database import Database
from .dataset_images import bank_question
from .rows import row_json


def student_grade(db,owner):
    rows=db.query('SELECT grade FROM student_profiles WHERE user_id=?',[owner]).rows;grade=rows[0]['grade'] if rows else ''
    if grade not in ['初一','初二','初三','高一','高二','高三']:raise HTTPException(422,'请先在学习设置中选择具体年级')
    return grade


def later_math(grade):
    college='微积分|不定积分|定积分|微分方程|偏导数|拉普拉斯|傅里叶|泰勒级数|矩阵|行列式|特征值'
    if not grade.startswith('初'):return college
    senior=college+'|复数|虚数|共轭|导数|求导|向量|数列|对数|指数函数|椭圆|双曲线|圆锥曲线|排列组合|二项式定理|数学归纳|充分条件|必要条件|奇函数|偶函数|等差|等比|正态分布|随机变量|(^|[^a-zA-Z])(log|ln)([^a-zA-Z]|$)'
    if grade not in ['初一','初二']:return senior
    later=senior+'|二次函数|一元二次|反比例函数|三角函数|正弦|余弦|正切|圆周角|圆心角|相似三角形|(^|[^a-zA-Z])(sin|cos|tan)([^a-zA-Z]|$)'
    return later+'|勾股|全等|二次根式|分式|一次函数|因式分解|完全平方|平方差' if grade=='初一' else later


def bank_filter(subject,band,source,search,grade):
    params=[subject,subject,band,band,source,source,search,'%'+search+'%']
    if not grade.startswith('高'):params.extend([grade,{'初一':'七年级','初二':'八年级','初三':'九年级'}.get(grade,grade),later_math(grade)])
    return params


_WHERE=" FROM dataset_questions q WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 AND (?='' OR q.subject=?) AND (?='' OR q.grade_band=?) AND (?='' OR q.dataset_source_id=?) AND (?='' OR q.question_text LIKE ?)"


def scoped_where(grade):
    if grade.startswith('高'):return _WHERE.replace('q WHERE','q USE INDEX (ix_bank_browse) WHERE')+" AND q.grade_band='高中'"
    return _WHERE.replace('q WHERE','q USE INDEX (ix_bank_grade) WHERE')+" AND q.grade IN (?,?) AND (q.subject<>'数学' OR CONCAT(q.question_text,' ',COALESCE(q.options,''),' ',COALESCE(q.knowledge_points,'')) NOT REGEXP ?)"


def integer_parameter(raw,fallback,maximum,message,minimum=1):
    raw=raw or str(fallback)
    if not re.fullmatch(r'[+-]?[0-9]+',raw):raise HTTPException(422,message)
    value=int(raw)
    if not minimum<=value<=maximum:raise HTTPException(422,message)
    return value


async def study_bank(request):
    subject=request.query_params.get('subject','');band=request.query_params.get('grade_band','');source=request.query_params.get('source_id','');search=request.query_params.get('search','')
    if any(len(v.encode())>100 for v in [subject,band,source]) or len(search.encode())>300:raise HTTPException(422,'筛选条件过长')
    page=integer_parameter(request.query_params.get('page'),1,10000,'页码无效')
    seed=integer_parameter(request.query_params.get('shuffle_seed'),int(time.time())%2147483647,2147483647,'随机顺序参数无效',0)
    with Database.from_environment() as db:
        user=current_user(request,db);grade=student_grade(db,user['id']);filters=bank_filter(subject,band,source,search,grade);where=scoped_where(grade)
        source_names={r['id']:r['name'] for r in db.query('SELECT id,name FROM dataset_sources').rows}
        paging=f' LIMIT 20 OFFSET {(page-1)*20}';random_key=f"CRC32(CONCAT(q.id,':',{seed}))"
        if not subject:
            listing='SELECT q.* FROM dataset_questions q JOIN (SELECT id,subject_rank,random_key FROM (SELECT q.id,ROW_NUMBER() OVER (PARTITION BY q.subject ORDER BY '+random_key+',q.id) AS subject_rank,'+random_key+' AS random_key'+where+') mixed ORDER BY subject_rank,random_key,id'+paging+') selected ON selected.id=q.id ORDER BY selected.subject_rank,selected.random_key,selected.id'
        else:listing='SELECT q.*'+where+(' ORDER BY q.subject,q.id' if grade.startswith('高') else ' ORDER BY q.grade,q.subject,q.id')+paging
        items=[]
        for row in db.query(listing,filters).rows:
            value=row_json('dataset_questions',row);value['source_name']=source_names.get(row['dataset_source_id'],'题库');items.append(bank_question(value))
        facets={};source_counts={};total=0
        for row in db.query('SELECT q.subject,q.grade_band,q.dataset_source_id,COUNT(*) AS total'+where+' GROUP BY q.subject,q.grade_band,q.dataset_source_id',bank_filter('','','','',grade)).rows:
            row_subject,row_band,row_source=row['subject'],row['grade_band'],row['dataset_source_id'];amount=int(row['total']);key=row_subject+'|'+row_band
            item=facets.setdefault(key,{'subject':row_subject,'grade_band':row_band,'count':0});item['count']+=amount;source_counts[row_source]=source_counts.get(row_source,0)+amount
            if (not subject or subject==row_subject) and (not band or band==row_band) and (not source or source==row_source):total+=amount
        if search:total=int(db.query('SELECT COUNT(*) AS total'+where,filters).rows[0]['total'])
        return {'page':page,'page_size':20,'grade':grade,'scope_label':'高中' if grade.startswith('高') else grade,'shuffle_seed':seed,'questions':items,'total':total,'facets':list(facets.values()),'sources':[{'id':key,'name':source_names.get(key,'题库'),'count':amount} for key,amount in source_counts.items()]}
