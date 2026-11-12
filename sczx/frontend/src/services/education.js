import{ref}from'vue';import{api}from'./api.js';
const catalog=ref({stages:[],subjects:[],responseTypes:[],gradingModes:[]}),error=ref('');let pending;
export function useEducation(){if(!pending)pending=api.request('/curriculum/subjects').then(value=>{if(value?.responseTypes)catalog.value=value;error.value=''}).catch(e=>{error.value=e.message;pending=null});return{catalog,error}}
export function responseType(question={}){return question.responseType||'calculation'}
export function gradingMode(question={}){return question.gradingMode||(['single_choice','multiple_choice','true_false'].includes(responseType(question))?'exact':question.equation?'math':'manual')}
