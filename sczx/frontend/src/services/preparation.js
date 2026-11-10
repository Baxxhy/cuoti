import {api} from './api.js';
const base=id=>'/preparation/'+encodeURIComponent(id);
export const preparationApi={
 versions:id=>api.request(base(id)+'/versions'),
 version:(id,v)=>api.request(base(id)+'/versions/'+encodeURIComponent(v)),
 restore:(id,versionId,revision)=>api.request(base(id)+'/restore',{method:'POST',body:JSON.stringify({versionId,revision,confirmed:true})}),
 options:(id,versionId)=>api.request(base(id)+'/export-options'+(versionId?'?versionId='+encodeURIComponent(versionId):'')),
 async export(id,versionId,mode='formal',cleanEditorial=false){const params=new URLSearchParams({mode,cleanEditorial:String(cleanEditorial)});if(versionId)params.set('versionId',versionId);const response=await fetch('/api'+base(id)+'/export?'+params,{credentials:'include'});if(!response.ok)throw Error((await response.json()).detail||'导出失败');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=(mode==='trace'?'完整溯源教案':'正式教案')+'.docx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)},
};
