import {api} from './api.js';
const base=id=>'/preparation/'+encodeURIComponent(id);
export const preparationApi={
 versions:id=>api.request(base(id)+'/versions'),
 version:(id,v)=>api.request(base(id)+'/versions/'+encodeURIComponent(v)),
 restore:(id,versionId,revision)=>api.request(base(id)+'/restore',{method:'POST',body:JSON.stringify({versionId,revision,confirmed:true})}),
 async export(id,versionId){const response=await fetch('/api'+base(id)+'/export'+(versionId?'?versionId='+encodeURIComponent(versionId):''),{credentials:'include'});if(!response.ok)throw Error((await response.json()).detail||'导出失败');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='教案.docx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)},
};
