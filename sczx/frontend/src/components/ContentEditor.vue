<script setup>
import { computed, inject, ref } from "vue";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileCheck2,
  FileText,
  Layers,
  Upload,
} from "lucide-vue-next";
import { useLearning } from "@/store.js";
defineProps({ course: Boolean });
const store = useLearning(),
  notify = inject("notify"),
  tab = ref("case"),
  preview = ref(false),
  busy = ref(false),
  error = ref("");
const source = computed({
  get: () => store.data.caseDraft.source,
  set: (value) => (store.data.caseDraft.source = value),
});
const title = computed({
  get: () => store.data.caseDraft.title,
  set: (value) => (store.data.caseDraft.title = value),
});
const content = computed({
  get: () => store.data.caseDraft.content,
  set: (value) => (store.data.caseDraft.content = value),
});
const reviewed = computed({
  get: () => store.data.caseDraft.reviewed,
  set: (value) => (store.data.caseDraft.reviewed = value),
});
const fileName = computed({
  get: () => store.data.caseDraft.fileName,
  set: (value) => (store.data.caseDraft.fileName = value),
});
async function save() {
  notify((await store.save()) ? "案例草稿已保存" : store.saveError);
}
async function publish() {
  if (busy.value) return;
  if (!reviewed.value || !title.value.trim() || !content.value.trim()) {
    error.value = "请填写案例标题、内容并完成核对。";
    return;
  }
  busy.value = true;
  error.value = "";
  const previous = store.data.publishedCase;
  store.data.publishedCase = {
    ...JSON.parse(JSON.stringify(store.data.caseDraft)),
    publishedAt: new Date().toISOString(),
  };
  store.touch();
  if (await store.save()) notify("案例已发布到教学案例库");
  else {
    store.data.publishedCase = previous;
    error.value = store.saveError;
  }
  busy.value = false;
}
</script>
<template>
  <PageHeading :title="course ? '课程内容' : '资料与案例'"
    ><Button variant="outline" @click="preview = true"
      ><BookOpen />查看案例预览</Button
    ><Button @click="publish" :disabled="busy"
      ><Check />{{
        store.data.publishedCase ? "更新发布" : "核对并发布"
      }}</Button
    ></PageHeading
  >
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <div class="content-workflow">
    <span class="workflow-step done"><FileText :size="16" />材料整理</span
    ><ChevronRight :size="14" /><span class="workflow-step current"
      ><FileCheck2 :size="16" />经验核对</span
    ><ChevronRight :size="14" /><span
      :class="['workflow-step', { done: store.data.publishedCase }]"
      ><CheckCircle2 :size="16" />发布应用</span
    ><Status>{{
      store.data.publishedCase ? "已模拟发布" : "待核对草稿"
    }}</Status>
  </div>
  <div class="content-grid">
    <Surface class="source-material"
      ><div class="section-heading">
        <h2>原始材料</h2>
        <Status tone="amber">自编示例</Status>
      </div>
      <label class="source-upload"
        ><Upload :size="17" /><span>{{ fileName || "选择资料文件" }}</span
        ><input
          type="file"
          accept=".pdf,.docx,.txt,image/*"
          @change="fileName = $event.target.files?.[0]?.name || ''" /></label
      ><label class="field-label" for="source-link">公开资料出处</label
      ><Input
        id="source-link"
        v-model="source"
        placeholder="整理真实材料时填写来源链接"
      />
      <div class="source-document">
        <div class="source-doc-label">
          <FileText :size="15" />团队编写教学片段
        </div>
        <h3>从观察开始，理解共同变化。</h3>
        <p>
          展示相等的两边，让学生预测同时加入相同数量后，天平会怎样变化。先请学生解释，再通过操作验证。
        </p>
        <p class="highlighted-source">
          追问：如果只改变一边，会发生什么？请学生比较两种变化，并用自己的话说明相等关系。
        </p>
        <p>再引导学生将观察写为等式，讨论怎样通过两边的共同运算保持关系。</p>
        <div class="source-page-number">材料示例 · 第 1 页</div>
      </div>
      <InfoTip label="内容来源说明"
        >当前为团队编写材料，正式内容需登记真实作者、原文与使用条件。</InfoTip
      ></Surface
    >
    <Surface class="experience-editor"
      ><AppTabs
        v-model="tab"
        :items="[
          { value: 'case', label: '教学经验' },
          { value: 'lesson', label: '课时关联' },
        ]"
      /><template v-if="tab === 'case'"
        ><label class="field-label" for="case-title">案例标题</label
        ><Input id="case-title" v-model="title" /><label
          class="field-label"
          for="experience-content"
          >引导步骤与调整方式</label
        ><Textarea
          id="experience-content"
          v-model="content"
          class="experience-textarea" />
        <div class="review-checks">
          <div>
            <CheckCircle2 :size="17" /><span>示例数学关系</span
            ><Status tone="green">人工核对</Status>
          </div>
          <div>
            <CircleAlert :size="17" /><span>资料来源</span
            ><Status tone="amber">待正式整理</Status>
          </div>
        </div>
        <label class="review-confirm"
          ><input
            v-model="reviewed"
            type="checkbox"
          />我已核对当前自编示例的内容与标记</label
        >
        <div class="paper-actions">
          <Button variant="outline" @click="save">保存草稿</Button
          ><Button @click="publish" :disabled="busy"
            >发布案例<ArrowRight
          /></Button></div
      ></template>
      <div v-else class="lesson-association">
        <Status tone="blue">七年级数学</Status>
        <h2>一元一次方程 / 等式性质</h2>
        <p>目标：解释两边共同变化的条件，并在新题中应用。</p>
        <div class="association-item">
          <Layers :size="18" /><span>观察、解释、练习与独立检查</span>
        </div>
        <RouteButton route="courses" secondary>查看课程目录</RouteButton>
      </div></Surface
    >
  </div>
  <AppDialog
    v-model:open="preview"
    :title="title"
    content-class="case-preview-dialog"
    ><div class="dialog-copy">{{ content }}</div>
    <InfoTip label="内容来源说明"
      >来源：{{ source || "当前自编示例，待整理真实公开材料。" }}</InfoTip
    ></AppDialog
  >
</template>
