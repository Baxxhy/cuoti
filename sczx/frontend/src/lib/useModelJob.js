import { ref, computed, onBeforeUnmount } from "vue";
import { modelApi } from "@/services/models.js";

export function useModelJob(onDone = () => {}) {
  const job = ref(null), error = ref(""), submitting = ref(false);
  const busy = computed(() => submitting.value || ["queued", "running"].includes(job.value?.status));
  let source, timer, generation = 0, completedId, disposed = false;
  function clear() { source?.close(); source = null; clearTimeout(timer); }
  async function refresh(id, version) {
    try {
      const value = await modelApi.detail(id);
      if (version !== generation) return;
      job.value = value;
      error.value = "";
      if (["succeeded", "failed", "cancelled"].includes(value.status)) {
        clear();
        const completionKey = `${id}:${value.attemptNumber}:${value.status}`;
        if (completedId !== completionKey) { completedId = completionKey; await onDone(value); }
      }
    } catch (problem) { if (version === generation) error.value = problem.message; }
  }
  function poll(id, version) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (version !== generation) return;
      await refresh(id, version);
      if (version === generation && !["succeeded", "failed", "cancelled"].includes(job.value?.status)) poll(id, version);
    }, 1500);
  }
  async function open(value) {
    if (disposed) return;
    clear();
    const version = ++generation;
    error.value = "";
    job.value = value;
    if (!value) return;
    await refresh(value.id, version);
    if (version !== generation || ["succeeded", "failed", "cancelled"].includes(job.value?.status)) return;
    const base = import.meta.env.VITE_API_BASE || "";
    source = new EventSource(`${base}/api/ai/jobs/${encodeURIComponent(value.id)}/events`, { withCredentials: true });
    source.addEventListener("progress", (event) => {
      if (version !== generation) return;
      try {
        const data = JSON.parse(event.data);
        if (["succeeded", "failed", "cancelled"].includes(data.status)) { refresh(value.id, version); return; }
        job.value = { ...job.value, step: data.step, status: data.status, attemptNumber: data.attemptNumber };
        if (value.capability === 'lesson_agent') refresh(value.id, version);
      } catch { source?.close(); poll(value.id, version); }
    });
    source.addEventListener("done", () => refresh(value.id, version));
    source.onerror = () => { if (version === generation) { source?.close(); poll(value.id, version); } };
  }
  async function create(payload) {
    if (busy.value) return;
    submitting.value = true; error.value = "";
    const version = generation;
    try { const value = await modelApi.create(payload); if (!disposed && version === generation) await open(value); }
    catch (problem) { if (!disposed && version === generation) error.value = problem.message; }
    finally { submitting.value = false; }
  }
  async function retry() {
    if (busy.value || !job.value) return;
    submitting.value = true; error.value = "";
    const version = generation, id = job.value.id;
    try { const value = await modelApi.retry(id); if (!disposed && version === generation) await open(value); }
    catch (problem) { if (!disposed && version === generation) error.value = problem.message; }
    finally { submitting.value = false; }
  }
  onBeforeUnmount(() => { disposed = true; generation++; clear(); });
  return { job, busy, submitting, error, create, open, retry };
}
