import {readingValue} from './lesson-reading.js';

// Match the server's required-block rules; the submit endpoint remains authoritative.
export function incompleteBlocks(task,record){
 if(!task?.snapshot?.lessonSnapshot)return [];
 const answered=new Set((record?.attempts||[]).map(a=>task.questions?.[a.question]?.id));
 return (task.snapshot.blocks||[]).filter(b=>b.required).filter(b=>
  ['practice','check'].includes(b.type)?(b.questionIds||[]).some(id=>!answered.has(id)):!record?.drafts?.blocks?.[b.id]?.completed
 ).map(b=>({...b,title:readingValue(task.snapshot,b,'title')}));
}
