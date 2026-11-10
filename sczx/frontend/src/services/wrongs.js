import { api } from "./api.js";
const send = (path, body, method = "POST") =>
  api.request("/wrongs" + path, { method, body: JSON.stringify(body) });
export const wrongApi = {
  list: () => api.request("/wrongs"),
  options: () => api.request("/wrongs/options"),
  detail: (id) => api.request("/wrongs/" + encodeURIComponent(id)),
  create: (body) => send("", body),
  save: (id, body) => send("/" + encodeURIComponent(id), body, "PUT"),
  attempt: (id, body) => send("/" + encodeURIComponent(id) + "/attempts", body),
  review: (id, body) => send("/" + encodeURIComponent(id) + "/review", body),
};
export const wrongStatuses = {
  pending: "待补救",
  learning: "补救中",
  awaiting_retest: "待独立复测",
  retest_passed: "独立复测通过",
  retest_failed: "复测未通过",
  needs_review: "需要核对",
};
