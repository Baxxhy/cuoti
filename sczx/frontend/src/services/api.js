const apiBase = import.meta.env.VITE_API_BASE || "";
const uploadedImages = new Map();

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${apiBase}/api${path}`, {
      credentials: "include",
      cache: "no-store",
      headers: options.body instanceof FormData ? options.headers : { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new Error("无法连接到学习服务，请检查网络后重试。");
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const message = (typeof body?.detail === "object" ? body.detail.message : body?.detail) || (response.status === 401 ? "登录已失效，请重新登录。" : "操作未能完成，请重试。");
    const error = new Error(message);
    error.status = response.status;
    error.detail = body?.detail;
    throw error;
  }
  return body;
}

async function uploadImage(dataUrl) {
  const response = await fetch(dataUrl);
  const blob = await response.blob();
  const file = new File([blob], `题图-${Date.now()}.${blob.type.split("/")[1] || "png"}`, { type: blob.type || "image/png" });
  const form = new FormData();
  form.append("file", file);
  return request("/files", { method: "POST", body: form });
}

async function externalizeImages(value) {
  if (typeof value === "string" && value.startsWith("data:image/")) {
    if (!uploadedImages.has(value)) uploadedImages.set(value, uploadImage(value).then((file) => file.url).catch((error) => {
      uploadedImages.delete(value);
      throw error;
    }));
    return uploadedImages.get(value);
  }
  if (Array.isArray(value)) return Promise.all(value.map(externalizeImages));
  if (value && typeof value === "object") return Object.fromEntries(await Promise.all(Object.entries(value).map(async ([key, item]) => [key, await externalizeImages(item)])));
  return value;
}

function linkStudentRecords(data) {
  data.records ||= {};
  for (const [taskId, records] of Object.entries(data.studentRecords || {})) {
    if (!Array.isArray(records)) continue;
    const selected = records.find((item) => item.studentId === data.activeStudentId) || records[0];
    if (selected) data.records[taskId] = selected;
  }
  return data;
}

export const api = {
  request,
  me: () => request("/auth/me"),
  login: (username, password) => request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  async platform(lessonId) { return linkStudentRecords(await request("/platform"+(lessonId?"?lessonId="+encodeURIComponent(lessonId):""))); },
  setCaseFavorite: (id,selected) => request('/ai/cases/'+encodeURIComponent(id)+'/bookmark',{method:'PUT',body:JSON.stringify({selected})}),
  async savePlatform(data) { linkStudentRecords(data); return request("/platform", { method: "PUT", body: JSON.stringify({ data: await externalizeImages(data) }) }); },
  async publish(classroomId, lessonDraft) { return request("/tasks/publish", { method: "POST", body: JSON.stringify({ classroomId, lessonId:lessonDraft.lessonId, lessonDraft: await externalizeImages(lessonDraft), idempotencyKey: crypto.randomUUID() }) }); },
  submitTask: (taskId) => request(`/records/${encodeURIComponent(taskId)}/submit`, { method: "POST" }),
  saveFeedback: (recordId, feedback) => request(`/records/${encodeURIComponent(recordId)}/feedback`, { method: "PUT", body: JSON.stringify({ feedback }) }),
  accounts: () => request("/accounts"),
  createAccount: (payload) => request("/accounts", { method: "POST", body: JSON.stringify(payload) }),
  createClassroom: (payload) => request("/classrooms", { method: "POST", body: JSON.stringify(payload) }),
  addMember: (classId, studentId) => request(`/classrooms/${encodeURIComponent(classId)}/members`, { method: "POST", body: JSON.stringify({ studentId }) }),
  classroomMembers: (classId) => request(`/classrooms/${encodeURIComponent(classId)}/members`),
  replyIssue: (issueId, reply) => request(`/issues/${encodeURIComponent(issueId)}/reply`, { method: "PUT", body: JSON.stringify({ reply }) }),
  saveCase: (payload) => request("/cases/draft", { method: "PUT", body: JSON.stringify(payload) }),
  publishCase: (caseId) => request(`/cases/${encodeURIComponent(caseId)}/publish`, { method: "POST" }),
  async importLegacy(payload) { return request("/legacy-import", { method: "POST", body: JSON.stringify({ ...payload, data: await externalizeImages(payload.data) }) }); },
};

export function readLegacyData() {
  for (const key of ["shicheng-platform-v1", "shicheng-vue-prototype", "shicheng-nova-prototype-v2"]) {
    const raw = localStorage.getItem(key);
    if (!raw) continue;
    try { return { sourceId: key, data: JSON.parse(raw) }; }
    catch { return { sourceId: key, data: null, error: "找到的旧记录无法解析。" }; }
  }
  return null;
}
