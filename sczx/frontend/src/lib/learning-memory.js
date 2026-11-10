export function memoryTarget(target, returnTask, knowledgeId) {
  if (
    typeof target !== "string" ||
    !/^\/(learn|check|repair|result)\?/.test(target)
  )
    return "/memory";
  const url = new URL(target, "http://memory.local");
  if (returnTask) url.searchParams.set("returnTask", returnTask);
  if (knowledgeId) url.searchParams.set("returnKnowledge", knowledgeId);
  return url.pathname + url.search;
}

export function memoryAuditFor(audit, item) {
  if (!item) return audit || [];
  return (audit || []).filter(
    (a) =>
      a.knowledgeId === item.id ||
      a.details.original?.knowledgeIds?.includes(item.id) ||
      a.details.knowledgeIds?.includes(item.id) ||
      item.evidence.some((e) => e.eventId === a.eventId),
  );
}

export function memoryTeacherTask(target,items){
 if(typeof target!=='string'||!/^\/(learn|check|repair|result)\?/.test(target))return null;
 const params=new URL(target,'http://memory.local').searchParams;
 const task=params.get('task');if(task)return task;
 const wrong=params.get('wrong');return items.flatMap(i=>i.evidence).find(e=>e.wrongId===wrong)?.taskId||null;
}
