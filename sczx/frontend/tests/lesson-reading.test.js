import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mathFragments,readingLines,readingValue,relatedExample} from '../src/lib/lesson-reading.js';

test('all five lessons retain every original clause and mathematical condition in presentation fragments',()=>{
 const bundle=JSON.parse(readFileSync(new URL('../../docs/planning/第十六步单元内容草案_20261111_v1.json',import.meta.url)));
 for(const row of bundle.lessons)for(const block of row.data.blocks){
  assert.equal(mathFragments(block.content).map(p=>p.text).join(''),block.content);
  assert.equal(readingLines(block.content).map(p=>p.text).join(''),block.content.replace(/\n/g,''));
 }
 for(const text of ['0x=0有无穷多解，0x=1无解；同除的数必须非零。','x/(-3)=4','-2(x+3)=-2x-6','x/2+x/3=5','2[x+(x+3)]=30'])assert.equal(mathFragments(text).map(p=>p.text).join(''),text);
});
test('the example visual comes from the same lesson, never from a check answer',()=>{
 const block={id:'intro',type:'explanation',content:'先明确未知数。'};
 const lesson={blocks:[block,{id:'example',type:'example',title:'原例题',content:'解2x+3=11：两边减3。'}],questions:[{kind:'check',equation:'x=999'}]};
 assert.deepEqual(relatedExample(lesson,block),{equation:'2x+3=11',title:'原例题'});assert.equal(relatedExample({blocks:[block],questions:lesson.questions},block),null);
});
test('legacy AI text and explicit student revisions retain their own frozen source without mutation',()=>{
 const block={id:'a',agentJobId:'legacy',content:'出示等式。'},lesson={blocks:[block],lessonSnapshot:{blocks:[{id:'a',content:'等式两边同加3。'}]}};
 const before=JSON.stringify(lesson);assert.equal(readingValue(lesson,block),'等式两边同加3。');assert.equal(JSON.stringify(lesson),before);
 assert.equal(readingValue(lesson,{...block,studentContent:'两边同减2。'}),'两边同减2。');
});
