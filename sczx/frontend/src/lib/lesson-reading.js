// Presentation only: keep the stored lesson and all mathematical conditions intact.
const expressionPattern = /[-−(\[\dA-Za-z][\dA-Za-z \t()+\-−*/×÷=^.[\]{}]*=[\dA-Za-z \t()+\-−*/×÷=^.[\]{}]+/g;
export function readingValue(lesson, block, key='content') {
  const source=block.agentJobId?lesson.lessonSnapshot?.blocks?.find(item=>item.id===block.id):null;
  const field=key==='content'?'studentContent':'studentTitle';
  return block[field]??source?.[field]??source?.[key]??block[key]??'';
}
export function mathFragments(text='') {
  const value=String(text),parts=[];let offset=0;
  for(const match of value.matchAll(expressionPattern)) {
    if(match.index>offset) parts.push({type:'text',text:value.slice(offset,match.index)});
    parts.push({type:'equation',text:match[0]});offset=match.index+match[0].length;
  }
  if(offset<value.length) parts.push({type:'text',text:value.slice(offset)});
  return parts.length?parts:[{type:'text',text:value}];
}
export function readingLines(text='') {
  return (String(text).match(/[^\n。；]+[。；]?|[。；]/g)||[]).map(value=>({text:value,parts:mathFragments(value)}));
}
export function relatedExample(lesson, currentBlock) {
  for(const block of lesson.blocks||[]) {
    if(block.type!=='example'||block.id===currentBlock.id)continue;
    const equation=mathFragments(readingValue(lesson,block)).find(part=>part.type==='equation');
    if(equation)return {equation:equation.text.trim(),title:readingValue(lesson,block,'title')};
  }
  return null;
}
