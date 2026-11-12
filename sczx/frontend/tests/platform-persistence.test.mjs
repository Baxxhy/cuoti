import{test}from'node:test';import assert from'node:assert/strict';import{Browser}from'./cdp.mjs';
test('read-only metadata never saves; draft edits serialize, failures retain edits and old account errors stay scoped',async()=>{
 const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");
 const result=await b.eval(async()=>{
  const{createPinia}=await import('/node_modules/.vite/deps/pinia.js'),{useLearning}=await import('/src/store.js'),{createPlatform}=await import('/src/services/platform.js'),{api}=await import('/src/services/api.js');const s=useLearning(createPinia()),old={platform:api.platform,savePlatform:api.savePlatform},writes=[];
  const data={...createPlatform(),lesson:{id:'lesson'},lessonDraft:{id:'draft',lessonId:'lesson',goal:'原目标',blocks:[],questions:[],revision:1},records:{r:{feedback:'服务端反馈'}}};s.user={id:'teacher-one',role:'teacher'};api.platform=async()=>data;api.savePlatform=async payload=>{writes.push(payload);return{draftRevision:2}};
  try{await s.load();s.data.activeTaskId='read-only';s.data.messages=[{title:'只读消息'}];s.data.records.r.feedback='另一个专用接口保存的反馈';s.touch();await s.save();const cleanCount=writes.length;
   s.data.lessonDraft.goal='新目标';await s.save();const teacherPayload=writes[0],afterSave=!s.hasUnsavedChanges;
   let release;api.savePlatform=payload=>{writes.push(payload);return new Promise(r=>release=r)};s.data.lessonDraft.goal='正在保存';const pending=s.save();await new Promise(r=>setTimeout(r,0));s.data.lessonDraft.goal='保存期间的新修改';api.savePlatform=async payload=>{writes.push(payload);return{draftRevision:4}};release({draftRevision:3});await pending;const latest=writes.at(-1).lessonDraft.goal;
   api.savePlatform=async()=>{throw Error('controlled failure')};s.data.lessonDraft.goal='失败后保留';const failed=await s.save(),retained=s.data.lessonDraft.goal,dirty=s.hasUnsavedChanges;await s.load();const reloaded={clean:!s.hasUnsavedChanges,error:s.saveError};
   let reject;api.savePlatform=()=>new Promise((_,r)=>reject=r);s.data.lessonDraft.goal='旧账号修改';const oldSave=s.save();s.user={id:'teacher-two',role:'teacher'};s.data={...data,lessonDraft:{...data.lessonDraft,goal:'新账号目标'}};reject(Error('old account error'));await oldSave;
   return{cleanCount,teacherPayload,afterSave,latest,failed,retained,dirty,reloaded,currentGoal:s.data.lessonDraft.goal,error:s.saveError};
  }finally{Object.assign(api,old)}
 });assert.equal(result.cleanCount,0);assert.equal(result.teacherPayload.lessonDraft.goal,'新目标');assert(!('records'in result.teacherPayload));assert(result.afterSave);assert.equal(result.latest,'保存期间的新修改');assert.equal(result.failed,false);assert.equal(result.retained,'失败后保留');assert(result.dirty);assert.deepEqual(result.reloaded,{clean:true,error:''});assert.equal(result.currentGoal,'新账号目标');assert.equal(result.error,'');assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
