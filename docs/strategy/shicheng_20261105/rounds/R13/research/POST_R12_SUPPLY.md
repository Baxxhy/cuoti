# 内容供给一手补证（不评分）

核验：2026-11-05。已读09、25、22及NEXT_CONTENT_PRODUCTION、CONT_AI去重；OATutor/ITB、PLOS、PromptHive不计新样本。MathDial此前已在AI_EVIDENCE E3引用，本轮是2项新增来源（ReadingQuizMaker、VIVID）＋MathDial新增生产细节，不能算3篇全新研究；三者均独立于OATutor团队。结论：有真实教师编制、筛选与修订的生产路径先例；没有可直接填入本项目的中文决策内容合格产能、完整双审工时或国内报价。

## 检索与核验范围

按academic-research-suite的bibliography/source_verification合约作定向补缺：2023—2026，英文原始论文/作者公开副本/官方内容说明，检索ACL、作者大学网站、arXiv、出版方；检索式包括“MathDial compensated”“educational content authoring minutes teachers”“ReadingQuizMaker”“VIVID vicarious”。不是系统综述，搜索引擎未给稳定总命中数，不伪造PRISMA计数。正文筛查MathDial、ReadingQuizMaker、Generative Students、VIVID；Generative Students仅有有限改题案例，改选返工证据更直接的VIVID。Khan官方内容团队旧页不可访问，未据摘要凑供给数字。最终报告3项材料，其中MathDial按已有来源补充生产细节处理。

曾用浏览工具尝试打开三项S2元数据API地址，未取到内容；这只说明本次访问尝试失败，不能断言S2服务不可用。ARS默认采用浏览核验，不以API可达为前提。本次DOI地址直开也未成功，实际以ACL记录、作者大学PDF、arXiv及出版方索引互核题名/作者/年份。未读程序、未运行模型。三项均为作者评估自有系统，有知识/项目利益关联；无独立商业验收或中国生产审计。证据等级按具体问题：生产描述为VI，VIVID受控作者研究可作III参考，不把这一等级移作学生效果证明。样本集中海外、2023—2024且2/3来自CHI，不能代表国内供给市场。

## 1. MathDial：教师决策可以落实到可交付对话，但不是六分钟合格包

Macina, J., Daheim, N., Chowdhury, S. P., Sinha, T., Kapur, M., Gurevych, I., & Sachan, M. (2023). *MathDial: A dialogue tutoring dataset with rich pedagogical properties grounded in math reasoning problems*. Findings of EMNLP, 5602–5621. [原始记录与PDF](https://aclanthology.org/2023.findings-emnlp.372/)，会议日期2023-12-06—10。已读§3—4、附录D及局限，非仅摘要。

事实：91名有教学经验的采集者，培训测试须满分；作者检查每人若干初始对话。先标错误解的首个错误，再选教学动作、写回应。发布2861段完整对话；约6分钟/段，末批报酬折合12美元/小时。这是对话采集时间，未含可核完整独立双审、返工及维护，不能相乘当我方单价。细动作复核仅17段/102条话语，两复核者κ=0.60。

边界：学生由LLM模拟，发布数不等于本项目合格决策数，更不证明真人学会。[作者README](https://github.com/eth-nlped/mathdial)写CC BY-SA 4.0，[官方数据卡](https://huggingface.co/datasets/eth-nlped/mathdial)显示CC BY 4.0，当前冲突仍在；未核清版本与上游前，不把整库直接作为商用素材。可借鉴“错误依据→动作→回应”生产结构。

## 2. ReadingQuizMaker：真实作者产出与修改记录，不能当独立验收

Lu, X., Fan, S., Houghton, J., Wang, L., & Wang, X. (2023). *ReadingQuizMaker: A human-NLP collaborative system that supports instructors to design high-quality reading quiz questions*. CHI. DOI:10.1145/3544548.3580957。[作者大学原文PDF](https://web.eecs.umich.edu/~xwanghci/papers/CHI23-ReadingQizMaker.pdf)，会议2023-04-23—28。读§5—6、限制及首页权利声明。

13名大学教师，每人有45分钟协作编题、另20分钟审改预生成题；共制89题。规定时段不是89题独立验收后的净工时。日志：88条改写建议被采纳，23条仍经作者编辑。50美元补偿整个90—100分钟研究，不是编题报价。质量与省时主要为作者自评，固定任务顺序也限制效率比较。

可外推：候选、作者选用、修改、发布分别记数；采纳不等于审核合格，大学阅读题速度不外推初中数学。PDF的ACM权利声明不授予题库商用；独立内容许可未确认，可参考工序。

## 3. VIVID：人工修订确有质量作用，仍须回查原始条件

Choi, S., Lee, H., Lee, Y., & Kim, J. (2024). *VIVID: Human-AI collaborative authoring of vicarious dialogues from lecture videos*. CHI. DOI:10.1145/3613904.3642867。[作者预印本v1全文](https://arxiv.org/html/2403.09168v1)，2024-03-14；出版方索引为2024-05-11。本轮细节取v1的§6.1、6.3—6.4、7.1，不假定版本结果完全相同。

12名STEM教师为中学数学/科学讲解制作对话。4名教师复核24段修订前及对应24段修订后对话；错误话轮比例处于0—10%的对话，由17/24升到22/24，不能说22段零错误。转写遗漏必要数学条件等问题修订后仍约17%，原文分母不够明确，不计算我方退稿率。未报可复用净工时；45,000韩元/小时是参与研究补偿。主观效率与基线无显著差异。

可外推：把原材料条件缺失与派生内容错误分开检查，不能只润色最终对话。v1论文CC BY-NC-SA 4.0不等于视频、转写和生成对话获商用授权；本轮未确认后者，引用研究即可。

## 对现有供给与经营的具体影响（推论）

1. 保留完整学生伙伴。后台按“一个学习目的＋可观察困难＋对应动作及继续/换法条件＋自主任务”的决策案例组织制作，与四入口共享；不是再建教师平台，也不拿对话条数代替产品范围。
2. 在现有流程前落实作者样例校准、原文条件核对；制作时固定正确解与首个错误/困难依据。数学审核先核原始材料与派生例子，教学审核再核动作是否匹配目标、是否过早泄露以及适用边界。分歧留理由、退回作者修订，不只求标签一致。
3. 沿用25的全成本口径，把首次制作、作者修订、独立审阅、失败候选、学生所见呈现、版本回查分开计时；产出只计正式通过版本。来源条件变化时，回查受影响例题、帮助与自主任务，再复用同一合格版本服务多次学习。以上事实支持可组织生产，不支持预先承诺日产量、低价或无限维护。

未找到中国本地教师/数学审核者的可核正式报价，也没有三项中的完整中文双审维护成本；不填估造数字。可引用这些先例解释资源角色和计量单位，不能替代我方实际投入记录或授权。
