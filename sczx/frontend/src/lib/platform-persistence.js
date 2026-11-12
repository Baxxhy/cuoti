// Only these fields are edited through the aggregate draft endpoint. Attempts,
// feedback, accounts and other business records have their own write methods.
const draftFields=['caseId','caseSnapshot','lessonSnapshot','goal','studentBase','dueDate','blocks','questions','planningDetails'];
export function platformDraft(data,role){
 if(role==='admin')return {};
 if(role==='teacher'){
  const draft=data.lessonDraft||{},lessonId=draft.lessonId||data.lesson?.id;
  if(!lessonId)return {};
  return {lesson:{id:lessonId},lessonDraft:{lessonId,revision:draft.revision||0,...Object.fromEntries(draftFields.filter(k=>draft[k]!==undefined).map(k=>[k,draft[k]]))}};
 }
 if(role==='student')return {records:Object.fromEntries(Object.entries(data.records||{}).filter(([id,r])=>!r.completed&&!r.readOnly&&!data.tasks?.find(t=>t.id===id)?.readOnly).map(([id,r])=>[id,{id:r.id,observation:r.observation||'',drafts:r.drafts||{}}]))};
 return data; // Isolated component fixtures may not have an authenticated role.
}
export function platformDraftSignature(data,role){
 const value=platformDraft(data,role);
 if(role==='teacher'&&value.lessonDraft){const {revision,...draft}=value.lessonDraft;return JSON.stringify({...value,lessonDraft:draft})}
 return JSON.stringify(value);
}
