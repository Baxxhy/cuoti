import {api} from './api.js';
const send=(url,body,method='POST')=>api.request('/curriculum'+url,{method,body:body===undefined?undefined:JSON.stringify(body)});
export const curriculumApi={
 catalog:()=>api.request('/curriculum/courses'),knowledge:()=>api.request('/curriculum/knowledge'),
 lesson:(id,versionId)=>api.request('/curriculum/lessons/'+encodeURIComponent(id)+(versionId?'?versionId='+encodeURIComponent(versionId):'')),
 createCourse:body=>send('/courses',body),saveCourse:(id,body)=>send('/courses/'+id,body,'PUT'),
 createUnit:body=>send('/units',body),saveUnit:(id,body)=>send('/units/'+id,body,'PUT'),
 createLesson:body=>send('/lessons',body),saveLesson:(id,body)=>send('/lessons/'+id,body,'PUT'),
 action:(id,action)=>send('/lessons/'+id+'/'+action),saveKnowledge:points=>send('/knowledge',{points},'PUT'),
 hint:(task,index)=>send('/tasks/'+task+'/questions/'+index+'/hint'),
};
