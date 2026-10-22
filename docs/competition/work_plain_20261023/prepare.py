from pathlib import Path
import json,re,shutil,hashlib
from lxml import etree
import cairosvg
B=Path(__file__).resolve().parent
O=B.parent/'deliverables/通俗化重构版'
OLD=B.parent/'deliverables/插图优化版'
(O/'figures').mkdir(exist_ok=True)
shutil.copytree(OLD/'figures/screenshots',O/'figures/screenshots',dirs_exist_ok=True)
# Preserve the existing compositions. Only labels and text colours change.
labels={'研究问题':'学生困难','关键方法':'系统处理','可观察证据':'学习结果','过程缺依据':'错误难定位','答对缺情境':'答对需分辨','训练缺接续':'复习难坚持','首步不等价':'第一步出错','学习证据':'学习材料','提案':'计算结果','来源校验':'核对原题','身份与归属':'账号与权限','校验与事务':'检查与保存','公开接口':'业务接口','(a) 已核验前缀':'(a) 前面步骤正确','诊断资格':'首错判断','前序有效':'前步正确','本步不等价':'本步错误','(b) 前序证据不足':'(b) 前面步骤未确认','首错资格不足':'不能确定首错','保留错误候选':'保留疑似错误','事件准入':'作答检查','状态输出':'估计结果','有效事件':'可采用的作答','来源有效':'原题未变','完整答案曝光':'看过完整答案','不增加掌握证据':'不计独立答对','辅助学习记录':'保留求助记录','过程记录':'保留订正记录','硬约束筛选':'先筛选题目','优先组与排序':'再安排顺序','合格到期题':'可做的到期题','证据不足':'材料需核对','原题与技能':'原题与目标','候选可用':'有合适题','受约束生成':'按原题出题','统一核验':'检查题目','保存后作答':'保存并作答','证据诊断':'分析错因','动作处理':'处理学生回答','受理与读取检查点':'保存请求与进度','校验与事务提交':'检查并保存结果','保存检查点':'保存当前进度','返回后结束本次调用':'等待学生再作答','(a) 学习对象关联':'(a) 题目与记录','(b) 来源版本演化':'(b) 编辑后的处理','来源标识':'题目内容','来源快照':'当时的题目','冻结快照':'任务旧快照','历史保留':'任务历史','当前有效结果':'重新分析结果','冻结来源':'保存原题版本','绑定执行租约':'登记本次执行','版本有效':'任务版本未变','租约有效':'执行凭证有效','来源一致':'原题内容未变','未被取消':'学生未取消','事务提交':'统一保存'}
report=[]
for p in sorted((OLD/'figures').glob('*.svg')):
 if p.stem=='02':continue
 root=etree.fromstring(p.read_bytes());changes=[]
 if p.stem in ('03','08','10'):
  for g in root.xpath('//*[local-name()="g"][*[local-name()="path" and @d="M12 20v2"]]'):g.getparent().remove(g)
 for e in root.xpath('//*[local-name()="text"]'):
  e.set('fill','#000000')
  if e.text in labels:
   changes.append([e.text,labels[e.text]]);e.text=labels[e.text]
 dst=O/'figures'/p.name
 dst.write_bytes(etree.tostring(root,xml_declaration=True,encoding='utf-8'))
 cairosvg.svg2png(url=str(dst),write_to=str(dst.with_suffix('.png')),output_width=3000,output_height=2000)
 report.append({'file':p.name,'changes':changes,'original_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(B/'figure_changes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
keys=['retrieval_learning','techniques','spacing','knowledge_tracing','react','rag','cangjie','pydantic','sympy','langgraph','mysql','uniapp','vue','fastapi','qdrant','bge','anki','photomath','playwright','pytest']
old=(OLD/'错题帮_系统设计文档_插图优化版.md').read_text()
rows=re.findall(r'^\[(\d+)\] (.+)$',old,re.M)
refs={key:re.sub('2026-10-22','2026-10-23',text).replace('et al..','et al.') for key,(_,text) in zip(keys,rows)}
refs['techniques']=refs['techniques'].replace('https://pubmed.ncbi.nlm.nih.gov/26173288/','https://journals.sagepub.com/doi/10.1177/1529100612453266')
refs['policy']='中共中央, 国务院. [教育强国建设规划纲要（2024—2035年）](https://www.moe.gov.cn/jyb_xxgk/moe_1777/moe_1778/202501/t20250119_1176193.html)[EB/OL]. (2025-01-19)[2026-10-23].'
refs['digital']='教育部等九部门. [关于加快推进教育数字化的意见](https://www.moe.gov.cn/srcsite/A01/s7048/202504/t20250416_1187476.html)[EB/OL]. 教办〔2025〕3号, (2025-04-11)[2026-10-23].'
refs['project']='错题帮项目组. [错题帮源码及实施记录](https://github.com/Baxxhy/cuoti/tree/0092d19cdc9956aabe81e51a666a06f76ccddc7f)[CP/OL]. 版本0092d19, README.md与docs/final/IMPLEMENTATION_STATUS.md [2026-10-23].'
(B/'references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2))
print('Prepared',len(report),'existing figures and',len(refs),'reference entries')
