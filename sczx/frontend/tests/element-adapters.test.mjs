import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('Element controls preserve selected IDs, checkbox arrays, local file selection and native form submission',async()=>{
 const b=await Browser.launch();
 try{
  await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');
  await b.wait("!!document.querySelector('#root')?.__vue_app__");
  const result=await b.eval(async()=>{
   const {createApp,h,ref,nextTick}=await import('/node_modules/.vite/deps/vue.js');
   const {default:Button}=await import('/src/components/app/Button.vue');
   const {default:Select}=await import('/src/components/app/NativeSelect.js');
   const {default:Checkbox}=await import('/src/components/app/Checkbox.vue');
   const {default:FilePicker}=await import('/src/components/app/FilePicker.vue');
   const selected=ref('room-a'),ids=ref([]),picked=[];let submitted=0;
   const el=document.createElement('div');document.body.append(el);
   const app=createApp({render:()=>h('section',{},[
    h('form',{onSubmit:e=>{e.preventDefault();submitted++}},[
     h(Select,{modelValue:selected.value,'onUpdate:modelValue':v=>selected.value=v},{default:()=>[h('option',{value:'room-a'},'甲班'),h('option',{value:'room-b'},'乙班')]}),
     h(Checkbox,{modelValue:ids.value,value:'student-a','onUpdate:modelValue':v=>ids.value=v},{default:()=> '甲同学'}),
     h(Button,{},()=> '保存')]),
    h(FilePicker,{id:'controlled-element-file',accept:'.txt',onChange:e=>picked.push(e.target.files[0]?.name)})])});
   Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);
   app.mount(el);
   const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Element interaction did not settle')};
   try{
    el.querySelector('.el-select__wrapper').click();
    await wait(()=>[...document.querySelectorAll('.el-select-dropdown__item')].some(n=>n.textContent==='乙班'));
    [...document.querySelectorAll('.el-select-dropdown__item')].find(n=>n.textContent==='乙班').click();await nextTick();
    el.querySelector('input[type=checkbox]').click();await nextTick();
    el.querySelector('form button').click();await nextTick();
    const input=el.querySelector('input[type=file]'),transfer=new DataTransfer();transfer.items.add(new File(['demo'],'样本.txt',{type:'text/plain'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
    await wait(()=>picked.length===1);
    return {selected:selected.value,ids:[...ids.value],isArray:Array.isArray(ids.value),picked,submitted,standardControls:!!el.querySelector('.el-button')&&!!el.querySelector('.el-select')&&!!el.querySelector('.el-checkbox')&&!!el.querySelector('.el-upload')};
   }finally{app.unmount();el.remove()}
  });
  assert.deepEqual(result,{selected:'room-b',ids:['student-a'],isArray:true,picked:['样本.txt'],submitted:1,standardControls:true});
  assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
