import {api} from './api.js';
const send=(path,body,method='POST')=>api.request('/ai/agent/'+path,{method,...(body===undefined?{}:{body:JSON.stringify(body)})});
export const planningApi={
 save:(id,plan)=>send(id+'/draft',plan,'PUT'),
 currentDraft:lessonId=>api.request('/ai/agent/draft-state?lessonId='+encodeURIComponent(lessonId)),
 confirm:(id,hash)=>send(id+'/confirm',{expectedDraftHash:hash,confirmed:true}),
 cancel:id=>send(id+'/cancel'),
};
