import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workspaceGroups,workspaceFor,workspaceHref} from '../src/lib/workspace-navigation.js';
import {incompleteBlocks} from '../src/lib/task-completion.js';

test('each existing destination has one business home and detail routes stay with their parent',()=>{
 const expected={student:['home','courses','exams','live','wrong','memory','records','class'],teacher:['teacher','cases','courses','prepare','agent','exam-bank','exam-papers','exams','live','groups','community','class','memory','insights'],admin:['manage','content','issues']};
 for(const [role,routes] of Object.entries(expected))for(const route of routes)assert.equal(workspaceGroups[role].filter(g=>g.routes.includes(route)).length,1,role+':'+route);
 assert.equal(workspaceGroups.student.length,3);assert.equal(workspaceGroups.teacher.length,5);
 for(const route of ['learn','check','result'])assert.equal(workspaceFor('student',route).id,'learning');
 assert.equal(workspaceFor('student','repair').id,'review');assert.equal(workspaceFor('teacher','case-detail').id,'resources');
});
test('class and lesson context survives navigation with the route-specific parameter names',()=>{
 assert.equal(workspaceHref('teacher','groups',{class:'class-a'}),'#/groups?class=class-a');
 assert.equal(workspaceHref('teacher','memory',{class:'class-a',studentId:'student-b'}),'#/memory?classId=class-a&studentId=student-b');
 assert.equal(workspaceHref('teacher','insights',{classId:'class-a'}),'#/insights?class=class-a');
 assert.equal(workspaceHref('teacher','live',{},'class-current'),'#/live?class=class-current');
 assert.equal(workspaceHref('teacher','agent',{lesson:'lesson-a'}),'#/agent?lesson=lesson-a');
});
test('a result offers the first required uncompleted step and respects question evidence',()=>{
 const task={snapshot:{lessonSnapshot:{},blocks:[{id:'intro',title:'原教师标题',studentTitle:'认识等式',type:'explanation',required:true},{id:'practice',title:'随堂练习',type:'practice',questionIds:['p1'],required:true},{id:'check',title:'独立练习',type:'check',questionIds:['q1','q2'],required:true}]},questions:[{id:'p1'},{id:'q1'},{id:'q2'}]};
 const record={drafts:{blocks:{}},attempts:[{question:0},{question:1}]};
 assert.deepEqual(incompleteBlocks(task,record).map(b=>b.title),['认识等式','独立练习']);
 record.drafts.blocks.intro={completed:true};record.attempts.push({question:2});assert.deepEqual(incompleteBlocks(task,record),[]);
 assert.deepEqual(incompleteBlocks({snapshot:{blocks:task.snapshot.blocks}},{}),[]);
});
