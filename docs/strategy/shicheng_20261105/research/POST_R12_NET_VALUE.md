# 教师经验相对强辅导的净值：定向新证据

2026-11-05。先读13、22、CONT_AI、NEXT_CONCRETE_BASELINES；依已应用的 academic-research-suite bibliography/source_verification 合约做定向核验。本稿不评R13、不评分，不改正式稿。

**结论：新增三项均有真实学生，但仍没有直接证明“同模型、同内容、同历史的强辅导，加教师决策案例后净值更高”。**它们分别提供教师反馈的强替代、结构化帮助的有限增量、持续使用的约束。保持完整学生伙伴；不据此重选题型或转教师平台。

## 1｜Worden 等：教师写的反馈没有自然形成优势

*A Large Scale Randomized Control Trial Showing LLM Generated Feedback Helps Low-Knowledge Middle School Math Students with Short-Term Learning*，ACM L@S，**2026-06-28**，[正式论文/DOI](https://doi.org/10.1145/3774398.3811594)。作者本人的[EDM2026报告§2](https://educationaldatamining.org/edm2026/proceedings/2026.EDM.doctoral-consortium-papers.460/index.html)补充“不存在可靠差异”的表述。

方法/样本：ASSISTments初中数学两项RCT；第二项12,950人，AI反馈对专家教师反馈。AI材料由Qwen-235B预生成，并有教师参与提示设计、初始核验及后续模型筛查。第一项20,706人，对照主要为正确性反馈。摘要报两试验合计21,478人，**单项人数不可相加**，口径关系未核。

位置/读取：正式摘要与出版元数据、作者EDM报告§2；ACM全文/PDF均未取到。后者是同一研究者的报告，不算独立复现。第二项摘要称学习结果相当；未读到效应CI、等效界限或延后测验，不能写成已证明严格等效/不劣。也不能把第一项的相对改善改写为百分点。

支持：经设计和筛查的LLM缓存反馈是有真实学生依据的强替代。反证：教师身份或人工撰写本身未表现出必然溢价；AI组已有教育者投入，研究没有隔离“教师贡献有无”。

**产品决定：**强基线应允许同样优质提示、筛查和缓存反馈；保留固定帮助优先路径。新增经验的价值须落在少误教、少无益帮助及可持续维护，不能以“教师写的”直接推优。

## 2｜Oreopoulos、Liut、Sungu、Low：NUMI结构化帮助有信号，保持增益很有限

*Making AI Tutoring Productive: Evidence from a Mastery-Based Math Practice Experiment*，**2026-08-17**，[作者工作论文全文](https://edworkingpapers.com/sites/default/files/ai26-1552.pdf)，[机构元数据/DOI](https://edworkingpapers.com/ai26-1552)。未当作已同行评议论文。

方法/样本：美国同一学区6—8年级，个人随机AI/无AI、掌握进度/自由进度及主题；两组有相同视频、题目和例解。首周分析6,997人，延后分析6,327人；一次约50分钟练习，一周后测。不是同模型强聊天对照。

位置/读取：重点读§3—5、Table1/9、附A2及A12，不冒称逐页审完73页。Table9掌握组3,209人：练过的Exercise1，AI40.2%对37.0%，差**3.2个百分点，SE1.7，附A2 p=.065**；未练对应题差0.2个百分点。即时订正改善伴随时间增加；掌握进度本身未提高延后学习。延后分析只含回测者，存在选择边界。

支持：在相同CAL内容上，交互帮助可能增加有限收益。反证：不支持普遍显著保持或广泛迁移；更慢也会减少接触后续内容，不能只报订正率。

**产品决定：**净值判断应同时看固定时间内的自主结果与帮助耗时/未接触内容；不得据此增设“三连对才退出”门槛。现有可结束、撤助与延后分列应保留。

## 3｜Oreopoulos、Low：Khanmigo的可达不等于有效使用

*One Click Away: AI Tutoring with Khanmigo in a Two-Year School Experiment*，**2026-08**，[作者工作论文全文](https://edworkingpapers.com/sites/default/files/ai26-1551.pdf)，[机构元数据/DOI](https://edworkingpapers.com/ai26-1551)。未当作已同行评议论文。

方法/样本：18所美国初中，校内年级集群随机；6,902是**学生—学期观测**，不是独立人数。干预是Khan Academy＋Khanmigo，随机对照为常规补救教学及其他CAL，**不是同Khan Academy去掉AI**。

位置/读取：重点读引言、设计与使用部分、Table5、附A5及日志样本说明。整体每学期约增1.3全国百分位名次；主模型显著，野生集群bootstrap p=.051。第二年可匹配日志仅563学生：95.7%尝试过，典型学生只在17%的出错练习会话发消息。这一比例不是全体随机学生的统一使用率。“收益像无AI平台”来自另项准实验的跨研究比较，不能改写成随机识别AI零增益。

支持：完整课程练习服务可产生小幅实际收益。反证：开放聊天入口与限制给答案，并不保证学生实质推理参与。

**产品决定：**后续优先核学生在卡点是否愿意开始并完成一步，追踪主动不用、退出和恢复；不以注册、曾用或聊天量证明伙伴价值，也不照搬强制参与。

## 核验、检索与剩余缺口

证据等级：三项设计均属II级RCT；第一项因仅摘要降低结果解读信心，后两为工作论文。出版社/作者机构元数据与题名匹配；**未启用程序化S2核验，按出版社/作者页核对。**曾用浏览工具尝试打开Worden与NUMI的两个S2 Graph API DOI查询地址，均返回URL不可访问；这只说明该浏览入口未取到结果，不能断言S2服务不可用，未取得S2 ID。未做付费期刊审计；未核完独立COI声明。作者参与ASSISTments或自建/合作平台评价，有研究者及平台关联；后两同一学区、部分同作者，不能当跨地区复制，更不能外推中国乡村。

检索范围：2023—2026，英文；Web检索定位ACM、Springer、arXiv、作者机构及Brown/NBER存档。词组含“LLM math tutor pedagogical strategies randomized students same model”“teacher pedagogical expertise”“LLM generated feedback teacher-written”“Making AI Tutoring Productive”“One Click Away”，并逐篇题名/DOI追踪。去重已有研究；AIED反馈风格原章未取得，仅列后续候选，不追加为第四项证据。此为定向检索，未记录完整数据库命中总数，不冒称系统综述。

三项没有隔离当前“教师决策案例＋边界＋本人历史”的增量，也没有比较中国家庭中的持续伙伴负担与成本。下一步最有价值的决定是维持公平强基线，把真实自主收益、总负担和维护投入作为共同净值条件；公开研究支持继续检验，尚不支持宣称已经胜出。
