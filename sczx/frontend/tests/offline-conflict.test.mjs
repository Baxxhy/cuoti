import{test}from'node:test';import assert from'node:assert/strict';import{Browser}from'./cdp.mjs';
test('confirming position cannot silently rebase another conflicting answer; normal own-write batches still advance',async()=>{
 const b=await Browser.launch();try{
 await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");
 const result=await b.eval(async()=>{
  const{enableVault,mutateVault,vaultData,closeVault}=await import('/src/services/offline/vault.js');const{saveLocal,syncDrafts,confirmConflict}=await import('/src/services/offline/learning.js');const{api}=await import('/src/services/api.js');const previous={me:api.me,request:api.request},user={id:'conflict-fixture',username:'conflict-fixture'},base='0'.repeat(64),external='5'.repeat(64);let revision=external,answer='5',counter=5,calls=[];
  await enableVault(user,'fixture-unlock-1112');const pkg={taskId:'task-fixture',userId:user.id,versionId:'a'.repeat(64),baseRevision:base,offlineUntil:new Date(Date.now()+86400000).toISOString(),drafts:{questions:{}},blocks:[]};await mutateVault(d=>d.packages.push(pkg));
  api.me=async()=>({user});api.request=async(path,opts)=>{const op=JSON.parse(opts.body);calls.push(op);if(op.baseRevision!==revision){const e=new Error('conflict');e.status=409;e.detail={allowRetry:true,serverRevision:revision,serverDrafts:{questions:{q:{answer}},lessonPosition:{blockId:'intro'}}};throw e}if(op.questionId==='q')answer=op.answer;revision=String(++counter).repeat(64);return{revision}};
  try{
   await saveLocal(pkg,'@position',{position:'next'});await saveLocal(pkg,'q',{answer:'4',reason:'本机内容'});const first=await syncDrafts();const pos=vaultData().operations.find(o=>o.questionId==='@position');await confirmConflict(pos.operationId);const second=await syncDrafts();const afterPosition={answer,questionStatus:vaultData().operations.find(o=>o.questionId==='q').status,second};
   await saveLocal(vaultData().packages[0],'q',{answer:'4',reason:'再次保存同一草稿'});const reeditBase=vaultData().operations.find(o=>o.questionId==='q').baseRevision;await syncDrafts();const afterReedit=answer;const question=vaultData().operations.find(o=>o.questionId==='q');await confirmConflict(question.operationId);await syncDrafts();const afterQuestion=answer;
   // New operations created against the same current revision can move as one batch.
   const current=vaultData().packages[0];await saveLocal(current,'@position',{position:'last'});await saveLocal(current,'q',{answer:'6'});const normal=await syncDrafts();return{first,afterPosition,reeditBase,afterReedit,afterQuestion,normal,answer,calls:calls.map(x=>({questionId:x.questionId,base:x.baseRevision}))};
  }finally{Object.assign(api,previous);await closeVault()}
 });
 assert.equal(result.first.conflicts,1);assert.equal(result.afterPosition.answer,'5');assert.equal(result.afterPosition.questionStatus,'conflict');assert.equal(result.afterPosition.second.conflicts,1);assert.equal(result.reeditBase,'0'.repeat(64));assert.equal(result.afterReedit,'5');assert.equal(result.afterQuestion,'4');assert.equal(result.normal.synced,2);assert.equal(result.normal.conflicts,0);assert.equal(result.answer,'6');assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
