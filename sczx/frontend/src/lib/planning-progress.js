// Generation steps remain historical evidence. Present the later, explicit
// teacher revision separately instead of reporting its resolved failure as live.
export function planningStep(result,key){
 const original=result?.steps?.find(s=>s.key===key);
 const checked=result?.editedAt&&result?.verification?.structure==='passed'&&result?.verification?.references==='passed'&&['verified','unverified'].includes(result?.verification?.status);
 if(!checked||!['validate','ready'].includes(key))return original;
 return {...original,key,status:'succeeded',tool:key==='validate'?'教师修订后的程序核验':'教师确认',startedAt:result.editedAt,finishedAt:key==='ready'?(result.accepted?.confirmedAt||result.editedAt):result.editedAt,error:undefined,reviewedAfterEdit:true,originalFailure:original?.status==='failed'?{error:original.error,finishedAt:original.finishedAt}:undefined};
}
