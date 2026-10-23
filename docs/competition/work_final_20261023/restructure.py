from pathlib import Path
import re,json,shutil
B=Path(__file__).resolve().parent;P=B.parent/'work_technology_revision_20261023';O=B.parent/'deliverables/参赛终稿';O.mkdir(exist_ok=True);(O/'figures').mkdir(exist_ok=True)
shutil.copytree(P.parent/'deliverables/技术介绍修订版/figures/screenshots',O/'figures/screenshots',dirs_exist_ok=True)
for f in ['build.py','layout.py','audit.py']:
 s=(P/f).read_text().replace('技术介绍修订版','最终版').replace("deliverables/最终版","deliverables/参赛终稿").replace('0092d19','d01d742');(B/f).write_text(s)
refs=json.loads((P/'references.json').read_text());refs['project']=refs['project'].replace('0092d19cdc9956aabe81e51a666a06f76ccddc7f','d01d7428c24180c9b767aa88e26c7dd732ee90b3').replace('0092d19','d01d742');(B/'references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2))
(B/'originals.json').write_text((B/'inputs.json').read_text())
def sections(s):
 result={}
 for m in re.finditer(r'^### (\d+\.\d+) (.+)\n',s,re.M):
  end=re.search(r'^##?#[ ]|^##[ ]',s[m.end():],re.M)
  result[m[1]]=s[m.end():m.end()+end.start() if end else len(s)].strip()
 return result
old=(P/'product.md').read_text();psec=sections(old)
s=old
# Keep background argument while reducing policy repetition.
a=s.index('教育数字化的发展');z=s.index('错题是观察',a)
s=s[:a]+'教育数字化政策持续推动数字资源与人工智能教育应用。《教育强国建设规划纲要（2024—2035年）》和《关于加快推进教育数字化的意见》提出资源共享与因材施教；2026年《“人工智能+教育”行动计划》进一步提出智能学伴等应用方向[ @policy ][ @digital ][ @ai_education ]。在线课程、题库和题目识别工具扩大了学生获取材料与解释的途径，日常错题处理中仍需要连接原作答、订正和后续练习。\n\n'+s[z:]
comp='''表0 学习工具与场景对照

| 工具 | 主要场景 | 原作答与解析 | 后续学习与记录 |
| --- | --- | --- | --- |
| Photomath | 扫描数学题并理解解法 | 官方展示分步解释与部分多解法 | 本次资料未确认其个人原步骤诊断与复习联动范围 |
| Anki | 卡片学习与间隔复习 | 以用户组织的卡片内容学习 | 官方提供学习步骤、复习间隔和每日数量设置 |
| 错题帮 | 个人错题订正与后续练习 | 关联原图、本人作答和诊断引用 | 保存帮助条件、新回答、任务进度与复习记录 |

表0按所核验资料比较使用侧重点；“未确认”表示资料范围，不表示其他产品不存在该能力。Photomath与Anki的功能依据分别为官方产品页和手册[ @photomath ][ @anki ]。

'''
s=s.replace('### 1.4 产品定位',comp+'### 1.4 产品定位')
a=s.index('## 3 产品特色');z=s.index('## 4 系统实现',a)
intro='''## 3 技术特色

错题帮围绕学生原作答组织四项相连的技术：先定位错误，再依据真实回答调整掌握估计，结合当前阶段安排后续学习，并为缺少候选的训练目标补充习题。图2概括材料、算法与学生新回答之间的联系。

![图2 错题学习技术总览](figures/01.png)

图2将错因定位、掌握评估、学习规划和习题补充分开，学生的实际作答进入下一轮学习记录。诊断解释用于订正，掌握估计用于安排训练，规划给出当前动作，补题提供具体可作答内容。

表99 问题、方法与项目特色

| 学生遇到的问题 | 采用的方法 | 项目落实的特色 |
| --- | --- | --- |
| 有答案却不清楚自己的错误位置 | 原步骤引用、规则检查与前序核对 | 诊断回到本人作答，区分错误候选和已核验首错 |
| 提示后答对与独立答对混在一起 | 按帮助条件赋权的掌握更新 | 保留求助记录，用不同影响解释后续安排 |
| 订正后不知道先练什么 | 当前阶段优先、条件过滤与排序 | 先解决本题困难，再选择时间内可完成的内容 |
| 题库有相似题却不一定适合 | 检索优先、技能准入和受约束生成 | 候选与原训练目标关联，保存为可恢复练习 |

'''
parts=[('3.1','错因定位',psec['3.1']),('3.2','掌握评估',psec['3.2']),('3.3','学习规划',psec['3.3'])]
for no,title,body in parts:
 if no=='3.3':body='\n\n'.join(x for x in body.split('\n\n') if not x.startswith('找题与出题'))
 intro+=f'### {no} {title}\n\n{body}\n\n'
intro+='''### 3.4 习题补充

学生理解原题后，需要一道检验相同知识的新题。仅按文字相似度找题，可能得到主题相近却使用不同方法的内容。系统先从已有题库查找候选，再确认候选是否真正符合当前训练目标。

**题库检索与模型生成共同提供习题，但各自保留来源。**题库题检查学科、年级、可作答材料、参考答案及技能匹配；没有合格候选时，系统依据原题、知识目标和当前学习范围生成新题。一般生成题还要经过同技能、答案、材料完整性和年级适配检查，才能进入练习[ @rag ]。

受支持的一元一次方程采用可解构造。例如先确定目标解为－7，再形成5x＋3＝－32，题干、答案与解析来自同一组参数。这个方法让指定方程题能够复算；其他学科依赖相应模型与内容检查，按具体题型说明结果。

仓颉保存通过检查的题目与会话。学生提交后可以重新读取同一结果，继续练习时再取得下一题；新题暂不可用时保留当前资料。习题补充因此同时解决训练内容与连续使用两个问题。

'''
s=s[:a]+intro+s[z:]
# Reduce duplicated technology encyclopedia, preserve meaningful responsibilities.
s=s.replace('前端使用uni-app、Vue 3和TypeScript构建。uni-app提供共享页面和跨端工程能力，Vue组织页面组件，TypeScript帮助检查数据使用方式[ @uniapp ][ @vue ]。','')
s=s.replace('当前页面功能与源码基线0092d19对应，项目实施记录保存了功能范围和验证批次[ @project ]。','本文源码核对基线为d01d742，功能及历史验收范围由实施记录说明[ @project ]。')
s=s.replace('开发环境通常使用仓颉8002端口、算法8012端口，前端端口可以配置；这些是运行设置，不影响学生账号中的题目和记录。','')
a=s.index('### 5.5 工程验证');z=s.index('## 6 成果与计划',a)
s=s[:a]+'''### 5.5 工程验证

表98归纳已有工程验证。完整回归与后续局部修复分别登记，测试日期及范围保持原记录；本次核对源码基线d01d742，并补查练习模式刷新恢复的6项针对性测试。

表98 工程验证概况

| 证据 | 已有结果 | 支持的结论 |
| --- | --- | --- |
| 2026年10月22日完整回归 | 前端290、算法690、仓颉46、浏览器71项通过 | 规定样例中的业务、算法、保存与主要流程 |
| 后续显示与构建检查 | 前端299项及局部56项通过；H5/App资源构建完成 | 对应排版、公式及跨端资源修复 |
| 2026年10月23日模式恢复专项 | 6项通过 | 切换变式后刷新保持模式与已判结果 |

这些结果支持现有用例中的工程行为。真实模型样例、受控返回和规则演算分别登记；学生学习收益与全部题型准确率仍需专项研究。详细证据索引单独保存，不与本章案例合并为学生实验。

'''+s[z:]
s=s.replace('项目的三项重点设计已经进入实际程序。','项目的四项重点设计已经进入实际程序。').replace('后续安排检查当前任务、候选题和可用时间。','后续安排检查当前任务、候选题和可用时间；习题补充连接技能匹配与保存后的实际作答。')
# Reuse ongoing work record in implementation, avoiding separate feature subsection.
s=s.replace('### 4.4 运行与使用',psec['3.4'].split('\n\n')[1]+'\n\n### 4.4 运行与使用')
# Renumber all table mentions in occurrence order, including introduction references.
nums=[]
for m in re.finditer(r'^表(\d+) ',s,re.M):
 if m[1] not in nums:nums.append(m[1])
s=re.sub(r'表(\d+)',lambda m:'表'+str(nums.index(m[1])+1) if m[1] in nums else m[0],s)
(B/'product.md').write_text(s)
# Seven-chapter technical design, drawing from fact-corrected revision and preserving original mechanisms.
ss=sections((P/'system.md').read_text())
out='# 错题帮系统设计文档\n\n2026“仓颉杯”智能编程大赛\n\n'
def chapter(n,title,opening=''):
 global out
 out+=f'## {n} {title}\n\n'+(opening+'\n\n' if opening else '')
def sub(n,title,body):
 global out
 out+=f'### {n} {title}\n\n{body.strip()}\n\n'
chapter(1,'总体设计','错题帮面向中学生个人错题学习，使用uni-app客户端、仓颉业务服务和Python算法服务。系统以学生原题和真实回答为依据，完成诊断、训练及复习；本报告重点说明四项算法、智能体流程、数据保存与运行验证。源码核对基线为d01d742。')
sub('1.1','设计目标',ss['1.1']+'\n\n'+ss['1.3'])
sub('1.2','系统架构',ss['2.1']+'\n\n'+ss['2.3'])
sub('1.3','技术选型',ss['2.2'])
sub('1.4','模块职责',ss['1.2']+'\n\n'+ss['2.4'])
chapter(2,'核心算法','四项算法分别处理错误位置、掌握估计、下一动作和训练内容。输入由仓颉组织，Python返回结果及依据，仓颉按当前题目和任务状态保存。下面依次介绍问题、输入输出、处理规则、演算与适用范围。')
sub('2.1','错因定位算法','**设计问题与输入输出。**学生可能使用不同解法，也可能只写出答案。错误定位需要先确认实际作答，再区分有证据的错误与尚待确认的解释。\n\n'+ss['3.3'])
sub('2.2','掌握更新算法',ss['4.1'])
sub('2.3','学习规划算法','**设计动机。**当前题目尚未订正、材料不完整或时间已用完时，单一相似度评分不足以决定下一步。因此先确定当前行动，再对合格候选排序。\n\n'+ss['4.2'])
sub('2.4','习题补充算法','**输入与输出。**输入是当前题目、学科年级、训练模式、目标技能和近期曝光记录。输出为带来源的具体练习候选，或当前无合格内容的结果。学生真正看到的题目还需由仓颉保存为可恢复会话。\n\n'+ss['4.3'])
chapter(3,'智能体设计','单协调器组织本题算法和工具反馈；学生交互、任务保存与等待由仓颉和前端共同承接。一次算法调用与跨多轮的学习任务分别管理。')
sub('3.1','协调架构',ss['5.1'])
sub('3.2','工作流设计',ss['5.2']+'\n\n'+ss['3.4'])
sub('3.3','工具与会话',ss['5.3']+'\n\n'+ss['5.4'])
sub('3.4','任务状态',ss['5.5'])
chapter(4,'数据设计','题目、实际步骤、学习事件和检查点各自保留身份。材料来源说明算法针对哪份内容，任务版本说明学生针对哪个进度提交，二者共同决定后续结果是否可采用。')
sub('4.1','数据关联',ss['6.1'])
sub('4.2','版本管理',ss['6.2'])
sub('4.3','异步提交',ss['6.3'])
sub('4.4','学习记忆',ss['6.4'])
chapter(5,'系统实现','客户端接收学生输入，仓颉执行业务规则和事务，Python实现算法接口。各层使用同一题目及事件关系，页面展示最终保存的学习状态。')
sub('5.1','前端实现',ss['7.1']+'\n\n'+ss['3.1'])
sub('5.2','业务服务',ss['7.2']+'\n\n'+ss['4.5'])
sub('5.3','算法服务',ss['3.2']+'\n\n'+ss['4.4'])
sub('5.4','安全容错',ss['7.3'])
sub('5.5','部署方案',ss['7.4'])
chapter(6,'系统验证','验证按算法机制、业务记录和真实页面流程组织。2026年10月22日完整回归记录前端290项、算法690项、仓颉46项和浏览器71项通过；后续显示修复分别保留299项及56项专项记录。2026年10月23日补查练习模式恢复6项通过。各批次不相加，详细环境与日志另存为独立验收材料。')
sub('6.1','算法机制', '\n\n'.join(ss['8.3'].split('\n\n')[:5])+'''\n\n规则验证采用固定输入和可复算输出，模型返回可被替换以稳定触发异常分支。关键情境见表97。\n\n表97 算法机制与反向情境\n\n| 算法 | 正向检查 | 反向检查 |\n| --- | --- | --- |\n| 错因定位 | 正确前缀后定位不等价一步 | 伪造引用、未核验前缀保留核对 |\n| 掌握更新 | 独立与提示产生不同权重 | 答案曝光、局部及重复事件不增加整题证据 |\n| 学习规划 | 合格到期题优先并稳定排序 | 学科不符、时间超限、刚完成题过滤 |\n| 习题补充 | 构造可解方程并保存练习 | 不同技能、缺图和失败候选不准入 |''')
sub('6.2','业务一致性','\n\n'.join(ss['8.3'].split('\n\n')[-4:]))
sub('6.3','功能流程','接口与浏览器验证分别检查实际保存和学生操作。录题后能够回看原图和确认内容；诊断后能够提交局部订正，再进入独立回答；类似题提交后刷新保留回执；练习考试中的错题收录保留题干、选项、配图和原作答。工作流样例为受控输入，真实模型运行案例另按原始归档说明。\n\n前端模式恢复专项检查切换变式、提交、离开和重新进入后仍读取同一模式及已保存结果。6项组件测试通过，执行中记录了开发WebSocket监听权限及组件桩警告；通过结果仅用于该组件行为，不推断新的全站验收。\n\nH5及App资源构建检查共享代码与资源产物。现有手机视口浏览器记录支持页面布局与输入操作；签名安装、相机权限和后台恢复仍需真实设备验收。')
sub('6.4','验证分析',ss['8.4'])
chapter(7,'总结与展望')
sub('7.1','系统成果','\n\n'.join(ss['9.1'].split('\n\n')[:2]))
sub('7.2','改进方向',ss['9.2'])
# Fix moved references, baseline and formula-chart description.
out=out.replace('0092d19','d01d742').replace('第4.4节','第5.3节').replace('第4.5节','第5.2节').replace('第4.1节','第2.2节')
out=out.replace('图3比较相同起点下三种作答条件的更新结果。独立答对与提示后答对采用不同权重，看过完整答案后的回答不提高这一估计值。图中0.914、0.608与0.350来自同一先验的规则演算，不是学生实验数据。','图3依次显示事件资格、帮助条件对应权重和状态更新。底部列出相同先验下的三种独立演算结果；这些数值解释默认规则，不是学生实验数据。')
out=out.replace('图2左侧，原题和第一步的解都是4，第二步的解是5；右侧说明前面步骤未确认时的处理。','图2上方组织来源检查、证据评分和前缀核对；下方对照前序成立与证据不足两种情况。')
# Retain references where methods apply; no Pydantic/SymPy standalone technology section.
out=out.replace('当前工程支持H5与App资源构建','当前工程支持H5与App资源构建')
# Renumber table captions and their mentions in their new order.
nums=[]
for m in re.finditer(r'^表(\d+) ',out,re.M):
 if m[1] not in nums:nums.append(m[1])
out=re.sub(r'表(\d+)',lambda m:'表'+str(nums.index(m[1])+1) if m[1] in nums else m[0],out)
(B/'system.md').write_text(out)
print('draft characters',len(s),len(out))
