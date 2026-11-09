import { api } from "./api.js";

export const modelApi = {
  search: (query = "") => api.request(`/ai/search?q=${encodeURIComponent(query)}`),
  contextualSearch: (body) => api.request('/ai/search',{method:'POST',body:JSON.stringify(body)}),
  searchOptions: () => api.request('/ai/search-options'),
  caseDetail: (id, versionId) => api.request(`/ai/cases/${encodeURIComponent(id)}${versionId ? `?versionId=${encodeURIComponent(versionId)}` : ""}`),
  capabilities: () => api.request("/ai/capabilities"),
  list: (recordId) => api.request(`/ai/jobs${recordId ? `?recordId=${encodeURIComponent(recordId)}` : ""}`),
  detail: (id) => api.request(`/ai/jobs/${encodeURIComponent(id)}`),
  create: (payload) => api.request("/ai/jobs", { method: "POST", body: JSON.stringify({ requestKey: crypto.randomUUID(), ...payload }) }),
  retry: (id) => api.request(`/ai/jobs/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  correct: (id, text) => api.request(`/ai/jobs/${encodeURIComponent(id)}/correction`, { method: "PUT", body: JSON.stringify({ text }) }),
  async upload(file) {
    const body = new FormData();
    body.append("file", file);
    return api.request("/files", { method: "POST", body });
  },
};

export const capabilityNames = { document_parse: "文档解析", document_ocr: "原文识别", case_extract: "案例提取", retrieval: "案例检索", text: "文字指导", ocr: "题图识别", embedding: "文本向量", rerank: "材料重排", asr: "语音转写", tts: "讲解音频" };
