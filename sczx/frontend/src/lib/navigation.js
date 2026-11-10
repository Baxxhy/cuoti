const taskPages = new Set([
  "learn",
  "check",
  "result",
  "insights",
]);
export function navigate(destination) {
  const [page, query = ""] = destination.split("?");
  const params = new URLSearchParams(query);
  if (taskPages.has(page) && !params.has("task")) {
    const current = new URLSearchParams(location.hash.split("?")[1] || "");
    if (current.has("task")) params.set("task", current.get("task"));
  }
  window.location.hash =
    "/" + page + (params.size ? "?" + params.toString() : "");
}
