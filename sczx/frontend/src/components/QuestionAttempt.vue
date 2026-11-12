<script setup>
import AnswerInput from "@/components/AnswerInput.vue";
import { ref, computed, watch, inject, useId, nextTick } from "vue";
import { useLearning } from "@/store.js";
import { curriculumApi } from "@/services/curriculum.js";
const props = defineProps({
  question: { type: Object, required: true },
  index: { type: Number, required: true },
  preview: Boolean,
});
const emit = defineEmits(["guide", "submitted"]);
const helpOpen=ref(false);
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
    emit("submitted");
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
    ><AnswerInput :question="question"
      :id="'answer-' + fieldId"
      v-model="answer"
      :disabled="(!preview && store.task?.readOnly) || busy"
    /><label :for="'reason-' + fieldId" class="field-label">说明你的思路与依据</label
    ><Textarea
      :id="'reason-' + fieldId"
      v-model="reason"
      :disabled="(!preview && store.task?.readOnly) || busy"
    />
    <AppAlert  v-if="hint" class="inline-notice">{{ hint }}</AppAlert>
    <p
      v-if="latest"
      role="status"
      :class="['curriculum-answer-result', latest.correct ? 'correct' : '']"
    >
      <span v-if="latest.answer!==answer||latest.reason!==reason" class="student-previous-answer">上次作答</span>{{ latest.verification?.status==='unverified'?'需要核对':latest.correct?'答案已核对':'再检查一下' }}
      <span>{{latest.helped?'用过帮助':'独立作答'}}</span><InfoTip v-if="latest.verification?.message" label="查看核对结果">{{latest.verification.message}}</InfoTip>
    </p>
    <AppAlert type="error" v-if="error" role="alert" class="form-error">{{ error }}</AppAlert>
    <div class="library-actions">
      <AppButton
        :disabled="(!preview && store.task?.readOnly) || busy || !answer.trim()"
        @click="submit"
        >{{ busy ? "保存中…" : "提交作答" }}</AppButton
      ><AppButton variant="ghost" :disabled="(!preview&&store.task?.readOnly)||busy" @click="helpOpen=true">需要提示</AppButton>
    </div>
    <AppDialog v-model:open="helpOpen" title="这道题需要帮助吗？"><p class="student-help-consequence">{{preview?'预览不会保存作答或帮助记录。':'获得提示后，本题会记为使用过帮助。'}}</p><div class="student-help-choices"><AppButton :disabled="busy" @click="helpOpen=false;ask()">给我一点提示</AppButton><AppButton v-if="!preview" variant="outline" :disabled="busy" @click="helpOpen=false;emit('guide',index)">向学习助手提问</AppButton></div></AppDialog>
  </div>
</template>
