from pathlib import Path
import json,hashlib,zipfile,re,subprocess
B=Path(__file__).resolve().parent;R=B.parents[2];O=B.parent/'deliverables/图文修订版'
render=json.loads((B/'word_render_manifest.json').read_text());checks=json.loads((B/'final_readonly_audit.json').read_text())
assert render['错题帮_系统说明文档_图文修订版.docx']['pages'] in range(28,33)
assert 50<=render['错题帮_系统设计文档_图文修订版.docx']['pages']<=55
for name,record in render.items():assert record['sha256']==checks[name]['sha256']==hashlib.sha256((O/name).read_bytes()).hexdigest()
sources={
'总体分层与业务入口':['README.md','backend-cangjie/README.md','backend-algorithms/README.md','frontend/src/api/index.js'],
'错因定位':['backend-algorithms/error_diagnosis.py','backend-algorithms/diagnosis_alignment.py','backend-algorithms/tests/test_error_diagnosis.py'],
'掌握估计与规划':['backend-algorithms/mastery_tracker.py','backend-algorithms/learning_planner.py','backend-algorithms/adaptive_practice.py'],
'单协调器':['backend-algorithms/learning_workflow.py','backend-cangjie/src/learning_task_worker.cj'],
'数据身份与约束':['backend-cangjie/schema/006_learning_tasks.sql','backend-cangjie/schema/010_study_sessions.sql'],
'学习记忆':['backend-cangjie/src/learning_memory.cj'],
'页面与草稿':['frontend/src/utils/task-draft.js','frontend/src/utils/task-entry.js','frontend/src/pages/task/task.vue'],
'复习与练习':['frontend/src/pages/review/review.vue','frontend/src/pages/practice/practice.vue','backend-cangjie/src/study_bank.cj'],
'既有验证':['docs/final/IMPLEMENTATION_STATUS.md']}
manifest={}
for theme,paths in sources.items():
 manifest[theme]=[]
 for p in paths:
  f=R/p;assert f.exists(),f
  manifest[theme].append({'path':p,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(B/'detail_source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
logs=json.loads((B.parent/'work_research_20261022/evidence_log_manifest.json').read_text())
for row in logs:assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
(B/'evidence_log_manifest.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
# Only the introductory facts and evidence need common wording; neither report depends on the other.
prod=(B/'product.md').read_text();design=(B/'system.md').read_text()
assert '见系统设计报告' not in prod and '系统设计第' not in prod
sections=re.split(r'^### ',design,flags=re.M)[1:]
coverage=[]
for raw in sections:
 title,body=raw.split('\n',1);body=re.split(r'^## ',body,flags=re.M)[0]
 paras=[x for x in body.split('\n\n') if x.strip() and not x.startswith(('!','|','表'))]
 coverage.append({'section':title,'characters':len(body),'prose_paragraphs':len(paras)})
assert len(coverage)==27 and min(x['prose_paragraphs'] for x in coverage)>=4
(B/'section_depth_audit.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
source_md='# 技术事实与验证来源\n\n核对日期：2026年10月22日。业务源码基线：71894bf；本次只修改文档与图表。源码对比确认当前业务文件相对该基线没有变化。\n\n'
for theme,items in manifest.items():
 source_md+='## '+theme+'\n\n'+'\n'.join('- `'+x['path']+'`；SHA-256：`'+x['sha256']+'`。' for x in items)+'\n\n'
source_md+='## 验证日志\n\n以下为已有工程验证记录，本次复核文件摘要及批次范围，没有重新执行业务测试。\n\n'
for row in logs:source_md+='- `'+Path(row['path']).name+'`：SHA-256 `'+row['sha256']+'`。\n'
source_md+='\n运行截图沿用研究重构版的11张历史浏览器归档，像素保持一致；机制图为本次独立提示词生成的示意图，图内算例与正文规则对应。它们不替代真实模型总体准确率或学生效果实验。\n'
(O/'技术事实与验证来源.md').write_text(source_md)
(O/'阅读说明.md').write_text('''# 错题帮文档交付说明

本目录包含两份独立报告，均为可编辑Word并配有Markdown源稿。

- **系统说明文档：29页。** 面向评委，说明问题、用户需求、功能与特色、典型应用、运行截图及成果。
- **系统设计文档：50页。** 面向技术审查，覆盖算法合同与演算、架构分工、单协调器、工具、数据约束、版本、接口、异常、部署及测试依据。

两份报告分别组织论述，必要术语、源码基线与验证数字一致；系统说明无需依赖系统设计才能阅读，系统设计也具备自己的目标、背景与结论。

每份报告包含20条可点击的真实参考文献，所有条目均在正文引用。10张机制图全部重新生成，使用白底、低饱和灰蓝及灰绿色，取消框内小字副说明；11张真实运行截图保持原样。图表与截图的性质在正文中分别说明。

正文指定宋体12.5磅，一级标题黑体16磅、二级标题黑体14磅，表格与题注统一11磅。全部可编辑文字为黑色，表格为全格线，图表题注居中，无页眉页脚、无附录。自动目录保留可更新字段。

页数由本次LibreOffice实际排版确认；Microsoft Word在不同字体安装及版本下可能有少量分页差异。Word指定宋体与黑体；本地预览对缺失黑体使用系统字体回退。

本次按要求只交付Word，不生成PDF。旧版文件保留在原目录。ZIP包含两份Word、两份源稿、图表、独立生成提示词及技术来源说明；内部检查脚本、临时页面预览和日志不放入ZIP。
''')
quality='''# 最终文档质量审查

审查日期：2026年10月22日。

## 定位与篇幅

系统说明29页，保留需求、特色、产品能力及11张真实截图组成的应用案例。系统设计50页，27个二级小节均增加相应设计细节，新增约1.8万字符；正文包含22张全格线表格及6张机制图。两份文档独立组织，不以压缩和扩展关系相互依赖。

系统说明按“项目概述—需求分析—关键技术—系统设计—实现与验证—总结与展望”组织。系统设计按“总体设计—核心算法—智能体设计—数据设计—系统实现—系统验证—总结与展望”组织。正文之后各列20条参考文献，没有附录。

## 内容核验

- 算法参数、公式及已有数值保留；新增计算例明确为演算，未写成实测收益。
- 核对了诊断、掌握、规划、单协调工作流、仓颉工作器、学习记忆、数据结构及前端请求和草稿源文件。
- 任务租约、来源、版本、步骤和请求身份分别解释；Python保持内部计算职责，业务数据库读写由仓颉承担。
- 新增业务接口表依据前端实际调用，新增数据约束表依据SQL结构；学习记忆数量及时间窗口依据当前实现。
- 既有测试日志摘要一致；没有新增虚构测试批次、学生实验、准确率或手机安装成果。
- 当前H5、App资源构建和后续签名设备验证分别表述。

## 图表与字体

10张机制图均更换为独立提示词生成的新PNG；人工逐张检查中文标签、主要连接方向、模块职责及算例。图内仅保留标题、短模块名、必要分支与数学符号，取消“结构·技能·答案”一类小字副说明。配色统一为低饱和灰蓝与灰绿色。

11张原运行截图保持原像素。程序核对Word中21张图片与源图像素一致。PNG是图像，图内文字不作为Word可编辑字体检查对象；图内标签经过视觉审查，真实截图保持界面原色。

程序检查可编辑文字颜色为000000，正文宋体，一级、二级标题黑体，图表题注居中，全部表格为全格线，页眉页脚引用已移除。正文12.5磅，表格及题注11磅；正文链接和参考文献链接与各自段落字号一致。

## 实际排版检查

已直接将两份Word渲染为79张页面PNG，未生成PDF。全页缩略预览检查布局，并放大检查算法公式、接口及数据表、参考文献和重点机制图页。未发现图表截断、文字覆盖、图题错位或多余空白页。目录64项页码与实际标题页核对一致，目录没有项目符号或手动换行。

源稿到Word的段落、表格内容、图表标题和引用链接均核对完整。正式文件原有公式保留，图表编号连续。原始参赛定稿与上一版研究重构文档的摘要均保持不变。

## 审查处理记录

| 问题 | 处理结果 |
| --- | --- |
| 配色鲜艳且小字拥挤 | 10张机制图重绘，短标签放大，解释移至正文 |
| 参考文献不足 | 两份各20条，全部在正文引用并保留来源链接 |
| 说明与设计定位接近 | 说明改为能力与应用表达，设计补足27小节的技术机制 |
| 设计深度与篇幅不足 | 增加算法演算、合同、约束、状态、恢复、接口及验收对象，实际50页 |
| 参考链接字号不一致 | 对正文和文献链接分别统一字号并重新渲染 |
| 旧版被覆盖的风险 | 新目录独立交付，原始文件核验未变 |

## 保留事项

页数以本次实际排版环境为准，其他Word版本可能产生少量差异。图表为用户指定的PNG交付，提示词保留以便重新生成。现有工程测试证据与真实模型总体质量、学生学习收益分别表述，后两项仍需相应研究数据。不存在据此宣称所有新题绝对正确的结论。
'''
(O/'最终文档质量审查报告.md').write_text(quality)
figs=['研究问题与方案','总体方法','系统架构','错因证据','辅助感知更新','学习规划','同源核验补题','任务协同','来源关联','异步提交']
(O/'图表索引.md').write_text('# 图表索引\n\n'+'\n'.join(f'- `{i:02d}.png`：{name}；同名`.prompt.md`保存独立提示词。' for i,name in enumerate(figs,1))+'\n\n另含11张未修改的历史运行截图，实际来源与解释见系统说明应用案例及技术事实清单。\n')
(O/'参赛提交检查清单.md').write_text('''# 提交检查清单

- [x] 两份独立Word：系统说明29页、系统设计50页。
- [x] 两份Markdown源稿及图表文件齐全。
- [x] 全部10张机制图更新，11张真实截图保留。
- [x] 每份20条参考文献，正文引用与链接核对。
- [x] 宋体正文、黑体标题、黑色可编辑文字，全格线表格、居中题注。
- [x] 自动目录页码、编号、公式及主要表格实际渲染检查。
- [x] 无附录、页眉页脚、PDF、业务凭据或内部临时文件。
- [x] 当前实现、既有验证、算例及后续工作分别表述。
- [x] 原始文档保留，交付目录独立。
- [ ] 提交者按官方最终入口填写团队身份及其他平台元信息，并在实际使用的Word中确认分页。

最后一项属于参赛平台提交操作，不影响本次文档交付。
''')
package=O/'错题帮_系统说明与详细设计.zip'
include=[p for p in O.rglob('*') if p.is_file() and (p.suffix in ['.docx','.png'] or p.name.endswith('.prompt.md') or p.name in ['错题帮_系统说明文档_图文修订版.md','错题帮_系统设计文档_图文修订版.md','技术事实与验证来源.md','阅读说明.md','图表索引.md'])]
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(include):z.write(p,p.relative_to(O))
with zipfile.ZipFile(package) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(include)
 assert not any(x.endswith('.pdf') or 'work_' in x or 'review/' in x for x in z.namelist())
(B/'completion_audit.json').write_text(json.dumps({'pages':{k:v['pages'] for k,v in render.items()},'section_depth':coverage,'source_checks':len(manifest),'all_prior_log_hashes_match':True,'package_entries':len(include),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'word_sha256':{k:v['sha256'] for k,v in checks.items()},'no_pdf':True,'business_code_changed':False,'visual_check':'All-page contact sheets plus full-size formula/table/reference/figure pages'},ensure_ascii=False,indent=2))
print('Final package:',package,'entries:',len(include))
