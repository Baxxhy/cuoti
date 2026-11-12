import {test} from 'node:test';
import assert from 'node:assert/strict';
import {statusTone,statusText} from '../src/lib/status-tone.js';
test('pending, in-progress and completed learning states remain distinct',()=>{
 assert.equal(statusTone('待完成'),'pending');assert.equal(statusTone('学习中'),'active');assert.equal(statusTone('已完成'),'success');assert.equal(statusTone('已提交'),'success');
});
test('uncertain mathematical evidence never inherits a success color',()=>{
 assert.equal(statusTone('需人工核对','green'),'pending');assert.equal(statusTone('核验不一致','green'),'danger');assert.equal(statusTone('未通过','green'),'pending');assert.equal(statusTone('待核对：答案可能正确','green'),'pending');
});
test('failures and overdue work are errors; drafts and unavailable actions stay neutral',()=>{
 for(const label of ['生成失败','已逾期','2人逾期','答案不正确'])assert.equal(statusTone(label),'danger');
 for(const label of ['草稿','已取消','未配置','历史记录'])assert.equal(statusTone(label),'neutral');
});
test('unknown labels retain explicit caller tone and help has its own informational state',()=>{
 assert.equal(statusTone('用过帮助'),'info');assert.equal(statusTone('独立作答'),'info');assert.equal(statusTone('数学','blue'),'active');assert.equal(statusTone('数学'),'neutral');
});
test('slot fragments and numbers retain a readable status label',()=>{
 assert.equal(statusText([{children:'待完成 '},{children:[{children:2},{children:' 项'}]}]),'待完成 2 项');
});
