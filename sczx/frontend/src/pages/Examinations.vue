<script setup>
import { confirmAction } from '@/lib/confirm-action.js';
import QuestionEditor from "@/components/QuestionEditor.vue";
import SubjectFields from "@/components/SubjectFields.vue";
import AnswerInput from "@/components/AnswerInput.vue";
import {useEducation} from "@/services/education.js";
import {examExplanation} from "@/lib/exam-explanation.js";
import{computed,ref,watch,onBeforeUnmount}from'vue';import{useRoute,useRouter}from'vue-router';import{api}from'@/services/api.js';import{useLearning}from'@/store.js';import{Plus,ArrowUp,ArrowDown,Trash2,ClipboardList,Check,FileDown,RefreshCw}from'@/components/app/icons.js';import AppSortable from'@/components/app/Sortable.vue';import{deadlineText}from'@/services/teaching.js';import MathExpression from'@/components/MathExpression.vue';import SpeechConfirm from'@/components/SpeechConfirm.vue';import SpeechReader from'@/components/SpeechReader.vue';
const route=useRoute(),router=useRouter(),store=useLearning(),teacher=computed(()=>store.user?.role==='teacher');const tab=computed(()=>route.path==='/exam-bank'?'bank':route.path==='/exam-papers'?'papers':'exams');
const error=ref(''),busy=ref(false),loading=ref(true),notice=ref(''),bank=ref([]),papers=ref([]),exams=ref([]),units=ref([]),knowledge=ref([]),classes=ref([]),lessons=ref([]),lessonId=ref(''),activePaper=ref(null),exam=ref(null),questionOpen=ref(false),questionEdit=ref(null),question=ref({}),entries=ref([]),paperTitle=ref(''),unitId=ref(''),filters=ref({knowledgeIds:[],count:3,total:30,kind:'',difficulty:''}),missing=ref(''),candidate=ref(null),candidateInput=ref({knowledgeIds:[],kind:'calculation',difficulty:'easy'}),publishOpen=ref(false),room=ref(''),starts=ref(''),ends=ref(''),minutes=ref(30),studentPreview=ref(false),answers=ref({}),activeQuestion=ref(0),selectedSubmission=ref(''),marks=ref({}),countdown=ref('');let generation=0,timer;
const candidateOpen=ref(false),importOpen=ref(false),pickerOpen=ref(false),pickerMode=ref('auto'),paperEditing=ref(false),paperToolsOpen=ref(false),bankSearch=ref(''),bankFilter=ref('all');
const visibleBank=computed(()=>bank.value.filter(q=>(bankFilter.value==='all'||(bankFilter.value==='reviewed')===!!q.reviewed)&&(q.draft.prompt+' '+q.draft.equation).includes(bankSearch.value.trim())));
const paperSaved=computed(()=>!!activePaper.value&&paperTitle.value===activePaper.value.draft.title&&unitId.value===activePaper.value.draft.unitId&&JSON.stringify(entries.value.map(e=>[e.versionId,Number(e.points)]))===JSON.stringify(activePaper.value.draft.entries.map(e=>[e.versionId,Number(e.points)])));
const gradingQuestion=ref(0);
const gradingEntry=computed(()=>exam.value?.paper?.entries?.[gradingQuestion.value]);
watch(selectedSubmission,()=>gradingQuestion.value=0);
async function markNext(){await mark();if(!error.value&&gradingQuestion.value<(exam.value?.paper.entries.length||0)-1)gradingQuestion.value++}
function examPhase(exam) {
 if(exam.resultsAt)return '成绩已发布';
 const now=Date.now(),start=Date.parse(exam.startsAt),end=Date.parse(exam.endsAt);
 if(Number.isFinite(start)&&now<start)return '待开始';
 if(Number.isFinite(end)&&now>=end)return '已结束';
 return Number.isFinite(start)?'进行中':'待开始';
}
const {catalog:education}=useEducation();
const statusLabel=value=>({verified:'已核验正确',inconsistent:'核验不一致',unverified:'需人工核对',succeeded:'已生成',queued:'等待生成',running:'正在生成',failed:'生成失败',cancelled:'已取消'})[value]||'待核对';
const clone=value=>JSON.parse(JSON.stringify(value));
const call=(path,method='GET',body)=>api.request('/exams'+path,{method,...(body?{body:JSON.stringify(body)}:{})});
const current=computed(()=>exam.value?.paper?.entries?.[activeQuestion.value]);const sub=computed(()=>exam.value?.submissions?.find(s=>s.id===selectedSubmission.value));const pending=computed(()=>!!exam.value?.submission&&!exam.value.submission.submittedAt);const bankChoices=computed(()=>bank.value.filter(q=>q.versions.length&&q.versions[0].data.unitId===unitId.value));
async function run(fn){if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await fn()}catch(e){error.value=e.message}finally{busy.value=false}}
async function load(){const g=++generation;loading.value=true;error.value='';try{const result=await Promise.all([call(''),teacher.value?call('/bank'):[],teacher.value?call('/papers'):[],api.request('/curriculum/courses'),api.request('/curriculum/knowledge'),api.request('/teaching/classes')]);if(g!==generation)return;[exams.value,bank.value,papers.value]=result;units.value=result[3].flatMap(c=>c.units.map(u=>({...u,grade:c.grade,subject:c.metadata?.subject||''})));if(!units.value.some(u=>u.id===unitId.value))unitId.value=units.value[0]?.id||'';lessons.value=units.value.flatMap(u=>u.lessons);knowledge.value=result[4];classes.value=result[5];lessonId.value||=(lessons.value[0]?.id||'');room.value||=(classes.value[0]?.id||'');if(route.query.exam){const freshExam=await call('/'+encodeURIComponent(route.query.exam));if(g!==generation)return;exam.value=freshExam;answers.value=clone(exam.value.submission?.answers||{});if(exam.value.submissions?.length&&!selectedSubmission.value)selectedSubmission.value=exam.value.submissions[0].id}else exam.value=null}catch(e){if(g===generation)error.value=e.message}finally{if(g===generation)loading.value=false}}
watch(()=>[route.path,route.query.exam],()=>{selectedSubmission.value='';activeQuestion.value=0;load()},{immediate:true});watch(sub,s=>{marks.value=Object.fromEntries((exam.value?.paper?.entries||[]).map(x=>[x.versionId,{score:s?.grades[x.versionId]?.score??0,comment:s?.grades[x.versionId]?.comment||''}]))});
function editQuestion(row){questionEdit.value=row;question.value=row?Object.fromEntries(Object.entries(row.draft).filter(([k])=>['prompt','equation','answer','explanation','subject','grade','knowledgeIds','unitId','kind','difficulty','points','source','requiresTeacherReview','responseType','gradingMode','options','rubric','acceptedAnswers','caseSensitive'].includes(k))):{prompt:'',equation:'',answer:'',explanation:'',subject:units.value.find(u=>u.id===unitId.value)?.subject||'',grade:units.value.find(u=>u.id===unitId.value)?.grade||'',knowledgeIds:[],responseType:'short_answer',gradingMode:'manual',unitId:unitId.value,kind:'calculation',difficulty:'easy',points:10,source:'教师自编',requiresTeacherReview:false};questionOpen.value=true}
async function saveQuestion(){await run(async()=>{const d={...question.value,points:Number(question.value.points)};await call('/bank'+(questionEdit.value?'/'+questionEdit.value.id:''),questionEdit.value?'PUT':'POST',{data:d,...(questionEdit.value?{revision:questionEdit.value.revision}:{})});questionOpen.value=false;await load();notice.value='题目已保存，等待审核'})}
async function reviewQuestion(row){if(!await confirmAction('确认已核对题干、适用条件、参考答案和解析？将保存固定版本。'))return;await run(async()=>{await call('/bank/'+row.id+'/review','POST',{revision:row.revision,confirmed:true});await load();notice.value='审核版本已保存'})}
async function leavePaper(){if(entries.value.length&&!paperSaved.value&&!await confirmAction('当前试卷修改尚未保存。返回列表将保留当前编辑内容，重新打开其他试卷会替换这些内容。继续？'))return;paperEditing.value=false}
function editPaper(p){paperEditing.value=true;activePaper.value=p;paperTitle.value=p?.draft.title||'单元检查';unitId.value=p?.draft.unitId||units.value[0]?.id||'';entries.value=clone(p?.draft.entries||[])}
function toggle(q,event){const v=q.versions[0];if(event.target.checked)entries.value.push({versionId:v.id,points:v.data.points,question:v.data});else entries.value=entries.value.filter(x=>x.versionId!==v.id)}
function move(i,delta){const target=i+delta;if(target<0||target>=entries.value.length)return;const [x]=entries.value.splice(i,1);entries.value.splice(target,0,x)}
async function assemble(){await run(async()=>{const r=await call('/assemble','POST',{...filters.value,count:Number(filters.value.count),total:Number(filters.value.total),unitId:unitId.value});if(!r.sufficient){missing.value=r.missingKnowledge?'缺少知识点：'+r.missingKnowledge.join('、'):'符合条件 '+r.available+' 题，还缺 '+r.missing+' 题';return}missing.value='';entries.value=r.entries;pickerOpen.value=false;notice.value='试卷题目已添加，请核对顺序与分值'})}
async function savePaper(){await run(async()=>{const p=await call('/papers'+(activePaper.value?'/'+activePaper.value.id:''),activePaper.value?'PUT':'POST',{title:paperTitle.value,unitId:unitId.value,entries:entries.value.map(e=>({versionId:e.versionId,points:Number(e.points)})),...(activePaper.value?{revision:activePaper.value.revision}:{})});await load();editPaper(p);notice.value='试卷草稿已保存'})}
async function reviewPaper(){if(!activePaper.value)return;if(!await confirmAction('确认已核对学生试卷、题目顺序、分值及教师参考解答？'))return;await run(async()=>{const p=await call('/papers/'+activePaper.value.id+'/review','POST',{revision:activePaper.value.revision,confirmed:true});await load();editPaper(p);notice.value='试卷审核完成'})}
async function generateCandidate(){await run(async()=>{candidate.value=await api.request('/ai/jobs',{method:'POST',body:JSON.stringify({capability:'text',requestKey:crypto.randomUUID(),data:{examCandidate:true,unitId:unitId.value,...candidateInput.value}})})})}
async function refreshCandidate(){await run(async()=>{candidate.value=await api.request('/ai/jobs/'+candidate.value.id)})}
async function adopt(){await run(async()=>{await call('/bank/candidate/'+candidate.value.id,'POST',{});candidate.value=null;await load();candidateOpen.value=false;notice.value='已存为待审核题目'})}
// datetime-local has no timezone. Teachers always enter Beijing time, even
// when this browser or the local Linux service runs in another timezone.
const beijingInput=value=>new Date(value+8*3600000).toISOString().slice(0,16);
function publishDialog(){starts.value=beijingInput(Date.now()-60000);ends.value=beijingInput(Date.now()+3600000);publishOpen.value=true}
async function publish(){await run(async()=>{const r=await call('','POST',{versionId:activePaper.value.versions[0].id,classId:room.value,startsAt:new Date(starts.value+':00+08:00').toISOString(),endsAt:new Date(ends.value+':00+08:00').toISOString(),minutes:Number(minutes.value),requestKey:crypto.randomUUID()});publishOpen.value=false;router.push('/exams?exam='+r.id)})}
async function start(){await run(async()=>{exam.value=await call('/'+exam.value.id+'/start','POST',{});answers.value=clone(exam.value.submission.answers||{})})}
async function saveAnswers(submit=false){if(submit&&!await confirmAction('提交后答卷只读，无法继续修改。确认交卷？'))return;await run(async()=>{exam.value=await call('/'+exam.value.id+(submit?'/submit':'/answers'),submit?'POST':'PUT',{revision:exam.value.submission.revision,answers:answers.value});notice.value=submit?'答卷已提交':'草稿已保存'})}
async function nextAnswerQuestion(){if(pending.value)await saveAnswers(false);if(!error.value&&activeQuestion.value<exam.value.paper.entries.length-1)activeQuestion.value++}
function answerModel(){const key=current.value?.versionId;if(key&&!answers.value[key])answers.value[key]={answer:'',reason:''};return key?answers.value[key]:{answer:'',reason:''}}
watch(current,()=>answerModel());
async function mark(){await run(async()=>{const entry=gradingEntry.value,record=sub.value;if(!entry||!record)return;const value=marks.value[entry.versionId];const score=Number(value.score);if(!Number.isInteger(score)||score<0||score>entry.points||!value.comment.trim())throw Error('请填写本题范围内的分数和批阅依据。');const saved=await call('/'+exam.value.id+'/submissions/'+record.id+'/grades','PUT',{revision:record.revision,grades:{[entry.versionId]:{score,comment:value.comment}}});if(sub.value===record)Object.assign(record,saved);notice.value='本题批阅已保存，原答案及程序核验保留'})}
async function release(){if(!await confirmAction('成绩发布后学生将看到答案和讲评，当前版本不能再修改。确认发布？'))return;await run(async()=>{await call('/'+exam.value.id+'/results','POST',{confirmed:true});await load();notice.value='成绩与讲评已发布'})}
function exportFile(mode){const q=selectedSubmission.value?'?submissionId='+encodeURIComponent(selectedSubmission.value):'';window.open('/api/exams/'+exam.value.id+'/export/'+mode+q,'_blank','noopener')}
timer=setInterval(()=>{const s=exam.value?.submission;if(!s?.startedAt||s.submittedAt){countdown.value='';return}const n=Math.max(0,Math.floor((new Date(s.deadline)-Date.now())/1000));countdown.value=Math.floor(n/60)+':'+String(n%60).padStart(2,'0')},1000);onBeforeUnmount(()=>{clearInterval(timer);generation++});
</script>
<template>
<PageHeading :title="tab==='bank'?'题库':tab==='papers'?'组卷':exam?.title||'考试'">
<AppButton v-if="teacher&&tab==='bank'" @click="editQuestion(null)"><Plus :size="16"/>录入题目</AppButton>
<AppButton v-if="teacher&&tab==='papers'&&!paperEditing" @click="editPaper(null)"><Plus :size="16"/>新建试卷</AppButton>
<AppButton variant="ghost" size="icon" aria-label="刷新考试工作区" :disabled="loading" @click="load"><RefreshCw :size="16"/></AppButton>
</PageHeading>

<AppAlert type="error" v-if="error" class="form-error" role="alert">{{error}}<AppButton variant="ghost" @click="load">重新读取</AppButton></AppAlert>
<AppAlert type="success" v-if="notice" role="status" class="exam-notice">{{notice}}</AppAlert>
<ElSkeleton v-if="loading" animated :rows="3" aria-label="正在读取…"/>
<template v-else-if="tab==='bank'&&teacher">
<div class="teacher-bank-toolbar"><Input v-model="bankSearch" aria-label="搜索题目" placeholder="搜索题目或方程"/><AppSelect v-model="bankFilter" label="题目状态" :options="[{value:'all',label:'全部题目'},{value:'reviewed',label:'已审核'},{value:'pending',label:'待审核'}]"/><AppButton variant="outline" @click="importOpen=true">引用课程题目</AppButton><AppButton variant="outline" @click="candidateOpen=true">AI 出题</AppButton></div>
<div class="exam-bank-grid teacher-bank-single">
<Surface class="exam-bank-main">
<AppEmpty v-if="!bank.length" class="empty-state"><ClipboardList/><h3>还没有题目</h3><AppButton @click="editQuestion(null)">录入第一题</AppButton></AppEmpty>
<Surface data-ui="card" role="article" v-for="q in visibleBank" :key="q.id" class="exam-bank-row">
<div>
<Status>{{q.reviewed?'已审核 v'+q.versions[0]?.number:'待审核'}}</Status>
<h3>{{q.draft.prompt}}</h3>
<div class="exam-math"><MathExpression :text="q.draft.equation"/></div>
<span>{{q.draft.kind==='application'?'应用':q.draft.kind==='explanation'?'解释':'计算'}} 　 {{q.draft.points}}分 　 {{q.draft.source}}</span>
</div>
<div class="exam-toolbar">
<AppButton variant="ghost" @click="editQuestion(q)">编辑</AppButton>
<AppButton variant="outline" :disabled="busy||q.reviewed" @click="reviewQuestion(q)">核对并审核</AppButton>
</div>
<AppDisclosure>
<template #title>参考解答与版本</template>
<p>{{q.draft.answer}} 　 {{examExplanation(q.draft)}}</p>
<p>方程核验：{{statusLabel(q.draft.referenceVerification?.status)}}</p>
<p v-for="v in q.versions" :key="v.id">v{{v.number}} 　 {{v.data.prompt}} 　 {{v.data.answer}} 　 {{v.id}}</p>
</AppDisclosure>
</Surface><AppEmpty v-if="bank.length&&!visibleBank.length" class="empty-state"><h3>没有匹配的题目</h3><AppButton variant="outline" @click="bankSearch='';bankFilter='all'">清空筛选</AppButton></AppEmpty>
</Surface>
</div>
</template>
<template v-else-if="tab==='papers'&&teacher">
<Surface data-ui="card" v-if="!paperEditing" class="teacher-paper-list"><AppButton variant="ghost" data-layout="row" type="button" v-for="p in papers" :key="p.id" class="teacher-paper-row" @click="editPaper(p)"><FileDown :size="21"/><span><strong>{{ p.draft.title }}</strong><small>{{ p.draft.entries.length }} 题 　 {{ p.draft.total }} 分</small></span><Status>{{ p.reviewed?'已审核':'草稿' }}</Status><span>打开试卷</span></AppButton><AppEmpty v-if="!papers.length" class="empty-state"><ClipboardList :size="28"/><h3>还没有试卷</h3><AppButton @click="editPaper(null)">新建第一份试卷</AppButton></AppEmpty></Surface>
<div v-else class="teacher-paper-editor"><div class="teacher-paper-editor-bar"><AppButton variant="ghost" @click="leavePaper">返回试卷列表</AppButton><span>{{ activePaper?.reviewed&&paperSaved?'已审核':paperSaved?'已保存':'编辑中' }}</span></div><ol class="teacher-paper-steps" aria-label="组卷流程"><li :class="{current:!entries.length}">1 选择题目</li><li :class="{current:entries.length&&!activePaper?.reviewed}">2 核对并保存</li><li :class="{current:activePaper?.reviewed&&paperSaved}">3 发布考试</li></ol>
<Surface>
<div class="exam-form-grid">
<label>试卷名称<Input v-model="paperTitle"/>
</label>
<label>单元<NativeSelect v-model="unitId" @change="entries=[]">
<option v-for="u in units" :key="u.id" :value="u.id">{{u.title}}</option>
</NativeSelect>
</label>
</div>
<Surface data-ui="card" class="teacher-paper-title"><h2>试卷题目</h2><AppButton variant="outline" @click="pickerOpen=true"><Plus :size="16"/>添加题目</AppButton></Surface>
<AppSortable v-model="entries" item-key="versionId" handle=".exam-drag" class="exam-paper-entries">
<template #item="{element:e,index:i}">
<Surface data-ui="card" role="article">
<AppButton variant="ghost" data-layout="row" type="button" class="exam-drag" :aria-label="'拖动第'+(i+1)+'题'">{{String(i+1).padStart(2,'0')}}</AppButton>
<div>
<h3>{{e.question.prompt}}</h3>
<div class="exam-math"><MathExpression :text="e.question.equation"/></div>
<label>分值<Input v-model="e.points" type="number" min="1" max="100"/>
</label>
</div>
<div class="exam-entry-tools">
<AppButton variant="ghost" size="icon" :disabled="!i" :aria-label="'上移第'+(i+1)+'题'" @click="move(i,-1)">
<ArrowUp :size="16"/>
</AppButton>
<AppButton variant="ghost" size="icon" :disabled="i===entries.length-1" :aria-label="'下移第'+(i+1)+'题'" @click="move(i,1)">
<ArrowDown :size="16"/>
</AppButton>
<AppButton variant="ghost" size="icon" :aria-label="'删除第'+(i+1)+'题'" @click="entries.splice(i,1)">
<Trash2 :size="16"/>
</AppButton>
</div>
</Surface>
</template>
</AppSortable>
<AppEmpty v-if="!entries.length" class="empty-state"><ClipboardList :size="28"/><h3>还没有题目</h3><AppButton @click="pickerOpen=true">添加题目</AppButton></AppEmpty>
<footer class="exam-toolbar">
<strong>{{entries.length}}题 　 {{entries.reduce((n,e)=>n+Number(e.points),0)}}分</strong>
<AppButton :variant="activePaper?.reviewed&&paperSaved?'outline':'default'" :disabled="busy||!entries.length" @click="savePaper">保存试卷</AppButton>
<AppButton variant="outline" :disabled="!entries.length" @click="studentPreview=true">学生预览</AppButton>
<AppButton variant="outline" :disabled="busy||!paperSaved||activePaper.reviewed" @click="reviewPaper">核对并审核</AppButton>
<AppButton :disabled="busy||!activePaper?.reviewed||!paperSaved" @click="publishDialog">发布考试</AppButton>
</footer>
</Surface>
</div>
</template>
<template v-else>
<template v-if="!exam">
<div class="exam-list">
<Surface v-for="e in exams" :key="e.id">
<div class="exam-list-row">
<div>
<Status>{{examPhase(e)}}</Status>
<h2>{{e.title}}</h2>
<p>{{deadlineText(e.startsAt)}} — {{deadlineText(e.endsAt)}} 　 {{e.minutes}}分钟</p>
</div>
<RouteButton :route="'exams?exam='+e.id">{{teacher?'查看答卷':'进入考试'}}</RouteButton>
</div>
</Surface>
<AppEmpty v-if="!exams.length" class="empty-state"><ClipboardList/><h3>{{teacher?'尚未发布考试':'暂无已分配考试'}}</h3><RouteButton v-if="teacher" route="exam-papers">创建试卷</RouteButton></AppEmpty>
</div>
</template>
<template v-else>
<ElSpace wrap :size="12" class="exam-heading">
<div>
<Status>{{exam.resultsAt?'成绩已发布':!teacher&&exam.submission?.submittedAt?'已交卷':examPhase(exam)==='已结束'?(teacher?'成绩待发布':'已结束'):examPhase(exam)==='待开始'?'待开始':exam.submission?.startedAt?'考试中':'进行中'}}</Status>
<p>{{deadlineText(exam.startsAt)}} — {{deadlineText(exam.endsAt)}} 　 {{exam.minutes}}分钟</p>
</div>
<RouteButton route="exams" secondary :aria-current="tab==='exams'?'page':undefined">考试列表</RouteButton>
</ElSpace>
<template v-if="teacher">
<div class="teacher-grading-toolbar"><span>{{ exam.submissions.filter(s=>s.submittedAt).length }} / {{ exam.submissions.length }} 人已交卷</span><AppButton variant="outline" @click="paperToolsOpen=true"><FileDown :size="16"/>导出</AppButton><AppButton :disabled="busy||!!exam.resultsAt" @click="release">发布成绩</AppButton></div>
<div class="exam-grading">
<Surface>
<h2>答卷</h2>
<AppButton variant="ghost" data-layout="row" type="button" v-for="s in exam.submissions" :key="s.id" class="exam-paper-link" :class="{'is-active':s.id===selectedSubmission}" @click="selectedSubmission=s.id">
<strong>{{s.studentName}}</strong>
<span>{{s.submittedAt?'已交卷':'未交卷'}} 　 {{s.total}}分 　 {{Object.keys(s.grades).length}} / {{exam.paper.entries.length}} 已核对</span>
</AppButton>
</Surface>
<Surface v-if="sub">
<div class="exam-toolbar">
<h2>{{sub.studentName}}</h2>
<AppButton variant="ghost" :disabled="!sub.submittedAt" @click="exportFile('submission')">导出答卷</AppButton>
<AppButton variant="ghost" :disabled="!sub.submittedAt" @click="exportFile('learning')">学习记录</AppButton>
</div>
<ElSpace wrap :size="12" class="focus-grading-nav" aria-label="批阅题目"><AppButton :variant="(gradingQuestion===i)?'selected':'ghost'" data-layout="row" type="button" v-for="(entry,i) in exam.paper.entries" :key="entry.versionId" :aria-label="'批阅第'+(i+1)+'题'" :aria-current="gradingQuestion===i?'step':undefined" :class="{active:gradingQuestion===i}" @click="gradingQuestion=i">{{i+1}}<Check v-if="sub.grades[entry.versionId]" :size="12"/></AppButton></ElSpace>
<Surface data-ui="card" role="article" v-for="e in gradingEntry?[gradingEntry]:[]" :key="e.versionId" class="exam-grade-question">
<h3>{{gradingQuestion+1}}. {{e.question.prompt}}（{{e.points}}分）</h3>
<div class="exam-math"><MathExpression :text="e.question.equation"/></div>
<Surface data-ui="card" class="exam-original">
<p>原答：{{sub.answers[e.versionId]?.answer||'未填写'}}</p>
<p>解释：{{sub.answers[e.versionId]?.reason||'未填写'}}</p>
</Surface>
<Status>{{statusLabel(sub.automatic[e.versionId]?.status)}}</Status>
<AppDisclosure class="teacher-grade-reference"><template #title>参考解答</template><p>{{e.question.answer}}</p><p>{{examExplanation(e.question)}}</p></AppDisclosure>
<div class="exam-form-grid">
<label>得分<Input v-if="marks[e.versionId]" v-model="marks[e.versionId].score" type="number" min="0" :max="e.points" :readonly="!!exam.resultsAt"/>
</label>
<label>批阅与讲评<Textarea v-if="marks[e.versionId]" v-model="marks[e.versionId].comment" :readonly="!!exam.resultsAt"/>
</label>
</div>
</Surface>
<div class="focus-grading-actions"><AppButton variant="outline" :disabled="!gradingQuestion" @click="gradingQuestion--">上一题</AppButton><AppButton :disabled="busy||!sub.submittedAt||!!exam.resultsAt" @click="markNext">{{gradingQuestion<exam.paper.entries.length-1?'保存并下一题':'保存批阅'}}</AppButton><AppButton v-if="exam.resultsAt&&gradingQuestion<exam.paper.entries.length-1" variant="outline" @click="gradingQuestion++">下一题</AppButton></div>
<AppDisclosure class="teacher-grade-audit">
<template #title>批阅记录 　 {{sub.audits?.length||0}}</template>
<p v-for="a in sub.audits" :key="a.id">{{new Date(a.at).toLocaleString('zh-CN')}} 　 {{a.actorId}} 　 {{a.id}}</p>
</AppDisclosure>
</Surface>
</div>
</template>
<template v-else>
<Surface v-if="!exam.submission.startedAt">
<h2>准备开始</h2>
<p>开始后按服务器记录计时，提交后答卷只读。</p>
<AppButton :disabled="busy" @click="start">开始考试</AppButton>
</Surface>
<template v-else>
<div class="exam-answer-layout">
<aside class="exam-answer-nav">
<strong>{{exam.submission.submittedAt?'已交卷':countdown}}</strong>
<nav aria-label="试题导航">
<AppButton :variant="(i===activeQuestion)?'selected':'ghost'" data-layout="row" type="button" v-for="(e,i) in exam.paper.entries" :key="e.versionId" :class="{active:i===activeQuestion,answered:answers[e.versionId]?.answer}" :aria-label="'第'+(i+1)+'题'" :aria-current="activeQuestion===i?'step':undefined" @click="activeQuestion=i">{{String(i+1).padStart(2,'0')}}</AppButton>
</nav>
<p v-if="exam.resultsAt">总分 {{exam.submission.total}} / {{exam.paper.total}}</p>
</aside>
<Surface v-if="current" class="exam-answer-paper">
<div class="exam-toolbar">
<Status>第 {{activeQuestion+1}} 题 　 {{current.points}}分</Status>
<SpeechReader :context-key="current.versionId" :text="current.question.prompt+'。'+current.question.equation"/>
</div>
<h2>{{current.question.prompt}}</h2>
<div v-if="current.question.equation" class="exam-math"><MathExpression :text="current.question.equation"/></div>
<label>答案<AnswerInput :question="current.question" :model-value="answerModel().answer" :readonly="!pending" :disabled="busy" @update:model-value="answerModel().answer=$event"/>
</label>
<AppDisclosure v-if="pending" class="focus-exam-voice"><template #title>语音输入</template><SpeechConfirm :context-key="current.versionId" :disabled="busy" @confirmed="answerModel().answer=$event"/></AppDisclosure>
<label>思路与依据<Textarea :model-value="answerModel().reason" :readonly="!pending" :disabled="busy" @update:model-value="answerModel().reason=$event"/>
</label>
<div class="exam-toolbar">
<AppButton v-if="pending" variant="outline" :disabled="busy" @click="saveAnswers(false)">保存草稿</AppButton>
<AppButton v-if="pending" :disabled="busy" :variant="activeQuestion===exam.paper.entries.length-1?'default':'outline'" @click="saveAnswers(true)">确认交卷</AppButton>
<AppButton v-if="activeQuestion<exam.paper.entries.length-1" :disabled="busy" @click="nextAnswerQuestion">下一题</AppButton>
</div>
<template v-if="exam.resultsAt">
<Surface data-ui="card" class="exam-result-grade">
<h3>{{exam.submission.grades[current.versionId]?.score}} / {{current.points}} 分</h3>
<p>{{exam.submission.grades[current.versionId]?.comment}}</p>
<p>参考：{{current.question.answer}}</p>
<p class="preserve-lines">{{examExplanation(current.question)}}</p>
</Surface>
<RouteButton route="wrong" secondary>去订正错题</RouteButton>
<AppButton variant="ghost" @click="exportFile('learning')">导出学习记录</AppButton>
</template>
<p v-else-if="!pending" role="status">答卷已保存，等待教师发布成绩与讲评。</p>
</Surface>
</div>
</template>
</template>
</template>
</template>
<AppDialog v-model:open="candidateOpen" title="AI 出题" content-class="teacher-ai-question-dialog"><AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert><Surface class="exam-candidate">
<h2>生成候选题</h2>
<label>单元<NativeSelect v-model="unitId">
<option v-for="u in units" :key="u.id" :value="u.id">{{u.title}}</option>
</NativeSelect>
</label>
<label>知识点<NativeSelect v-model="candidateInput.knowledgeIds" multiple>
<option v-for="k in knowledge" :value="k.id" :key="k.id">{{k.name}}</option>
</NativeSelect>
</label>
<label>题型<NativeSelect v-model="candidateInput.kind"><option v-for="item in education.responseTypes" :key="item.value" :value="item.value">{{item.label}}</option><option value="application">应用题</option><option value="explanation">解释题</option></NativeSelect>
</label>
<label>难度<NativeSelect v-model="candidateInput.difficulty">
<option value="easy">基础</option>
<option value="medium">进阶</option>
<option value="hard">综合</option>
</NativeSelect>
</label>
<AppButton :disabled="busy" @click="generateCandidate">生成待审核候选</AppButton>
<template v-if="candidate">
<Status>{{statusLabel(candidate.status)}}</Status>
<AppAlert type="error" v-if="candidate.error" role="alert">{{candidate.error}}</AppAlert>
<p>{{candidate.result?.prompt}}</p>
<p>{{candidate.result?.equation}}</p>
<AppButton v-if="candidate.status==='succeeded'" :disabled="busy" @click="adopt">存入待审核题库</AppButton>
<AppButton v-else :disabled="busy" variant="outline" @click="refreshCandidate">读取进度</AppButton>
</template>
</Surface></AppDialog>
<AppDialog v-model:open="importOpen" title="引用课程题目"><AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert><div class="exam-publish"><label class="field-label">来源课时<NativeSelect v-model="lessonId" aria-label="来源课时">
<option v-for="l in lessons" :value="l.id" :key="l.id">{{l.title}}</option>
</NativeSelect></label>
<AppButton variant="outline" :disabled="busy||!lessonId" @click="run(async()=>{await call('/bank/import','POST',{lessonId});await load();importOpen=false;notice='课程题目已存为待审核候选'})">引用课程题目</AppButton>

</div><p class="small-caption">引用后先进入待审核题库，审核后才能用于组卷。</p></AppDialog>
<AppDialog v-model:open="pickerOpen" title="添加题目" content-class="teacher-question-picker-dialog"><AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert><AppTabs v-model="pickerMode" :items="[{value:'auto',label:'按条件组卷'},{value:'bank',label:'从题库选择'}]"/><Surface data-ui="card" v-if="pickerMode==='auto'" class="exam-constraints">
<div class="exam-form-grid">
<label>知识点<NativeSelect multiple v-model="filters.knowledgeIds">
<option v-for="k in knowledge" :key="k.id" :value="k.id">{{k.name}}</option>
</NativeSelect>
</label>
<label>题数<Input v-model="filters.count" type="number" min="1" max="100"/>
</label>
<label>总分<Input v-model="filters.total" type="number" min="1"/>
</label>
<label>题型<NativeSelect v-model="filters.kind"><option value="">全部题型</option><option v-for="item in education.responseTypes" :key="item.value" :value="item.value">{{item.label}}</option><option value="application">应用题</option><option value="explanation">解释题</option></NativeSelect>
</label>
<label>难度<NativeSelect v-model="filters.difficulty">
<option value="">全部</option>
<option value="easy">基础</option>
<option value="medium">进阶</option>
<option value="hard">综合</option>
</NativeSelect>
</label>
</div>
<AppButton variant="outline" :disabled="busy" @click="assemble">生成候选试卷</AppButton>
<p v-if="missing" role="status">{{missing}}<RouteButton route="exam-bank" secondary>补充题库</RouteButton>
</p>
</Surface><section v-else class="exam-question-picker">
<AppCheckbox v-for="q in bankChoices" :key="q.id" :checked="entries.some(e=>e.versionId===q.versions[0].id)" @change="toggle(q,$event)">{{q.versions[0].data.prompt}} 　 {{q.versions[0].data.equation}}</AppCheckbox><p v-if="!bankChoices.length" class="muted">本单元暂无已审核题目。</p><AppButton @click="pickerOpen=false">完成选择 　 {{ entries.length }} 题</AppButton></section>
</AppDialog>
<AppDialog v-model:open="paperToolsOpen" title="导出考试资料"><div class="exam-toolbar">
<AppButton variant="outline" @click="exportFile('student')">
<FileDown :size="16"/>学生版试卷</AppButton>
<AppButton variant="outline" @click="exportFile('teacher')">教师版试卷</AppButton>
<AppButton variant="outline" :disabled="!exam.resultsAt" @click="exportFile('grades')">班级成绩</AppButton>
</div></AppDialog>
<AppDialog v-model:open="questionOpen" title="题目编辑" content-class="exam-question-dialog">
<ElForm @submit.prevent="saveQuestion"><AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert>
<div class="exam-form-grid">
<label>单元<NativeSelect v-model="question.unitId">
<option v-for="u in units" :key="u.id" :value="u.id">{{u.title}}</option>
</NativeSelect>
</label>
<label>知识点<NativeSelect multiple v-model="question.knowledgeIds">
<option v-for="k in knowledge" :key="k.id" :value="k.id">{{k.name}}</option>
</NativeSelect>
</label>
<label>题型<NativeSelect v-model="question.kind"><option v-for="item in education.responseTypes" :key="item.value" :value="item.value">{{item.label}}</option><option value="application">应用题</option><option value="explanation">解释题</option></NativeSelect>
</label>
<label>难度<NativeSelect v-model="question.difficulty">
<option value="easy">基础</option>
<option value="medium">进阶</option>
<option value="hard">综合</option>
</NativeSelect>
</label>
<label>学科<Input v-model="question.subject"/>
</label>
<label>年级<Input v-model="question.grade"/>
</label>
</div>
<label>题干<Textarea v-model="question.prompt" required/>
</label>
<SpeechConfirm context-key="bank-prompt" @confirmed="question.prompt=$event"/>
<SubjectFields v-model:grade="question.grade" v-model:subject="question.subject"/><QuestionEditor :question="question" :subject="question.subject"/>
<div class="exam-form-grid">
<label>分值<Input v-model="question.points" type="number" min="1" max="100"/>
</label>
<label>来源<Input v-model="question.source" required/>
</label>
</div>
<AppCheckbox class="exam-check" v-model="question.requiresTeacherReview">需要人工核对解题过程</AppCheckbox>
<AppButton type="submit" :disabled="busy">保存待审核题目</AppButton>
</ElForm>
</AppDialog>
<AppDialog v-model:open="studentPreview" title="学生试卷预览">
<h2>{{paperTitle}}</h2>
<section v-for="(e,i) in entries" :key="e.versionId" class="exam-grade-question">
<h3>{{i+1}}. {{e.question.prompt}}（{{e.points}}分）</h3>
<p>{{e.question.equation}}</p>
</section>
</AppDialog>
<AppDialog v-model:open="publishOpen" title="发布考试">
<ElForm class="exam-publish" @submit.prevent="publish"><AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert>
<label>班级<NativeSelect v-model="room">
<option v-for="c in classes" :key="c.id" :value="c.id">{{c.name}}</option>
</NativeSelect>
</label>
<label>开始时间（北京时间）<Input v-model="starts" type="datetime-local" required/>
</label>
<label>截止时间（北京时间）<Input v-model="ends" type="datetime-local" required/>
</label>
<label>作答限时（分钟）<Input v-model="minutes" type="number" min="1" max="240"/>
</label>
<p>本次发布固定试卷版本，班级当前学生将收到考试；后续编辑不影响本次试卷。</p>
<AppButton type="submit" :disabled="busy">确认发布考试</AppButton>
</ElForm>
</AppDialog>
</template>
