// Old AI candidates sometimes stored escaped newlines and an editorial status.
// Present those snapshots faithfully as content without changing the frozen data.
export function examExplanation(question={}){
 const text=question.explanation||'';
 if(!question.candidateJobId&&!/^AI候选[，,；;]/.test(question.source||''))return text;
 return text.replace(/\\+n(?![A-Za-z])/g,'\n').replace(/\s*本题为待教师审核的候选题[。.]?\s*$/,'').trim();
}
