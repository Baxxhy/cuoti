import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('late session initialization and older platform reads cannot replace a newer signed-in user or lesson', async()=>{
 const b=await Browser.launch();
 try{
  await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');
  const result=await b.eval(async()=>{
   const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
   const {useLearning}=await import('/src/store.js'),{createPlatform}=await import('/src/services/platform.js'),{api}=await import('/src/services/api.js');
   const previous=getActivePinia(),store=useLearning(createPinia()),saved={me:api.me,login:api.login,platform:api.platform};
   let rejectOld,resolveOld;api.me=()=>new Promise((_,reject)=>{rejectOld=reject});api.login=async()=>({user:{id:'user-B',username:'B',role:'student'}});api.platform=async()=>({...createPlatform(),lesson:{id:'signed-in-B'}});
   try{
    const initializing=store.initialize();await store.login('B','test-only');rejectOld(Object.assign(new Error('old expired session'),{status:401}));await initializing;
    const identity=store.user.id,initialLesson=store.data.lesson.id;
    api.platform=lesson=>lesson==='old'?new Promise(resolve=>{resolveOld=resolve}):Promise.resolve({...createPlatform(),lesson:{id:'new'}});
    const old=store.load('old');await store.load('new');resolveOld({...createPlatform(),lesson:{id:'old'}});await old;
    return{identity,initialLesson,lesson:store.data.lesson.id,status:store.status};
   }finally{Object.assign(api,saved);setActivePinia(previous)}
  });
  assert.deepEqual(result,{identity:'user-B',initialLesson:'signed-in-B',lesson:'new',status:'ready'});assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
