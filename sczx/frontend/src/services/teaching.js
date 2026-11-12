import { api } from "./api.js";
const get = (path) => api.request("/teaching" + path);
const send = (path, body = {}, method = "POST") =>
  api.request("/teaching" + path, { method, body: JSON.stringify(body) });
export const teachingApi = {
  classes: () => get("/classes"),
  dashboard: (id) =>
    get("/dashboard" + (id ? "?classId=" + encodeURIComponent(id) : "")),
  editClass: (id, data) => send("/classes/" + id, data, "PUT"),
  removeMember: (id, student) =>
    send("/classes/" + id + "/members/" + student, {}, "DELETE"),
  tasks: (id) => get("/classes/" + id + "/tasks"),
  task: (id) => get("/tasks/" + id),
  assign: (id, studentIds) => send("/tasks/" + id + "/assign", { studentIds }),
  invite: (id, days = 7) => send("/classes/" + id + "/invites", { days }),
  invites: (id) => get("/classes/" + id + "/invites"),
  revoke: (id, invite) =>
    send("/classes/" + id + "/invites/" + invite + "/revoke"),
  join: (code) => send("/join", { code }),
  messages: (box = "inbox") => get("/messages?box=" + box),
  read: (id) => send("/messages/" + id + "/read"),
  supplements: (id) => get("/tasks/" + id + "/supplements"),
  arrange: (id, data) =>
    send("/tasks/" + id + "/supplements", {
      requestKey: crypto.randomUUID(),
      ...data,
    }),
  act: (id, action, response = "") =>
    send("/supplements/" + id + "/" + action, { response }),
  cancel: (id) => send("/supplements/" + id + "/cancel"),
  feedback: (id, student, feedback) =>
    send("/supplements/" + id + "/students/" + student + "/feedback", {
      feedback,
    }, "PUT"),
};
export const deadlineText = (value) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "无截止时间";
