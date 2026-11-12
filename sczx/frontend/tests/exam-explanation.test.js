import{test}from'node:test';import assert from'node:assert/strict';import{examExplanation}from'../src/lib/exam-explanation.js';
test('candidate presentation fixes escaped newlines and workflow suffix without editing frozen data or TeX',()=>{
 const q={candidateJobId:'generated',explanation:'两边减5。\\n\\n分步解释：\\n1. 得x=7。\\n本题为待教师审核的候选题。'};const original=JSON.stringify(q);
 assert.equal(examExplanation(q),'两边减5。\n\n分步解释：\n1. 得x=7。');assert.equal(JSON.stringify(q),original);
 assert.equal(examExplanation({candidateJobId:'generated',explanation:'x\\neq 0'}),'x\\neq 0');assert.equal(examExplanation({explanation:q.explanation}),q.explanation);
 const old={source:'AI候选，待教师审核；ModelJob old-job',reviewRecord:{at:'2026-11-12'},explanation:'说明。\\\\n\\\\n1. 两边同减5。\\\\n本题为待教师审核的候选题。'};
 assert.equal(examExplanation(old),'说明。\n\n1. 两边同减5。');assert.equal(old.explanation.includes('\\\\n'),true);
});
