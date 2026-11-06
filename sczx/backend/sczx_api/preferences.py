import json
from fastapi import HTTPException
from .accounts import current_user, read_json, text_field
from .database import Database
from .rows import row_json


def number(obj, key):
    value = obj.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


async def student_preferences(request):
    with Database.from_environment() as db:
        user = current_user(request, db)
        if user['role'] != 'student':
            raise HTTPException(403, '仅学生可以修改本人的学习方向')
        data = await read_json(request) if request.method == 'PATCH' else {}
        with db.transaction():
            rows = db.query('SELECT * FROM student_profiles WHERE user_id=? FOR UPDATE', [user['id']]).rows
            if not rows:
                raise HTTPException(404, '学生档案不存在')
            profile = row_json('student_profiles', rows[0])
            prefs = profile.get('preferences') or {}
            version = number(prefs, 'experience_version')
            if request.method == 'PATCH':
                if any(key not in ['grade', 'subject', 'minutes', 'goal', 'version'] for key in data):
                    raise HTTPException(422, '请求包含不支持的字段')
                if type(data.get('version')) is not int or number(data, 'version') != version:
                    raise HTTPException(409, '学习方向已变化，请重新读取后保存')
                grade = text_field(data, 'grade', 30) if 'grade' in data else profile['grade']
                if 'grade' in data and grade not in ['初一', '初二', '初三', '高一', '高二', '高三']:
                    raise HTTPException(422, '请选择初一至高三的年级')
                subject = text_field(data, 'subject', 30)
                if subject not in ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '道德与法治', '思想政治']:
                    raise HTTPException(422, '请选择支持的学科')
                minutes = number(data, 'minutes')
                if type(data.get('minutes')) is not int or minutes not in [5, 10, 20]:
                    raise HTTPException(422, '请选择5、10或20分钟')
                goal = text_field(data, 'goal', 30)
                if goal not in ['understand', 'practice', 'review']:
                    raise HTTPException(422, '请选择学习目标')
                prefs.update(focus_subject=subject, daily_minutes=minutes, focus_goal=goal, experience_version=version + 1)
                db.query('UPDATE student_profiles SET grade=?,preferences=?,updated_at=UTC_TIMESTAMP(6) WHERE user_id=?', [grade, json.dumps(prefs, ensure_ascii=False), user['id']])
                profile['grade'] = grade
            return {'grade': profile['grade'], 'subject': prefs.get('focus_subject', ''), 'minutes': number(prefs, 'daily_minutes') if number(prefs, 'daily_minutes') > 0 else 10, 'goal': prefs.get('focus_goal') or 'understand', 'version': number(prefs, 'experience_version')}
