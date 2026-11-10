import { api } from './api.js';
export const insightsApi = {
  get: (params) => api.request('/insights?' + new URLSearchParams(Object.entries(params).filter(([,v])=>v))),
  review: body => api.request('/insights/reviews',{method:'POST',body:JSON.stringify(body)}),
};
export const supportApi = {
  list: params => api.request('/support?' + new URLSearchParams(params || {})),
  create: body => api.request('/support',{method:'POST',body:JSON.stringify(body)}),
  update: (id,body) => api.request('/support/'+id+'/events',{method:'POST',body:JSON.stringify(body)}),
};
