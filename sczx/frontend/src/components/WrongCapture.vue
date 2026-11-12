<script setup>
import SubjectFields from "@/components/SubjectFields.vue";
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { Upload, Crop, ScanText, RotateCcw } from "@/components/app/icons.js";
import { modelApi } from "@/services/models.js";
import { wrongApi } from "@/services/wrongs.js";
import { useModelJob } from "@/lib/useModelJob.js";
import { useLearning } from "@/store.js";
const props = defineProps({
    options: { type: Object, default: () => ({ knowledge: [] }) },
  }),
  emit = defineEmits(["saved"]);
const store = useLearning(),
  key = "sczx-wrong-capture-" + store.user.id;
let saved = {};
try {
  saved = JSON.parse(sessionStorage.getItem(key) || "{}");
} catch {}
const form = ref({
  prompt: "",
  equation: "",
  answer: "",
  reason: "",
  subject: "",
  grade: "",
  knowledgeIds: [],
  fileId: null,
  cropFileId: null,
  ocrJobId: null,
  confirmed: false,
  requestKey: crypto.randomUUID(),
  ...saved,
});
const captureMode = ref(form.value.fileId ? "image" : "text");
const working = ref(false),
  error = ref(""),
  local = ref(""),
  image = ref(null),
  rect = ref({ x: 0, y: 0, w: 100, h: 100 });
const preview = computed(
  () =>
    local.value ||
    (form.value.cropFileId || form.value.fileId
      ? "/api/files/" + (form.value.cropFileId || form.value.fileId)
      : ""),
);
const job = useModelJob((value) => {
  if (value.status === "succeeded" && form.value.ocrAppliedId !== value.id) {
    form.value.ocrAppliedId = value.id;
    form.value.ocrJobId = value.id;
    form.value.prompt = value.result.text;
    form.value.equation = value.result.equation;
    form.value.confirmed = false;
    form.value.answer = value.result.studentAnswer || form.value.answer;
  }
});
if (saved.ocrJobId) job.open({ id: saved.ocrJobId });
watch(form, (v) => sessionStorage.setItem(key, JSON.stringify(v)), {
  deep: true,
});
watch(
  () => job.job.value?.id,
  (id) => {
    if (id) {
      form.value.ocrJobId = id;
      sessionStorage.setItem(key, JSON.stringify(form.value));
    }
  },
);
let generation = 0,
  start = null;
async function upload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const token = ++generation;
  working.value = true;
  error.value = "";
  try {
    if (file.size > 12 * 1024 * 1024) throw new Error("题图不能超过12 MB");
    const asset = await modelApi.upload(file);
    if (token !== generation) return;
    if (local.value) URL.revokeObjectURL(local.value);
    local.value = URL.createObjectURL(file);
    form.value.fileId = asset.id;
    form.value.cropFileId = null;
    form.value.ocrJobId = null;
    form.value.confirmed = false;
    form.value.requestKey = crypto.randomUUID();
    rect.value = { x: 0, y: 0, w: 100, h: 100 };
    await job.open(null);
  } catch (e) {
    error.value = e.message;
  } finally {
    if (token === generation) working.value = false;
  }
}
function point(e) {
  const b = image.value.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(100, ((e.clientX - b.left) * 100) / b.width)),
    y: Math.max(0, Math.min(100, ((e.clientY - b.top) * 100) / b.height)),
  };
}
function down(e) {
  if (working.value || job.busy.value) return;
  start = point(e);
  e.currentTarget.setPointerCapture(e.pointerId);
}
function move(e) {
  if (!start) return;
  const p = point(e);
  rect.value = {
    x: Math.min(start.x, p.x),
    y: Math.min(start.y, p.y),
    w: Math.max(1, Math.abs(p.x - start.x)),
    h: Math.max(1, Math.abs(p.y - start.y)),
  };
}
async function crop() {
  working.value = true;
  error.value = "";
  try {
    if (
      !Object.values(rect.value).every(Number.isFinite) ||
      rect.value.w <= 0 ||
      rect.value.h <= 0 ||
      rect.value.x < 0 ||
      rect.value.y < 0 ||
      rect.value.x + rect.value.w > 100 ||
      rect.value.y + rect.value.h > 100
    )
      throw new Error("裁剪选区超出图片边界");
    const img = new Image();
    img.src = "/api/files/" + form.value.fileId;
    await img.decode();
    const r = rect.value,
      c = document.createElement("canvas");
    c.width = Math.max(1, Math.round((img.naturalWidth * r.w) / 100));
    c.height = Math.max(1, Math.round((img.naturalHeight * r.h) / 100));
    c.getContext("2d").drawImage(
      img,
      (img.naturalWidth * r.x) / 100,
      (img.naturalHeight * r.y) / 100,
      c.width,
      c.height,
      0,
      0,
      c.width,
      c.height,
    );
    const blob = await new Promise((resolve) => c.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("裁剪失败，请重试");
    const file = await modelApi.upload(
      new File([blob], "题目裁剪.png", { type: "image/png" }),
    );
    form.value.cropFileId = file.id;
    form.value.confirmed = false;
    form.value.ocrJobId = null;
    await job.open(null);
    local.value = "";
    rect.value = { x: 0, y: 0, w: 100, h: 100 };
  } catch (e) {
    error.value = e.message;
  } finally {
    working.value = false;
  }
}
async function recognize() {
  await job.create({
    capability: "ocr",
    fileId: form.value.cropFileId || form.value.fileId,
    data: { wrongCapture: true, subject: form.value.subject, grade: form.value.grade },
  });
}
async function save() {
  working.value = true;
  error.value = "";
  try {
    const result = await wrongApi.create(form.value);
    sessionStorage.removeItem(key);
    emit("saved", result);
  } catch (e) {
    error.value = e.message;
  } finally {
    working.value = false;
  }
}
onBeforeUnmount(() => {
  generation++;
  if (local.value) URL.revokeObjectURL(local.value);
});
</script>
<template>
  <AppTabs v-model="captureMode" :items="[{value:'text',label:'输入题目'},{value:'image',label:'上传题图'}]"/>
  <div class="capture-grid" :class="{'capture-text-mode':captureMode==='text'}">
    <section v-if="captureMode==='image'">
      <label class="upload-dropzone"
        ><Upload /><strong>选择原始题图</strong
        ><AppFilePicker aria-label="选择原始题图" accept="image/*" :disabled="working || job.busy.value" @change="upload"/></label>
      <div
        v-if="preview"
        class="crop-preview"
        @pointerdown="down"
        @pointermove="move"
        @pointerup="start = null"
        @pointercancel="start = null"
      >
        <img
          ref="image"
          :src="preview"
          alt="原始题图与选区"
          draggable="false"
        />
        <div
          class="crop-selection"
          :style="{
            left: rect.x + '%',
            top: rect.y + '%',
            width: rect.w + '%',
            height: rect.h + '%',
          }"
        />
      </div>
      <AppDisclosure v-if="form.fileId" class="study-disclosure"><template #title>精确调整裁剪</template><div class="capture-coordinates">
        <label
          v-for="(label, k) in { x: '左', y: '上', w: '宽', h: '高' }"
          :key="k"
          >{{ label }}%<input
            v-model.number="rect[k]"
            :aria-label="'裁剪' + label + '百分比'"
            type="number"
            min="0"
            :max="k === 'w' ? 100 - rect.x : k === 'h' ? 100 - rect.y : 100"
        /></label>
      </div></AppDisclosure>
      <div v-if="form.fileId" class="paper-actions">
        <AppButton
          variant="outline"
          :disabled="working || job.busy.value"
          @click="crop"
          ><Crop />保存裁剪</AppButton
        ><AppButton
          variant="outline"
          :disabled="working || job.busy.value"
          @click="recognize"
          ><ScanText />识别题目</AppButton
        >
      </div>
      <p v-if="working || job.busy.value" role="status">
        {{ working ? "正在保存…" : job.job.value?.step || "正在提交…" }}
      </p>
      <AppAlert type="error" v-if="job.job.value?.status === 'failed'" role="alert">
        {{ job.job.value.error
        }}<AppButton variant="outline" @click="job.retry">重试识别</AppButton>
      </AppAlert>
      <AppAlert type="error" v-if="job.error.value" role="alert">{{ job.error.value }}</AppAlert>
      <ul v-if="job.job.value?.result?.uncertainties?.length">
        <li v-for="t in job.job.value.result.uncertainties" :key="t">
          {{ t }}
        </li>
      </ul>
    </section>
    <form @submit.prevent="save"><SubjectFields v-model:grade="form.grade" v-model:subject="form.subject"/>
      <label class="field-label" for="wrong-prompt">题目内容</label
      ><Textarea
        id="wrong-prompt"
        v-model="form.prompt"
        required
        @update:model-value="form.confirmed = false"
      />
      <label v-if="form.subject==='数学'||form.equation" class="field-label" for="wrong-equation">数学表达式（可选）</label
      ><Input
        v-if="form.subject==='数学'||form.equation" id="wrong-equation"
        v-model="form.equation"
        @update:model-value="form.confirmed = false"
      />
      <AppCheckbox v-if="form.fileId" class="capture-confirm" v-model="form.confirmed" :disabled="!form.ocrJobId || job.job.value?.status !== 'succeeded'">已核对文字、符号，并选定一道题</AppCheckbox>
      <AppDisclosure class="study-disclosure"><template #title>学科与知识点</template><div class="capture-fields">
        <div>
          <label class="field-label" for="wrong-subject">学科</label
          ><Input id="wrong-subject" v-model="form.subject" />
        </div>
        <div>
          <label class="field-label" for="wrong-knowledge">知识点</label
          ><NativeSelect id="wrong-knowledge" v-model="form.knowledgeIds" multiple>
            <option v-for="p in options.knowledge" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </NativeSelect>
        </div>
      </div></AppDisclosure>
      <label class="field-label" for="wrong-answer">原来的答案</label
      ><Input id="wrong-answer" v-model="form.answer" />
      <label class="field-label" for="wrong-reason">原来的解题过程</label
      ><Textarea id="wrong-reason" v-model="form.reason" />
      <AppAlert type="error" v-if="error" role="alert" class="form-error">{{ error }}</AppAlert>
      <AppButton
        type="submit"
        :disabled="
          working ||
          job.busy.value ||
          !form.prompt.trim() ||
          (!!form.fileId && !form.confirmed)
        "
        >保存错题</AppButton
      >
    </form>
  </div>
</template>
