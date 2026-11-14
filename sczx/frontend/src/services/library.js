import { api } from './api.js';
const json = (body, method='POST') => ({method,body:JSON.stringify(body)});
export const libraryApi = {
  coverage:()=>api.request("/library/experience-coverage"),
  jobs: () => api.request('/ai/jobs?capability=case_extract'),
  materials: () => api.request('/library/materials'),
  upload: (form) => api.request('/library/materials',{method:'POST',body:form}),
  material: id => api.request('/library/materials/'+id),
  saveMaterial: (id,body) => api.request('/library/materials/'+id,json(body,'PUT')),
  unit: id => api.request('/library/units/'+id),
  saveUnit: (id,text) => api.request('/library/units/'+id,json({text},'PUT')),
  extract: unitIds => api.request('/library/extract',json({unitIds})),
  cases: () => api.request('/library/cases'),
  suggestions: id => api.request('/library/cases/'+id+'/knowledge-suggestions'),
  case: id => api.request('/library/cases/'+id),
  newCase: unitIds => api.request('/library/cases',json({unitIds})),
  save: (id,data) => api.request('/library/cases/'+id+'/draft',json({data},'PUT')),
  action: (id,action) => api.request('/library/cases/'+id+'/'+action,{method:'POST'}),
};
