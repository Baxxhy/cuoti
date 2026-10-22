from pathlib import Path
import json,shutil
B=Path(__file__).resolve().parent; changes=[]
for k in ('product','system'):
 a=B/'revisions/round2';a.mkdir(parents=True,exist_ok=True);shutil.copy2(B/f'{k}.md',a/f'{k}.md')
p=B/'system.md';s=p.read_text()
old=next(x for x in s.split('\n\n') if x.startswith('最终评价从具体行为出发：'))
s=s.replace('\n\n'+old,'');changes.append({'issue':'删除重复结尾','before':old,'after':'删除；相同验证对象已经在8.3、8.4及9.2解释。'})
names={'步骤检查':'check_step','回答判定':'grade_answer','知识检索':'knowledge_search','条件对照':'compare_variant','手写识别':'recognize_handwriting','图解生成':'visualization'}
for name,code in names.items():s=s.replace(f'| {name} {code} |',f'| {name} |')
old='步骤对齐step_alignment比较原步骤与参考步骤的关系，题图检查inspect_figure补充图片中可以确认的条件。二者保留各自引用，不替代学生的原作答。'
new='表5中的步骤检查和回答判定分别对应check_step、grade_answer；知识检索和条件对照对应knowledge_search、compare_variant；手写识别和图解对应recognize_handwriting、visualization。工具标识用于服务之间识别操作，学生页面使用中文名称。\n\n步骤对齐step_alignment比较原步骤与参考步骤的关系，题图检查inspect_figure补充图片中可以确认的条件。二者保留各自引用，不替代学生的原作答。'
assert old in s;s=s.replace(old,new);changes.append({'issue':'工具名称换行','before':'表5中文能力与英文代码同列，长名称截词','after':'表内保留中文，英文标识移到表后完整说明。'})
s=s.replace('/{id}/','/<br>{id}/');changes.append({'issue':'接口路径断行','before':'固定等宽三列表，接口路径随机截词','after':'接口列加宽，长路径在斜线处分行。'})
p.write_text(s)
(B/'round3_changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('第三轮正文及表格修订完成')
