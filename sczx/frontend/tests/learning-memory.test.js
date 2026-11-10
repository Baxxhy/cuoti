import test from 'node:test';
import assert from 'node:assert/strict';
import {memoryAuditFor,memoryTarget,memoryTeacherTask} from '../src/lib/learning-memory.js';
test('knowledge correction remains auditable from old and new knowledge',()=>{
 const change={kind:'knowledge_correction',knowledgeId:'A',eventId:'event1',details:{original:{knowledgeIds:['A']},knowledgeIds:['B']}};
 assert.equal(memoryAuditFor([change],{id:'A',evidence:[]}).length,1);assert.equal(memoryAuditFor([change],{id:'B',evidence:[]}).length,1);assert.equal(memoryAuditFor([change],{id:'C',evidence:[]}).length,0);
});
test('review targets retain return scope without accepting arbitrary destinations',()=>{assert.equal(memoryTarget('/repair?wrong=w','taskB','A'),'/repair?wrong=w&returnTask=taskB&returnKnowledge=A');assert.equal(memoryTarget('https://invalid/'),'/memory');assert.equal(memoryTeacherTask('/repair?wrong=w',[{evidence:[{wrongId:'w',taskId:'A'}]}]),'A');assert.equal(memoryTeacherTask('https://invalid/',[]),null)});
