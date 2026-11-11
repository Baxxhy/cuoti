// Business groups replace the old frequent/more split. Routes remain bookmarkable.
export const workspaceGroups={
 student:[
  {id:'learning',label:'学习',route:'home',routes:['home','courses','records','offline','learn','check','result'],tabs:[['home','学习任务'],['courses','课程'],['records','学习记录'],['offline','离线学习']]},
  {id:'review',label:'错题与复习',route:'wrong',routes:['wrong','repair','memory'],tabs:[['wrong','错题本'],['memory','复习建议']]},
  {id:'classroom',label:'班级',route:'class',routes:['class','exams','live'],tabs:[['class','我的班级'],['exams','考试'],['live','课堂']]},
 ],
 teacher:[
  {id:'overview',label:'教学概览',route:'teacher',routes:['teacher'],tabs:[]},
  {id:'resources',label:'教学资源',route:'cases',routes:['cases','case-detail','community'],tabs:[['cases','教学案例'],['community','教研交流']]},
  {id:'planning',label:'备课',route:'prepare',routes:['prepare','agent','courses'],tabs:[['courses','课程'],['prepare','教案'],['agent','AI备课']]},
  {id:'classroom',label:'班级教学',route:'class',routes:['class','insights','live','groups','memory'],tabs:[['class','班级与任务'],['insights','学情反馈'],['live','实时课堂'],['groups','分层教学'],['memory','学生复习']]},
  {id:'assessment',label:'题库与考试',route:'exam-papers',routes:['exam-bank','exam-papers','exams'],tabs:[['exam-bank','题库'],['exam-papers','组卷'],['exams','考试与批阅']]},
 ],
 admin:[
  {id:'materials',label:'资料与案例',route:'manage',routes:['manage','cases','case-detail'],tabs:[]},
  {id:'curriculum',label:'课程内容',route:'content',routes:['content','courses'],tabs:[]},
  {id:'operations',label:'管理与运行',route:'issues',routes:['issues'],tabs:[]},
 ],
};
export function workspaceFor(role,routeName){return (workspaceGroups[role]||[]).find(g=>g.routes.includes(routeName))||null}
export function workspaceHref(role,target,query={},classId=''){
 const params=new URLSearchParams();
 if(role==='teacher'){
  const classroom=query.class||query.classId||classId;
  if(classroom&&['class','insights','live','groups','memory'].includes(target))params.set(target==='memory'?'classId':'class',String(classroom));
  if(target==='memory'&&query.studentId)params.set('studentId',String(query.studentId));
  if(['prepare','agent'].includes(target)&&query.lesson)params.set('lesson',String(query.lesson));
 }
 return '#/'+target+(params.size?'?'+params.toString():'');
}
