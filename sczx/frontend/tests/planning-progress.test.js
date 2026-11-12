import{test}from'node:test';import assert from'node:assert/strict';import{planningStep}from'../src/lib/planning-progress.js';
test('manual revision shows its current verification while retaining the original failed generation',()=>{
 const r={steps:[{key:'validate',status:'failed',error:'原数学关系不一致',finishedAt:'old'}],editedAt:'new',verification:{structure:'passed',references:'passed',status:'verified'},accepted:{confirmedAt:'accepted'}};
 const before=JSON.stringify(r);assert.equal(planningStep(r,'validate').status,'succeeded');assert.equal(planningStep(r,'validate').originalFailure.error,'原数学关系不一致');assert.equal(planningStep(r,'ready').finishedAt,'accepted');assert.equal(JSON.stringify(r),before);
 assert.equal(planningStep({...r,editedAt:null},'validate').status,'failed');assert.equal(planningStep({...r,verification:{...r.verification,status:'inconsistent'}},'validate').status,'failed');
});
