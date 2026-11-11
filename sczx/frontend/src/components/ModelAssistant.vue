<script setup>
import { computed, ref, watch, nextTick, onBeforeUnmount } from "vue";
import {
  ImagePlus,
  Send,
  Sparkles,
  RotateCcw,
  Square,
  ArrowUpRight,
} from "lucide-vue-next";
import { useLearning } from "@/store.js";
import { modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import ModelResult from "./ModelResult.vue";
import SpeechInput from "./SpeechInput.vue";
const props = defineProps({
  question: { default: null },
  blockId: { default: null },
  compact: Boolean,
});
const emit = defineEmits(["help"]);
const store = useLearning();
const recordId = computed(() => store.record?.id),
  scope = computed(
    () => `${recordId.value}:${props.question}:${props.blockId}`,
  );
const draftKey = computed(() =>
  props.question === null
    ? `assistantBlock-${props.blockId || "lesson"}`
    : `assistantQuestion-${props.question}`,
);
const strategies = [
  ["hint", "给我提示"],
  ["example", "举个例子"],
  ["rephrase", "换种讲法"],
  ["foundation", "补基础"],
];
const strategy = ref("hint"),
  prompt = ref(""),
  file = ref(null),
  uploading = ref(false),
  uploadError = ref(""),
  recognized = ref(""),
  equation = ref(""),
  ocrId = ref(null),
  parentId = ref(null),
  history = ref([]),
  restoring = ref(false);
let interaction = 0;
const submissionKeys = new Map(),
  pendingAsset = ref(null);
function createStable(payload) {
  const signature = JSON.stringify(payload);
  if (!submissionKeys.has(signature))
    submissionKeys.set(signature, crypto.randomUUID());
  return create({ ...payload, requestKey: submissionKeys.get(signature) });
}
const matches = (value) =>
  value.recordId === recordId.value &&
  (value.question ?? null) === props.question &&
  (value.blockId ?? null) === (props.blockId ?? null);
const { job, busy, error, create, open, retry } = useModelJob(async (value) => {
  if (!matches(value)) return;
  if (
    value.status === "failed" &&
    value.error?.includes("已移出班级") &&
    store.task
  )
    store.task.readOnly = true;
  if (value.status === "succeeded" && value.capability === "ocr") {
    pendingAsset.value = null;
    if (store.record && !store.task?.readOnly)
      delete store.record.drafts[draftKey.value + "-upload"];
    const saved = store.record?.drafts[`ocr-${value.id}`];
    recognized.value =
      typeof saved === "string" ? saved : (saved?.text ?? value.result.text);
    equation.value = saved?.equation ?? value.result.equation ?? "";
    ocrId.value = value.id;
  }
  if (value.status === "succeeded" && value.capability === "text") {
    parentId.value = value.input?.guidance ? value.id : null;
    if (value.input?.ocrJobId) {
      ocrId.value = value.input.ocrJobId;
      recognized.value = value.input.recognizedText || "";
      equation.value = value.input.confirmedEquation || "";
    }
    const expected = scope.value;
    await store.refreshRecord();
    if (expected !== scope.value) return;
    const rows = await modelApi.list(recordId.value);
    if (expected === scope.value)
      history.value = rows
        .filter(matches)
        .filter((x) => x.strategy)
        .slice(0, 8);
  }
});
const earlier = computed(() =>
  history.value
    .filter((item) => item.id !== job.value?.id)
    .slice(0, 4)
    .reverse(),
);
watch(
  scope,
  async (_, __, onCleanup) => {
    const version = ++interaction;
    let live = true;
    onCleanup(() => (live = false));
    restoring.value = true;
    await open(null);
    pendingAsset.value =
      store.record?.drafts[draftKey.value + "-upload"] || null;
    ocrId.value = null;
    parentId.value = null;
    recognized.value = "";
    equation.value = "";
    file.value = null;
    history.value = [];
    uploadError.value = "";
    uploading.value = false;
    prompt.value =
      store.record?.drafts[draftKey.value] ??
      (props.question === null &&
      props.blockId === store.task?.snapshot?.blocks?.[0]?.id
        ? store.record?.drafts.assistant
        : undefined) ??
      "";
    await nextTick();
    restoring.value = false;
    if (!recordId.value) return;
    try {
      const rows = await modelApi.list(recordId.value);
      if (!live || version !== interaction) return;
      const related = rows.filter(matches);
      history.value = related.filter((x) => x.strategy).slice(0, 8);
      const latest = related.find((x) =>
        ["text", "ocr"].includes(x.capability),
      );
      if (latest) {
        await open(latest);
        if (!live || version !== interaction) return;
        parentId.value =
          latest.status === "succeeded" && latest.strategy ? latest.id : null;
      }
    } catch (e) {
      if (live) uploadError.value = e.message;
    }
  },
  { immediate: true, flush: "sync" },
);
watch(prompt, (value) => {
  if (!restoring.value && store.record && !store.task?.readOnly) {
    store.record.drafts[draftKey.value] = value;
    store.touch();
  }
});
watch([recognized, equation], () => {
  if (
    !restoring.value &&
    store.record &&
    ocrId.value &&
    !store.task?.readOnly &&
    job.value?.capability === "ocr"
  ) {
    store.record.drafts[`ocr-${ocrId.value}`] = {
      text: recognized.value,
      equation: equation.value,
    };
    store.touch();
  }
});
async function send(choice = strategy.value, confirmImage = false) {
  if (busy.value || uploading.value || store.task?.readOnly) return;
  const expected = scope.value,
    targetRecord = recordId.value,
    targetQuestion = props.question,
    targetBlock = props.blockId,
    selected = file.value;
  interaction++;
  uploadError.value = "";
  const text = prompt.value.trim() || (choice === "try" ? "我想自己试试" : "");
  if (!selected && !pendingAsset.value && !text) {
    uploadError.value = "请写下问题或对追问的回应。";
    return;
  }
  if (!(await store.save())) {
    uploadError.value = store.saveError;
    return;
  }
  if (scope.value !== expected) return;
  if (selected) {
    uploading.value = true;
    try {
      const asset = await modelApi.upload(selected);
      if (scope.value !== expected) return;
      file.value = null;
      pendingAsset.value = { id: asset.id };
      store.record.drafts[draftKey.value + "-upload"] = { id: asset.id };
      store.touch();
      await createStable({
        capability: "ocr",
        recordId: targetRecord,
        fileId: asset.id,
        data: { question: targetQuestion, blockId: targetBlock, prompt: text },
      });
    } catch (e) {
      if (scope.value === expected) uploadError.value = e.message;
    } finally {
      if (scope.value === expected) uploading.value = false;
    }
    return;
  }
  if (pendingAsset.value && job.value?.capability !== "ocr") {
    await createStable({
      capability: "ocr",
      recordId: targetRecord,
      fileId: pendingAsset.value.id,
      data: { question: targetQuestion, blockId: targetBlock, prompt: text },
    });
    return;
  }
  const data = {
    guidance: true,
    prompt: text,
    strategy: choice,
    question: targetQuestion,
    blockId: targetBlock,
    parentJobId: parentId.value,
  };
  if (job.value?.capability === "ocr" && !confirmImage) {
    uploadError.value = "请先核对题目并确认。";
    return;
  }
  if (ocrId.value) {
    const confirmed = [
      recognized.value,
      equation.value && !recognized.value.includes(equation.value)
        ? equation.value
        : "",
    ]
      .filter(Boolean)
      .join("\n");
    if (!confirmed.trim()) {
      uploadError.value = "请填写确认后的题目。";
      return;
    }
    Object.assign(data, {
      ocrJobId: ocrId.value,
      confirmed: true,
      recognizedText: confirmed,
      confirmedEquation: equation.value,
    });
  }
  if (choice !== "try") emit("help");
  await createStable({ capability: "text", recordId: targetRecord, data });
}
async function stop() {
  if (job.value && busy.value) {
    try {
      await modelApi.stop(job.value.id);
    } catch (e) {
      uploadError.value = e.message;
      return;
    }
  }
  await useTextOnly();
  prompt.value = "";
}
async function useTextOnly() {
  pendingAsset.value = null;
  file.value = null;
  ocrId.value = null;
  recognized.value = "";
  equation.value = "";
  parentId.value = null;
  if (store.record && !store.task?.readOnly) {
    delete store.record.drafts[draftKey.value + "-upload"];
    store.touch();
  }
  await open(null);
}
function chooseFile(event) {
  parentId.value = null;
  pendingAsset.value = null;
  delete store.record?.drafts[draftKey.value + "-upload"];
  file.value = event.target.files?.[0] || null;
  ocrId.value = null;
  recognized.value = "";
  equation.value = "";
}
onBeforeUnmount(() => interaction++);
</script>
<template>
  <aside
    class="ai-assistant tutoring-assistant"
    :class="{ 'is-compact': compact }"
  >
    <header class="ai-assistant-heading">

      <h3>学习助手</h3>
      <Button
        v-if="job"
        variant="ghost"
        size="icon-sm"
        :aria-label="busy ? '停止本轮指导' : '开始新一轮指导'"
        @click="stop"
        ><Square v-if="busy" :size="14" /><RotateCcw v-else :size="14"
      /></Button>
    </header>
    <p
      v-if="job?.input?.context?.focus === 'confirmed_image'"
      class="tutoring-context"
    >
      题图 · {{ job.input.context.question.equation || "已确认题目" }}
    </p>
    <p v-else-if="blockId" class="tutoring-context">
      {{ store.task?.snapshot?.blocks?.find((b) => b.id === blockId)?.title }}
    </p>
    <details class="study-disclosure tutoring-strategy-picker"><summary>指导方式 · {{strategies.find(s=>s[0]===strategy)?.[1]}}</summary><div class="tutoring-strategies" aria-label="指导方式">
      <Button
        v-for="[value, label] in strategies"
        :key="value"
        :variant="strategy === value ? 'secondary' : 'ghost'"
        :aria-pressed="strategy === value"
        :disabled="busy || store.task?.readOnly"
        @click="strategy = value"
        >{{ label }}</Button
      >
    </div></details>
    <details v-if="earlier.length" class="tutoring-history">
      <summary>前面的指导 · {{ earlier.length }}</summary>
      <article v-for="item in earlier" :key="item.id">
        <p class="tutoring-response">{{ item.prompt }}</p>
        <ModelResult :job="item" :can-retry="false" />
      </article>
    </details>
    <p v-if="job?.prompt" class="tutoring-response">{{ job.prompt }}</p>
    <ModelResult
      :job="job"
      :busy="busy"
      :can-retry="!store.task?.readOnly"
      @retry="retry"
    />
    <template
      v-if="
        job?.capability === 'ocr' &&
        job.status === 'succeeded' &&
        ocrId === job.id
      "
      ><img
        :src="`/api/files/${job.fileId}`"
        class="ai-original"
        alt="本轮识别的原始题图"
      />
      <p v-if="job.result.uncertainties?.length" class="inline-notice">
        待核对：{{ job.result.uncertainties.join("；") }}
      </p>
      <label class="field-label" for="confirmed-question"
        >识别文字<Textarea
          id="confirmed-question"
          :maxlength="6000"
          v-model="recognized"
          :disabled="store.task?.readOnly" /></label
      ><label class="field-label" for="confirmed-equation"
        >数学表达式<Textarea
          id="confirmed-equation"
          :maxlength="500"
          v-model="equation"
          :disabled="store.task?.readOnly" /></label
      ><Button
        :disabled="busy || store.task?.readOnly || !recognized.trim()"
        @click="send(strategy, true)"
        >确认题目并获取指导</Button
      ></template
    >
    <div class="ai-compose">
      <label class="sr-only" for="learning-question"
        >向学习助手提问或回答追问</label
      ><Textarea
        id="learning-question"
        :maxlength="3000"
        v-model="prompt"
        :disabled="store.task?.readOnly"
        :placeholder="
          parentId ? '写下你对追问的回答…' : '写下还没想明白的地方…'
        "
      />
      <div class="ai-compose-actions">
        <SpeechInput
          :context-key="scope"
          :disabled="busy || uploading || store.task?.readOnly"
          @text="prompt = [prompt.trim(), $event].filter(Boolean).join(' ')"
        /><label class="image-input"
          ><ImagePlus :size="18" /><span class="sr-only">选择题图</span
          ><input
            type="file"
            accept="image/*"
            :disabled="busy || uploading || store.task?.readOnly"
            @change="chooseFile" /></label
        ><span class="ai-file-name">{{ file?.name || "" }}</span
        ><Button
          :disabled="busy || uploading || !recordId || store.task?.readOnly"
          @click="send()"
          ><Send :size="15" />{{
            uploading
              ? "上传中…"
              : busy
                ? "处理中…"
                : file || pendingAsset
                  ? "识别题图"
                  : "发送"
          }}</Button
        >
      </div>
      <Button
        v-if="parentId"
        variant="outline"
        :disabled="busy || store.task?.readOnly || !prompt.trim()"
        @click="send('continue')"
        >回答后继续指导</Button
      >
    </div>
    <footer class="tutoring-footer">
      <Button
        v-if="
          (job?.capability === 'ocr' && job.status === 'failed') ||
          (pendingAsset && error)
        "
        variant="ghost"
        @click="useTextOnly"
        >改用文字提问</Button
      ><Button
        variant="ghost"
        :disabled="busy || store.task?.readOnly"
        @click="send('try')"
        >我想自己试试<ArrowUpRight :size="14" /></Button
      ><RouteButton v-if="job?.strategy === 'try'" route="check" secondary
        >回到原题作答</RouteButton
      >
    </footer>
    <p v-if="uploadError || error" class="form-error" role="alert">
      {{ uploadError || error }}
    </p>
  </aside>
</template>
