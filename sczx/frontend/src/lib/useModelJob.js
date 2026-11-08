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
      if (["succeeded", "failed"].includes(value.status)) {
        clear();
        const completionKey = `${id}:${value.attemptNumber}:${value.status}`;
        if (completedId !== completionKey) { completedId = completionKey; await onDone(value); }
      }
    } catch (problem) { if (version === generation) error.value = problem.message; }
  }
  function poll(id, version) {
    timer = setTimeout(async () => {
      if (version !== generation) return;
      await refresh(id, version);
      if (version === generation && !["succeeded", "failed"].includes(job.value?.status)) poll(id, version);
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
    if (version !== generation || ["succeeded", "failed"].includes(job.value?.status)) return;
    const base = import.meta.env.VITE_API_BASE || "";
    source = new EventSource(`${base}/api/ai/jobs/${encodeURIComponent(value.id)}/events`, { withCredentials: true });
    source.addEventListener("progress", (event) => {
      if (version !== generation) return;
      const data = JSON.parse(event.data);
      job.value = { ...job.value, step: data.step, status: data.status, attemptNumber: data.attemptNumber };
    });
    source.addEventListener("done", () => refresh(value.id, version));
    source.onerror = () => { if (version === generation) { source?.close(); poll(value.id, version); } };
  }
  async function create(payload) {
    if (busy.value) return;
    submitting.value = true; error.value = "";
    try { await open(await modelApi.create(payload)); }
    catch (problem) { error.value = problem.message; }
    finally { submitting.value = false; }
  }
  async function retry() {
    if (busy.value || !job.value) return;
    submitting.value = true; error.value = "";
    try { await open(await modelApi.retry(job.value.id)); }
    catch (problem) { error.value = problem.message; }
    finally { submitting.value = false; }
  }
  onBeforeUnmount(() => { disposed = true; generation++; clear(); });
  return { job, busy, submitting, error, create, open, retry };
}
