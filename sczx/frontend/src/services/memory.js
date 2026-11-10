import { api } from "./api.js";
export const memoryApi = {
  overview: ({ studentId, classId } = {}) => {
    const q = new URLSearchParams();
    if (studentId) q.set("studentId", studentId);
    if (classId) q.set("classId", classId);
    return api.request("/memory" + (q.size ? "?" + q : ""));
  },
  change: (body) =>
    api.request("/memory/changes", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
export { memoryTarget, memoryAuditFor, memoryTeacherTask } from "@/lib/learning-memory.js";
