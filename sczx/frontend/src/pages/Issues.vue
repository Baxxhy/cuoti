<script setup>
import {ref,computed,onMounted,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {useLearning} from '@/store.js';
import {supportApi} from '@/services/insights.js';
import {api} from '@/services/api.js';
import AccountManager from '@/components/AccountManager.vue';
import LegacyImport from '@/components/LegacyImport.vue';
import FailedJobs from '@/components/FailedJobs.vue';
import ModelConsole from '@/components/ModelConsole.vue';
const route=useRoute(),router=useRouter();
const store=useLearning(),items=ref([]),selected=ref(null),loading=ref(false),error=ref(''),busy=ref(false),status=ref(''),query=ref(''),reply=ref(''),next=ref('replied'),createOpen=ref(false),text=ref(''),category=ref('learning'),taskId=ref(store.task?.id||''),key=ref(crypto.randomUUID()),editKey=ref(''),healthText=ref(''),section=ref('queue'),historyOpen=ref(false);
const validSections=['queue','models','accounts'];
const sectionKey='sczx:operations-section:'+store.user.id;
function sectionFromRoute(){
 if(store.user.role!=='admin')return 'queue';
 if(validSections.includes(route.query.section))return route.query.section;
 try{const saved=sessionStorage.getItem(sectionKey);return validSections.includes(saved)?saved:'queue'}catch{return 'queue'}
}
section.value=sectionFromRoute();
watch(()=>route.query.section,()=>{section.value=sectionFromRoute();historyOpen.value=false});
function changeSection(value){if(!validSections.includes(value))return;section.value=value;try{sessionStorage.setItem(sectionKey,value)}catch{}historyOpen.value=false;router.replace({query:{...route.query,section:value}})}
const conversation=computed(()=>(selected.value?.history||[]).filter((entry,index)=>entry.content&&!(index===0&&entry.content===selected.value?.text&&!entry.oldStatus)));let generation=0;
const states=[{value:'',label:'全部状态'},{value:'pending',label:'待处理'},{value:'processing',label:'处理中'},{value:'replied',label:'已回复'},{value:'closed',label:'已关闭'}];
const visible=computed(()=>items.value.filter(i=>(!status.value||i.status===status.value)&&(!query.value||i.text.includes(query.value))));
async function load(){const g=++generation;loading.value=true;error.value='';try{const rows=await supportApi.list();if(g===generation){items.value=rows;if(selected.value)selected.value=rows.find(i=>i.id===selected.value.id)||null}}catch(e){if(g===generation)error.value=e.message}finally{if(g===generation)loading.value=false}}
function choose(i){selected.value=i;reply.value='';editKey.value=crypto.randomUUID();next.value=store.user.role==='student'?'pending':'replied'}
async function create(){if(busy.value)return;busy.value=true;try{const i=await supportApi.create({text:text.value,category:category.value,taskId:category.value==='learning'?taskId.value:null,requestKey:key.value});createOpen.value=false;text.value='';key.value=crypto.randomUUID();await load();choose(i)}catch(e){error.value=e.message}finally{busy.value=false}}
async function save(){if(busy.value)return;busy.value=true;try{const i=await supportApi.update(selected.value.id,{status:next.value,content:reply.value,expectedRevision:selected.value.revision,requestKey:editKey.value});await load();choose(i)}catch(e){error.value=e.message}finally{busy.value=false}}
async function health(){try{await api.request('/health');healthText.value='服务与数据库已连接'}catch(e){healthText.value=e.message}}
onMounted(()=>{load();if(store.user.role==='admin')health()});
</script>
<template><PageHeading :title="store.user.role==='admin'?'管理与运行':'帮助与反馈'"><Button v-if="section==='queue'" @click="createOpen=true">提交问题</Button></PageHeading>
<AppTabs v-if="store.user.role==='admin'" :model-value="section" @update:model-value="changeSection" :items="[{value:'queue',label:'问题反馈'},{value:'models',label:'能力验证'},{value:'accounts',label:'账号'}]"/>
<template v-if="section==='queue'"><div class="analytics-toolbar"><Input v-model="query" aria-label="搜索问题" placeholder="搜索问题"/><AppSelect :model-value="status||'all'" @update:model-value="status=$event==='all'?'':$event" label="问题状态筛选" :options="states.map(s=>({...s,value:s.value||'all'}))"/><Button variant="outline" @click="load">刷新</Button></div><p v-if="loading" role="status">读取问题…</p><p v-if="error" class="form-error" role="alert">{{error}} <Button variant="outline" @click="load">重新读取</Button></p>
<div class="issue-workspace admin-issue-workspace" :class="{'has-selection':selected}"><Surface class="issue-list"><button v-for="i in visible" :key="i.id" @click="choose(i)" :class="{active:selected?.id===i.id}"><Status>{{i.statusLabel}}</Status><h3>{{i.text}}</h3><small>{{i.ownerName}} · {{i.taskTitle||({learning:'历史学习问题',system:'系统反馈',content:'教学内容'})[i.category]}}</small></button><p v-if="!loading&&!visible.length" class="empty-state">{{items.length?'没有匹配的问题':'暂无问题反馈'}}</p></Surface>
<Surface v-if="selected" class="issue-detail"><SectionHeading :title="selected.ownerName+'的问题'"><Button variant="ghost" @click="historyOpen=true">对话记录</Button></SectionHeading><p class="preserve-lines">{{selected.text}}</p><Status>{{selected.statusLabel}}</Status><RouteButton v-if="selected.taskId&&store.user.role==='teacher'" :route="'insights?task='+selected.taskId" secondary>来源任务</RouteButton><div class="issue-history"><p v-if="selected.legacyReply&&!selected.history.some(e=>e.status==='replied'&&e.content===selected.legacyReply)">历史回复：{{selected.legacyReply}}</p><article v-for="h in conversation" :key="h.id"><strong>{{h.actorName}}</strong><time>{{new Date(h.createdAt).toLocaleString('zh-CN')}}</time><p>{{h.content}}</p></article></div><label class="field-label">{{store.user.role==='student'?'补充内容':'处理意见'}}<Textarea v-model="reply"/></label><AppSelect v-model="next" label="处理后状态" :options="states.filter(s=>s.value&&(store.user.role!=='student'||['pending','closed'].includes(s.value)))"/><Button :disabled="busy||(next==='replied'&&!reply.trim())" @click="save">保存处理</Button></Surface></div></template>
<section v-if="section==='models'&&store.user.role==='admin'"><ModelConsole/><details class="ops-disclosure"><summary>失败与重试</summary><FailedJobs/></details></section><details v-if="store.user.role!=='admin'" class="ops-disclosure"><summary>未完成的后台任务</summary><FailedJobs/></details><template v-if="section==='accounts'&&store.user.role==='admin'"><AccountManager/><div class="admin-maintenance"><Button variant="ghost" @click="health">检查连接</Button><span role="status">{{healthText}}</span><Button variant="ghost" @click="historyOpen=true">导入旧记录</Button></div></template>
<AppDialog v-model:open="historyOpen" :title="section==='accounts'?'导入旧记录':'对话记录'"><LegacyImport v-if="section==='accounts'"/><ol v-else-if="selected" class="admin-status-timeline"><li v-for="h in selected.history" :key="h.id"><strong><template v-if="h.oldStatus">{{states.find(s=>s.value===h.oldStatus)?.label||h.oldStatus}} → </template>{{states.find(s=>s.value===h.status)?.label}}</strong><span>{{h.actorName}} · {{new Date(h.createdAt).toLocaleString('zh-CN')}}</span><p v-if="h.content">{{h.content}}</p></li></ol></AppDialog>
<AppDialog v-model:open="createOpen" title="提交问题"><form class="intervention-form" @submit.prevent="create"><label class="field-label">类型<AppSelect v-model="category" label="问题类型" :options="[{value:'learning',label:'学习疑问'},{value:'content',label:'教学内容问题'},{value:'system',label:'系统问题'}]"/></label><label v-if="category==='learning'" class="field-label">来源任务<AppSelect v-model="taskId" label="问题来源任务" :options="store.data.tasks.map(t=>({value:t.id,label:t.title}))"/></label><label class="field-label">问题内容<Textarea v-model="text" required/></label><p v-if="error" class="form-error">{{error}}</p><Button :disabled="busy||!text.trim()">提交</Button></form></AppDialog>
</template>
