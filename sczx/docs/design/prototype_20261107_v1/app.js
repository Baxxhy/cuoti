const storageKey = 'shicheng-design-v1';
const initialState = {
  published: false,
  casePublished: false,
  completed: false,
  helped: false,
  questionIndex: 0,
  answers: [],
  review: false,
  plan: '从两边相等的天平出发，请学生预测同时增加相同砝码后的变化，再用等式表达观察结果。',
  feedback: '已经能解释两边同时增加相同数量的原因。请继续完成一道新题，尝试独立说明每一步。',
  balance: 0
};
let state = { ...initialState };
try {
  state = { ...initialState, ...JSON.parse(localStorage.getItem(storageKey) || '{}') };
} catch {
  state = { ...initialState };
}
const students = [
  { name: '林同学', progress: '已提交', help: '提示 1 次', result: '新题独立完成' },
  { name: '陈同学', progress: '学习中', help: '换讲法 1 次', result: '待检查' },
  { name: '周同学', progress: '未开始', help: '—', result: '—' }
];
const questions = [
  { stem: '已知 x − 3 = 5，等式两边同时加上 3，得到什么？', answer: '8', hint: '两边同时加上 3，左边的 −3 与 +3 抵消。右边也需要加上 3。', formula: 'x − 3 = 5' },
  { stem: '已知 y + 4 = 11，等式两边同时减去 4，y 等于多少？', answer: '7', hint: '左边减去 4 后只剩 y，右边进行相同运算。', formula: 'y + 4 = 11' }
];
const routes = {
  student: [['home', '我的学习'], ['courses', '课程'], ['wrong', '错题帮'], ['records', '学习记录']],
  teacher: [['teacher', '教学首页'], ['cases', '教学案例'], ['prepare', '我的教案'], ['class', '班级教学']],
  admin: [['manage', '管理首页'], ['manage', '资料与案例'], ['content', '课程内容'], ['issues', '反馈与运行']]
};
const roleNames = { student: '学生端', teacher: '教师端', admin: '内容管理端' };
const main = document.querySelector('#main');
const dialog = document.querySelector('#dialog');
let role = 'student';
let toastTimer;

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}
function save() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(state));
    return true;
  } catch {
    toast('浏览器暂时无法保存，当前页面仍可继续操作。');
    return false;
  }
}
function toast(message) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('show'), 3200);
}
function link(route, text, primary = false) {
  return `<a class="button ${primary ? 'primary' : ''}" href="#${route}">${text}</a>`;
}
function button(action, text, primary = false) {
  return `<button data-action="${action}" class="${primary ? 'primary' : ''}">${text}</button>`;
}
function header(title, description, action = '') {
  return `<div class="page-header"><div><h1>${title}</h1><p class="muted">${description}</p></div>${action}</div>`;
}
function breadcrumb(text, back = 'home', backLabel = '我的学习') {
  return `<div class="breadcrumb"><a href="#${back}">${backLabel}</a><span>/</span><span>${text}</span><span>· 演示</span></div>`;
}
function balance() {
  const count = state.balance;
  return `<div class="balance" aria-label="等式天平，两边始终进行相同操作"><div class="balance-base"></div><div class="beam"><div class="pan left"><span class="weight">x</span>${count ? `<span class="weight">${count}</span>` : ''}</div><div class="pan right"><span class="weight">5${count ? `+${count}` : ''}</span></div></div><span class="balance-caption">${count ? `两边同时加 ${count}，仍然相等` : '起始状态：x = 5'}</span></div>`;
}
function home() {
  return `${breadcrumb('学习首页')}${header('今天，从一个好问题开始。', '七年级数学 · 一元一次方程', link('courses', '浏览课程'))}
    <div class="grid">
      <section class="panel tonal lesson-focus span-8"><div><div class="course-meta"><span>继续学习</span><span>等式性质 · 第 1 课</span></div><h2>两边做同样的事，<br>为什么依然相等？</h2><p class="muted">从一架天平开始，理解等式的变化。</p></div><div><div class="progress"><span style="width:${state.completed ? 100 : 40}%"></span></div><div class="panel-head"><small class="muted">${state.completed ? '本课已提交，可回看学习过程' : '正在学习：观察与解释'}</small>${link('learn', state.completed ? '回看本课' : '继续学习', true)}</div></div></section>
      <section class="panel span-4"><div class="panel-head"><h2>接下来</h2><span class="status">演示任务</span></div><div class="row"><div><p>独立完成一道新题</p><small>检查对等式性质的理解</small></div></div><div class="row"><div><p>回看一道错题</p><small>解释两边怎样一起变化</small></div></div><div class="actions">${link('check', '开始检查')}${link('wrong', '查看错题')}</div></section>
      <section class="panel span-7"><div class="panel-head"><h2>教师任务</h2><a class="detail-link" href="#class">查看演示班级</a></div><div class="row"><div><p>等式性质 · 观察、解释与应用</p><small>七年级一班 · ${state.published ? '教师已模拟发布' : '示例任务'}</small></div><span class="status">${state.completed ? '已提交' : '学习中'}</span></div><div class="row"><div><p>教师给你的反馈</p><small>${escapeText(state.feedback)}</small></div></div></section>
      <section class="panel span-5"><h2>复习与发现</h2><div class="row"><div><p>等式两边必须同时变化吗？</p><small>从原作答中找到问题</small></div><a href="#repair" class="detail-link">去复习</a></div><div class="row"><div><p>下一课：解简单的一元一次方程</p><small>继续连接本课的知识</small></div><a href="#courses" class="detail-link">查看</a></div></section>
    </div>`;
}
function learning() {
  return `${breadcrumb('等式性质')}${header('等式的两边，一起变化', '第 1 课 · 观察、解释与应用', link('check', '进入独立检查'))}
    <div class="steps"><span class="current">观察天平</span><span>解释变化</span><span>随堂尝试</span><span>独立检查</span></div>
    <div class="grid"><article class="panel span-8"><h2 class="serif">如果两边同时增加，会发生什么？</h2><p>天平两边原本相等。试着给两边增加相同数量，再观察它们之间的关系。</p>${balance()}<div class="actions">${button('add-weight', '两边同时加 1')}${button('reset-weight', '重置天平')}</div><hr class="rule"><h3>用数学表达你的观察</h3><div class="formula-strip math">a = b &nbsp; ⇒ &nbsp; a + c = b + c</div><p>等式两边同时加上同一个数，结果仍然相等。你可以把它理解为保持相等关系的一次共同变化。</p><label for="observation">如果只改变左边，你认为会发生什么？</label><textarea id="observation" placeholder="写下你的观察和理由"></textarea><div class="actions">${button('save-observation', '保存解释', true)}${link('check', '我来独立试一试')}</div></article>
    <aside class="panel tonal span-4"><h2>需要一点帮助吗？</h2><p class="muted">选一种适合你的方式，再回到自己的思考。</p><div class="actions">${button('example', '举个例子')}${button('explain', '换种讲法')}</div><div id="learning-help"><blockquote>“相等”关注的是两边的关系。改变的时候，也要一起考虑两边。</blockquote></div><hr class="rule"><label for="question">向学习助手提问</label><textarea id="question" placeholder="例如，为什么不能只加一边？"></textarea>${button('ask', '发送问题')}<label for="question-image">也可以上传题图</label><label class="file-picker" for="question-image">选择本地题图<input id="question-image" type="file" accept="image/*"><span id="image-name">尚未选择</span></label><p class="source">帮助内容为原型预设演示。教学方法将由公开案例支持。</p></aside></div>`;
}
function check() {
  const question = questions[state.questionIndex];
  return `${breadcrumb('独立检查', 'learn', '等式性质')}${header('这一次，试着独立解释', '先完成自己的作答，需要时也可以获得帮助。')}
    <div class="grid"><section class="panel span-8"><div class="panel-head"><h2>检查题 ${state.questionIndex + 1}</h2><span class="status ${state.helped ? 'pending' : ''}">${state.helped ? '本题已获得帮助' : '本题尚未求助'}</span></div><p class="case-title">${question.stem}</p><div class="formula-strip math">${question.formula}</div><label for="answer">填写结果</label><input id="answer" inputmode="decimal" placeholder="请输入数值"><label for="reason">你是怎样保持等式成立的？</label><textarea id="reason" placeholder="说明两边进行了什么运算"></textarea><div id="check-feedback"></div><div class="actions">${button('submit-answer', '提交作答', true)}${button('hint', '我需要提示')}${link('result', '保存并稍后继续')}</div></section><aside class="panel tonal span-4"><h2>关于这次检查</h2><p>每一道题都会保留你的原作答和使用过的帮助。</p><p>如果查看了提示，你可以先理解当前题，再换一道新题尝试独立完成。</p><div class="actions">${button('new-question', '换一道新题')}</div><hr class="rule"><p class="source">原型包含两道检查题。两题均已作答后，可保存当前结果或返回课程复习。</p></aside></div>`;
}
function result() {
  const last = state.answers.at(-1);
  return `${breadcrumb('本课结果')}${header('每一次尝试，都有迹可循', '等式性质 · 你的学习过程', link('learn', '回到本课'))}
    <div class="grid"><section class="panel span-8"><h2>本次学习</h2><div class="row"><div><p>观察与解释</p><small>保持等式两边相等的变化</small></div><span class="status">${state.observation ? '已保存解释' : '可以继续'}</span></div><div class="row"><div><p>独立检查</p><small>${last ? `最近一次结果：${last.correct ? '答案正确' : '需要再练习'} · ${last.helped ? '获得过帮助' : '独立作答'}` : '还没有提交检查题'}</small></div>${link('check', '查看检查')}</div><div class="row"><div><p>错题与补救</p><small>${state.review ? '已完成一次补救尝试' : '解释两边怎样进行相同变化'}</small></div>${link('repair', '去补救')}</div><div class="actions">${button('complete', state.completed ? '再次提交本课结果' : '提交本课结果', true)}${link('records', '查看全部记录')}</div></section><aside class="panel tonal span-4"><h2>教师反馈</h2><p>${escapeText(state.feedback)}</p><p class="source">演示反馈，可在教师端修改。</p>${link('home', '返回我的学习')}</aside></div>`;
}
function wrong() {
  return `${breadcrumb('错题帮')}${header('把没想明白的地方，再想明白', '保存原题和你的思考，找到下一次可以独立完成的方法。', button('upload', '录入一道题', true))}
    <div class="list-tabs"><a class="selected" href="#wrong">全部错题</a><a href="#repair">待补救</a><a href="#records">复习记录</a></div><div class="grid"><article class="panel span-8"><div class="course-meta"><span>等式性质</span><span>来自课程随堂练习 · 演示</span></div><h2 class="case-title">x + 3 = 8，怎样消去左边的 3？</h2><div class="formula-strip"><span class="muted">原作答</span><div class="math">x = 8 + 3</div></div><p class="muted">需要回看的地方：左边减去 3 时，右边应该怎样变化？</p><div class="actions">${link('repair', '开始补救', true)}${link('result', '查看来源任务')}</div></article><aside class="panel tonal span-4"><h2>保留你的思考过程</h2><p>原题、最初的作答、得到的提示与后来的尝试，会一起留在学习记录里。</p><hr class="rule"><h3>独立录题</h3><p class="muted">拍照或手动输入题目，先确认题目，再开始学习。</p>${button('upload', '拍照或手动录入')}</aside></div>`;
}
function repair() {
  return `${breadcrumb('错题补救', 'wrong', '错题帮')}${header('两边的变化，要保持一致', '来自等式性质 · 保留最初的作答，重新解释你的方法。', link('result', '返回原任务'))}
    <div class="grid"><section class="panel span-7"><h2>先看原来的想法</h2><div class="math">x + 3 = 8<br>x = 8 + 3</div><p>左边的 +3 被去掉了，右边却增加了 3。可以先想一想：我们对两边做的是同一件事吗？</p><blockquote>两边同时减去 3，等式仍然成立。</blockquote><div class="formula-strip math">x + 3 − 3 = 8 − 3<br>x = 5</div></section><section class="panel tonal span-5"><h2>换个数字，再试一次</h2><p>如果 z + 2 = 9，你准备对两边进行什么运算？</p><label for="repair-answer">填写 z 的值</label><input id="repair-answer" inputmode="decimal" placeholder="你的答案"><label for="repair-reason">说明你的方法</label><textarea id="repair-reason" placeholder="两边同时……"></textarea><div id="repair-feedback"></div><div class="actions">${button('repair-submit', '提交这次尝试', true)}${link('result', '返回任务')}</div></section></div>`;
}
function cases() {
  return `${breadcrumb('教学案例', 'teacher', '教学首页')}${header('从好的教法，开始一堂课', '围绕教学目标与学生困难，寻找可以借鉴的经验。')}
    <div class="filter"><input id="case-search" aria-label="搜索教学案例" placeholder="搜索教学目标或学生困难"><select aria-label="学科"><option>七年级数学</option></select><select aria-label="单元"><option>一元一次方程</option></select>${button('search', '查找案例')}</div><div id="case-results" class="grid"><article class="panel span-8"><div class="course-meta"><span>等式性质</span><span>教学案例示例 · 团队编写</span></div><h2 class="case-title">从天平上的变化，走向等式的性质</h2><p class="case-preview muted">当学生习惯“移过去变号”，却无法解释原因时，通过观察、预测和共同操作，重新连接等式两边的关系。</p><div class="row"><span class="muted">适用困难</span><span>只改变一边 · 对变号理解机械</span></div><div class="actions">${link('case-detail', '阅读完整案例', true)}${link('prepare', '用于备课')}</div></article><aside class="panel tonal span-4"><h2>让经验进入教学</h2><p>先理解案例怎样判断学生的困难，再根据本班基础调整提问与活动。</p><hr class="rule"><p class="source">当前展示团队编写的案例结构示例。真实内容整理时登记公开材料、作者与原文定位。</p>${link('manage', '查看内容整理')}</aside></div>`;
}
function caseDetail() {
  return `${breadcrumb('案例详情', 'cases', '教学案例')}${header('从天平上的变化，走向等式的性质', '团队编写案例示例 · 等式性质', link('prepare', '用于备课', true))}<div class="grid"><article class="panel span-8"><h2>从学生的解释开始</h2><p>先请学生观察两边相等的天平，预测两边同时加入相同砝码后会发生什么，再通过操作验证。</p><blockquote>“你认为它还会保持平衡吗？如果只在左边加一个，会发生什么？”</blockquote><h2>把观察写成等式</h2><p>记录两边同时加上相同数的过程，引导学生说出“同时”和“相同”各自的含义。</p><div class="formula-strip math">a = b ⇒ a + c = b + c</div><h2>根据回应调整</h2><p>学生只说“移项变号”时，回到两边同时减去相同数的完整过程。学生能解释时，给出改变数字的新题，观察能否独立应用。</p></article><aside class="panel tonal span-4"><h2>使用前看一看</h2><p>前置基础：理解相等关系与加减法。</p><p>目标：解释等式两边的共同变化，并应用到简单等式。</p><hr class="rule"><h3>内容来源</h3><p class="source">流程原型中的团队编写示例。公开资料原文将在内容建设阶段补充核对。</p>${button('favorite', '收藏案例')}</aside></div>`;
}
function prepare() {
  return `${breadcrumb('备课工作区', 'teacher', '教学首页')}${header('等式性质', '教师教案与学生学习内容，按活动配套组织。', button('preview', '学生预览'))}<div class="grid"><section class="panel span-7"><div class="panel-head"><h2>教师教案</h2><span class="status">草稿 · 演示</span></div><label for="lesson-goal">本课目标</label><input id="lesson-goal" style="width:100%" value="理解并应用等式两边的共同变化"><label for="student-base">学生基础</label><input id="student-base" style="width:100%" value="已理解相等关系，容易机械使用移项变号"><div class="activity"><label for="plan-editor">活动一 · 观察与追问</label><textarea id="plan-editor">${escapeText(state.plan)}</textarea><div class="actions">${button('regenerate', '重新生成这一环节')}${link('case-detail', '查看参考案例')}</div></div><div class="activity"><h3>活动二 · 表达与应用</h3><p class="muted">把观察写成等式，说明两边进行了什么运算，再尝试独立新题。</p></div><div class="actions">${button('save-plan', '保存教案', true)}${button('publish-dialog', '发布给班级')}</div><div id="plan-feedback"></div></section><aside class="panel tonal span-5"><div class="panel-head"><h2>对应学生内容</h2><span class="muted">活动一</span></div><div class="paper"><h3>两边一起变化</h3><p id="student-plan">${escapeText(state.plan)}</p>${balance()}<p>预测一下：两边同时增加 1，天平还会平衡吗？</p></div><div class="actions">${button('preview', '打开完整预览')}</div><hr class="rule"><p class="source">来源关联：从天平上的变化，走向等式的性质。当前生成与发布为模拟操作。</p></aside></div>`;
}
function classroom() {
  return `${breadcrumb('七年级一班', 'teacher', '教学首页')}${header('七年级一班', '演示班级 · 用一堂课连接备课与学习', button('invite', '邀请学生'))}<div class="grid"><section class="panel span-8"><div class="panel-head"><h2>等式性质 · 班级任务</h2><span class="status">${state.published ? '已模拟发布' : '示例任务'}</span></div><p class="muted">观察天平、解释变化、完成练习与独立检查。</p><div class="counts"><div><strong>${students.length}</strong><small>演示成员</small></div><div><strong>${students.filter(s => s.progress === '已提交').length}</strong><small>示例已提交</small></div></div><div class="actions">${link('insights', '查看作答与反馈', true)}${link('prepare', '查看教案')}</div></section><aside class="panel tonal span-4"><h2>发布新的学习任务</h2><p>从已经保存的教案开始，预览学生内容，再选择班级发布。</p>${link('prepare', '去备课')}</aside></div>`;
}
function insights() {
  return `${breadcrumb('等式性质 · 学情反馈', 'class', '七年级一班')}${header('看见作答，也看见思考过程', '七年级一班 · 以下学情为演示数据', button('supplement', '安排补充学习'))}<section class="panel"><div class="counts"><div><strong>${students.length}</strong><small>演示学生</small></div><div><strong>${students.filter(s => s.progress === '已提交').length}</strong><small>已提交</small></div><div><strong>${students.filter(s => s.result === '新题独立完成').length}</strong><small>新题独立完成</small></div></div><div class="table-scroll"><table><thead><tr><th>学生</th><th>学习进度</th><th>获得的帮助</th><th>独立检查</th><th>操作</th></tr></thead><tbody>${students.map((s, index) => `<tr><td>${s.name}</td><td>${s.progress}</td><td>${s.help}</td><td>${s.result}</td><td><button data-action="student-detail" data-student="${index}">查看过程</button></td></tr>`).join('')}</tbody></table></div></section><div class="grid" style="margin-top:20px"><section class="panel span-7"><h2>共同困难 · 演示观察</h2><p>学生能记住“移项变号”，但解释两边怎样同时变化时仍需要提示。</p><blockquote>建议回到“两边同时减去同一个数”的完整步骤，再安排一道新题。</blockquote>${link('cases', '查找相关教学案例')}</section><section class="panel tonal span-5"><label for="teacher-feedback">给学生的反馈</label><textarea id="teacher-feedback">${escapeText(state.feedback)}</textarea><div class="actions">${button('save-feedback', '确认并保存反馈', true)}</div></section></div>`;
}
function manage() {
  return `${breadcrumb('内容核对', 'manage', '内容管理')}${header('让每一份经验，有据可查', '资料与案例 · 等式性质 · 团队编写示例', button('publish-case', state.casePublished ? '查看发布结果' : '核对并发布', true))}<div class="grid"><section class="panel span-6"><div class="panel-head"><h2>材料与来源</h2><span class="status pending">待补真实来源</span></div><label for="source-name">材料名称</label><input id="source-name" style="width:100%" value="等式性质教学活动 · 团队编写示例"><label for="source-url">公开材料出处</label><input id="source-url" style="width:100%" placeholder="内容建设时填写真实来源链接"><hr class="rule"><div class="paper"><h3>示例教学片段</h3><p>展示相等的两边，让学生预测两边同时加入相同数量后的变化。通过实际操作，引导学生解释为什么相等关系保持。</p><p>再讨论只改变一边的情况，比较两种操作的不同结果。</p></div><p class="source">此处为原型自编材料。真实资料将提供原文定位、作者与使用条件。</p></section><section class="panel span-6"><h2>教学经验整理</h2><label for="case-goal">教学目标</label><input id="case-goal" style="width:100%" value="理解等式两边共同变化的条件"><label for="case-content">引导方式与回应后的调整</label><textarea id="case-content">先预测，再操作，最后用等式表达。学生只说移项变号时，请其写出两边同时减去相同数的过程。</textarea><div class="row"><span>数学核对</span><span class="status">示例等式人工核对</span></div><div class="row"><span>来源核对</span><span class="status pending">自编示例，待正式整理</span></div><div class="actions">${button('save-case', '保存草稿')}${button('publish-case', '模拟发布案例', true)}</div><p class="source">模拟发布只更新本地原型状态。</p></section></div>`;
}
function records() {
  return `${breadcrumb('学习记录')}${header('回看自己的学习过程', '原作答、帮助与后来的尝试，按课时放在一起。')}
    <section class="panel"><h2>等式性质</h2>${state.answers.length ? state.answers.map((a, i) => `<div class="row"><div><p>第 ${i + 1} 次检查 · ${escapeText(a.value)}</p><small>${a.helped ? '获得帮助' : '独立作答'} · ${a.correct ? '答案正确' : '需要再练习'}</small><p class="muted">${escapeText(a.reason || '未填写解释')}</p></div>${link('check', '再尝试')}</div>`).join('') : '<div class="empty">还没有检查记录。完成一道新题后，可以在这里回看。</div>'}<div class="actions">${link('learn', '继续学习', true)}${link('repair', '复习错题')}</div></section>`;
}
function courses() {
  return `${breadcrumb('课程')}${header('从一课开始，连接一个单元', '七年级数学 · 一元一次方程')}<section class="panel"><h2>一元一次方程</h2><div class="row"><div><p>等式性质</p><small>观察天平 · 解释共同变化 · 独立检查</small></div>${link('learn', '开始学习', true)}</div><div class="row"><div><p>解简单的一元一次方程</p><small>后续课时 · 内容待建设</small></div><span class="muted">待开放</span></div><div class="row"><div><p>方程的应用</p><small>后续课时 · 内容待建设</small></div><span class="muted">待开放</span></div></section>`;
}
function teacherHome() {
  return `${breadcrumb('教学首页', 'teacher', '教师端')}${header('让好的教法，进入下一堂课', '从案例出发，准备教学，再看看学生真正理解了什么。', link('prepare', '继续备课', true))}<div class="grid"><section class="panel tonal lesson-focus span-8"><div><div class="course-meta">我的教案 · 草稿</div><h2>等式性质<br>从共同变化中理解相等</h2><p class="muted">教师安排与学生活动配套保存。</p></div><div class="actions">${link('prepare', '打开教案', true)}${link('cases', '寻找教学案例')}</div></section><section class="panel span-4"><h2>班级教学</h2><div class="row"><div><p>七年级一班</p><small>3 名演示学生 · 等式性质</small></div></div><div class="actions">${link('insights', '查看作答与反馈')}</div></section><section class="panel span-12"><div class="panel-head"><h2>可借鉴的教学经验</h2><a href="#cases" class="detail-link">浏览案例</a></div><p class="case-title">从天平上的变化，走向等式的性质</p><p class="muted">针对只改变等式一边、机械记忆移项变号的困难，设计观察与追问。</p></section></div>`;
}
function issues() {
  return `${breadcrumb('反馈与运行', 'manage', '管理首页')}${header('把问题带回对应内容', '原型演示 · 内容反馈与任务状态')}<section class="panel"><h2>待处理内容反馈</h2><div class="row"><div><p>学生反馈：只改变一边时，为什么不相等？</p><small>等式性质 · 活动一 · 演示反馈</small></div>${button('resolve', '查看并处理')}</div><h2 style="margin-top:25px">生成任务</h2><div class="row"><div><p>教案配套内容生成</p><small>原型模拟失败状态</small></div>${button('retry', '重试任务')}</div></section>`;
}
const views = { home, learn: learning, check, result, wrong, repair, cases, 'case-detail': caseDetail, prepare, class: classroom, insights, manage, records, courses, teacher: teacherHome, content: courses, issues };
function render() {
  const route = location.hash.slice(1) || 'home';
  if (['teacher', 'cases', 'case-detail', 'prepare', 'class', 'insights'].includes(route)) role = 'teacher';
  else if (['manage', 'content', 'issues'].includes(route)) role = 'admin';
  else role = 'student';
  document.querySelector('#role').value = role;
  document.querySelector('#navigation').innerHTML = routes[role].map(([path, label]) => `<a href="#${path}" class="${path === route ? 'active' : ''}" ${path === route ? 'aria-current="page"' : ''}>${label}</a>`).join('');
  main.innerHTML = (views[route] || home)();
  document.title = `${main.querySelector('h1')?.textContent || '师承智学'} · ${roleNames[role]}`;
  document.querySelector('#sidebar').classList.remove('open');
  document.querySelector('#menu').setAttribute('aria-expanded', 'false');
  window.scrollTo(0, 0);
  if (route === 'learn' && state.observation) document.querySelector('#observation').value = state.observation;
}
function openDialog(content) {
  document.querySelector('#dialog-content').innerHTML = content;
  dialog.showModal();
}
function preservePlan() {
  const editor = document.querySelector('#plan-editor');
  if (editor) state.plan = editor.value;
  return save();
}
const actions = {
  'add-weight'() { state.balance += 1; save(); document.querySelector('.balance').outerHTML = balance(); },
  'reset-weight'() { state.balance = 0; save(); document.querySelector('.balance').outerHTML = balance(); },
  'save-observation'() { state.observation = document.querySelector('#observation').value; if (save()) toast('解释已保存到本地演示记录'); },
  example() { document.querySelector('#learning-help').innerHTML = '<div class="note">例如 5 = 5，两边都加 2，得到 7 = 7。试着在天平上同时加 1，解释相等关系。</div>'; },
  explain() { document.querySelector('#learning-help').innerHTML = '<div class="note">把左右两边看作同样多的两组物品。如果只给其中一组增加物品，它们就不再同样多。</div>'; },
  ask() { const value = document.querySelector('#question').value.trim(); if (!value) return toast('先输入你的问题'); document.querySelector('#learning-help').innerHTML = `<div class="note"><strong>演示回应</strong><p>你问的是“${escapeText(value)}”。我们先比较两边的变化，再解释它们是否保持相等。也可以试着操作天平观察。</p></div>`; },
  hint() { state.helped = true; save(); document.querySelector('#check-feedback').innerHTML = `<div class="note">${questions[state.questionIndex].hint}<p>本题已记录帮助，理解后可以换新题检查。</p></div>`; document.querySelector('.status').textContent = '本题已获得帮助'; document.querySelector('.status').classList.add('pending'); },
  'new-question'() { const next = state.questionIndex + 1; if (next >= questions.length) return toast('两道演示题已展示，可以保存结果或回到本课复习'); state.questionIndex = next; state.helped = false; save(); render(); },
  'submit-answer'() { const value = document.querySelector('#answer').value.trim(); if (!value) return toast('请先填写结果'); const correct = value === questions[state.questionIndex].answer; state.answers.push({ value, reason: document.querySelector('#reason').value, helped: state.helped, correct, questionIndex: state.questionIndex }); save(); document.querySelector('#check-feedback').innerHTML = `<div class="note">${correct ? '数值正确。请结合你的解释回看两边进行了什么运算。' : '再想一想：等式两边进行了相同的运算吗？可以请求提示。'}<p>${state.helped ? '本次获得过帮助，下一题可再尝试独立完成。' : '本次记录为独立作答。解释内容留待教师查看。'}</p>${link('result', '查看本课结果')}</div>`; },
  complete() { state.completed = true; if (save()) { toast('本课结果已模拟提交'); render(); } },
  'repair-submit'() { const value = document.querySelector('#repair-answer').value.trim(); if (!value) return toast('请先填写答案'); state.review = value === '7'; save(); document.querySelector('#repair-feedback').innerHTML = `<div class="note">${state.review ? '答案正确。两边同时减去 2，得到 z = 7。' : '请试着在两边同时减去 2，再计算右边。'}</div>`; },
  upload() { openDialog('<h2>录入一道题</h2><p class="muted">上传与识别修订的交互演示</p><label for="upload-image">原始题图</label><input id="upload-image" type="file" accept="image/*"><label for="manual-question">确认题目文字</label><textarea id="manual-question">x + 3 = 8，求 x。</textarea><p class="source">原型展示本地文件选择与题目确认流程。</p>' + button('confirm-upload', '确认并开始补救', true)); },
  'confirm-upload'() { if (!document.querySelector('#manual-question').value.trim()) return toast('请先填写题目'); dialog.close(); location.hash = 'repair'; toast('已进入演示题目的补救流程'); },
  search() { const query = document.querySelector('#case-search').value.trim(); const match = !query || /等式|天平|变号|改变|一边|基础|理解/.test(query); document.querySelector('#case-results').hidden = !match; if (!match) { openDialog('<h2>暂时没有匹配的演示案例</h2><p>试试“等式”“天平”或“只改变一边”。</p>'); } else toast('找到 1 篇演示案例'); },
  favorite() { toast('案例已加入演示收藏'); },
  'save-plan'() { if (preservePlan()) { document.querySelector('#student-plan').textContent = state.plan; toast('教案与配套内容已保存到本地'); } },
  regenerate() { const editor = document.querySelector('#plan-editor'); const old = editor.value; editor.disabled = true; editor.value = '正在模拟生成教学环节……'; setTimeout(() => { editor.disabled = false; editor.value = '先请学生预测：两边同时加 1，天平还会平衡吗？再进行操作，并要求学生用“同时”和“相同”解释观察结果。'; document.querySelector('#plan-feedback').innerHTML = '<div class="note">模拟生成完成。请编辑并保存，也可以再次调整。</div>'; if (!old.trim()) toast('已补充一个演示教学环节'); }, 600); },
  preview() { preservePlan(); openDialog(`<h2>学生内容预览</h2><p class="muted">等式性质 · 活动一</p><div class="paper"><h3>两边一起变化</h3><p>${escapeText(state.plan)}</p><div class="math">a = b ⇒ a + c = b + c</div><p>写下预测，操作天平，再解释你的观察。</p></div><div class="actions">${button('publish-dialog', '继续发布')}</div>`); },
  'publish-dialog'() { preservePlan(); if (dialog.open) dialog.close(); openDialog('<h2>发布学习任务</h2><p>等式性质 · 教案与学生内容配套发布</p><label for="publish-class">选择班级</label><select id="publish-class"><option>七年级一班 · 演示班级</option></select><label for="due-date">建议完成时间</label><input id="due-date" type="date" value="2026-11-14"><p class="source">发布为本地模拟，学生首页与班级页将显示发布状态。</p><div class="actions">' + button('confirm-publish', '确认模拟发布', true) + '</div>'); },
  'confirm-publish'() { state.published = true; save(); dialog.close(); location.hash = 'class'; toast('已模拟发布给七年级一班'); },
  invite() { openDialog('<h2>邀请学生加入</h2><p>演示班级口令</p><div class="math">SCZX-DEMO</div><p class="muted">用于原型展示，正式班级邀请在业务开发阶段接入。</p>'); },
  supplement() { openDialog('<h2>安排补充学习</h2><p>给七年级一班补充“等式两边同时减去同一个数”的讲解和新题。</p><div class="actions">' + button('confirm-supplement', '确认模拟安排', true) + '</div>'); },
  'confirm-supplement'() { dialog.close(); toast('已模拟安排补充学习'); },
  'student-detail'(target) { const student = students[Number(target.dataset.student)]; if (student.name !== '林同学') return openDialog(`<h2>${student.name} · 演示学习状态</h2><p>${student.progress}</p><p>获得帮助：${student.help}</p><p>独立检查：${student.result}</p>`); openDialog('<h2>学生学习过程 · 演示</h2><div class="row"><div><p>原作答</p><div class="math">x + 3 = 8 → x = 8 + 3</div></div></div><div class="row"><p>获得提示：两边同时减去 3</p></div><div class="row"><p>新题 y + 4 = 11，回答 y = 7，独立完成</p></div><p class="source">这是演示过程，来自预设案例。</p>'); },
  'save-feedback'() { state.feedback = document.querySelector('#teacher-feedback').value; if (save()) toast('反馈已保存，学生端可查看'); },
  'save-case'() { toast('已模拟保存案例草稿'); },
  'publish-case'() { state.casePublished = true; save(); toast('案例已模拟发布，可在教师端查看示例'); },
  resolve() { openDialog('<h2>处理内容反馈</h2><p>等式性质 · 活动一</p><label for="resolve-text">回复学生</label><textarea id="resolve-text">我们会补充“只改变一边”的对比示例，帮助你观察相等关系的变化。</textarea><div class="actions">' + button('resolve-confirm', '保存处理结果', true) + '</div>'); },
  'resolve-confirm'() { dialog.close(); toast('反馈已模拟处理'); },
  retry() { toast('正在模拟重试'); setTimeout(() => toast('演示任务重试完成'), 700); }
};
document.addEventListener('click', event => {
  const target = event.target.closest('[data-action]');
  if (target) actions[target.dataset.action]?.(target);
});
document.querySelector('#role').addEventListener('change', event => {
  const homes = { student: 'home', teacher: 'teacher', admin: 'manage' };
  location.hash = homes[event.target.value];
});
document.querySelector('#menu').addEventListener('click', () => {
  const open = document.querySelector('#sidebar').classList.toggle('open');
  document.querySelector('#menu').setAttribute('aria-expanded', String(open));
});
document.querySelector('#reset').addEventListener('click', () => {
  state = { ...initialState, answers: [] };
  save();
  render();
  toast('本地演示进度已重置');
});
document.addEventListener('change', event => {
  if (event.target.id === 'question-image') document.querySelector('#image-name').textContent = event.target.files[0]?.name || '尚未选择';
});
window.addEventListener('hashchange', render);
render();
