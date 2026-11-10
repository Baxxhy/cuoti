<script setup>
import { ref, computed, watch, inject, useId, nextTick } from "vue";
import { useLearning } from "@/store.js";
import { curriculumApi } from "@/services/curriculum.js";
const props = defineProps({
  question: { type: Object, required: true },
  index: { type: Number, required: true },
  preview: Boolean,
});
const emit = defineEmits(["guide"]);
const store = useLearning(),
  notify = inject("notify", () => {});
const key = computed(() => props.question.id || String(props.index));
const instanceId = useId();
const fieldId = computed(() =>
  props.preview ? "preview-" + instanceId + "-" + key.value : key.value,
);
const answer = ref(""),
  reason = ref(""),
  hint = ref(""),
  helped = ref(false),
  busy = ref(false),
  error = ref(""),
  restoring = ref(false);
watch(
  () => `${props.preview ? "preview" : store.record?.id}:${key.value}`,
  async () => {
    restoring.value = true;
    const saved = props.preview
      ? {}
      : store.record?.drafts?.questions?.[key.value] || {};
    answer.value = saved.answer || "";
    reason.value = saved.reason || "";
    hint.value = saved.hint || "";
    helped.value =
      !!saved.helped ||
      !!store.record?.helps?.some((h) => h.question === props.index);
    error.value = "";
    await nextTick();
    restoring.value = false;
  },
  { immediate: true, flush: "sync" },
);
watch(
  () => store.record?.helps?.some((h) => h.question === props.index),
  (value) => {
    if (value && !props.preview) helped.value = true;
  },
  { immediate: true },
);
const latest = computed(() =>
  props.preview
    ? null
    : store.record?.attempts.filter((a) => a.question === props.index).at(-1),
);
watch([answer, reason, hint, helped], () => {
  if (restoring.value || props.preview || !store.record || store.task?.readOnly)
    return;
  store.record.drafts.questions ||= {};
  store.record.drafts.questions[key.value] = {
    answer: answer.value,
    reason: reason.value,
    hint: hint.value,
    helped: helped.value,
  };
  store.touch();
});
async function submit() {
  if (props.preview) {
    error.value = "预览作答不保存学习记录";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await store.submitAnswer(
      props.index,
      answer.value,
      reason.value,
      helped.value,
    );
    notify("作答已保存");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function ask() {
  const task = store.task?.id,
    record = store.record?.id,
    index = props.index;
  if (props.preview) {
    hint.value = "正式学习时可请求提示，预览不产生帮助记录。";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    if (!(await store.save())) throw new Error(store.saveError);
    if (
      store.record?.id !== record ||
      store.task?.id !== task ||
      props.index !== index
    )
      return;
    const r = await curriculumApi.hint(task, index);
    if (store.record?.id !== record || props.index !== index) return;
    hint.value = r.hint;
    helped.value = true;
    await store.refreshRecord();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="curriculum-answer" :data-question-id="key">
    <label :for="'answer-' + fieldId" class="field-label">你的答案</label
    ><Input
      :id="'answer-' + fieldId"
      v-model="answer"
      :disabled="(!preview && store.task?.readOnly) || busy"
    /><label :for="'reason-' + fieldId" class="field-label">解释你的运算</label
    ><Textarea
      :id="'reason-' + fieldId"
      v-model="reason"
      :disabled="(!preview && store.task?.readOnly) || busy"
    />
    <p v-if="hint" class="inline-notice">{{ hint }}</p>
    <p
      v-if="latest"
      role="status"
      :class="['curriculum-answer-result', latest.correct ? 'correct' : '']"
    >
      {{
        latest.verification?.message ||
        (latest.correct ? "数值正确" : "需核对或订正")
      }}
      · {{ latest.helped ? "获得过帮助" : "独立尝试" }}
    </p>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p>
    <div class="library-actions">
      <Button
        :disabled="(!preview && store.task?.readOnly) || busy || !answer.trim()"
        @click="submit"
        >{{ busy ? "保存中…" : "提交作答" }}</Button
      ><Button
        variant="ghost"
        :disabled="(!preview && store.task?.readOnly) || busy"
        @click="ask"
        >我需要提示</Button
      ><Button
        v-if="!preview"
        variant="ghost"
        :disabled="busy || store.task?.readOnly"
        @click.stop="emit('guide', index)"
        >向学习助手提问</Button
      >
    </div>
  </div>
</template>
