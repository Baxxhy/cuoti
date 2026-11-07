<script setup>
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useRoute } from "vue-router";
import { motion } from "motion-v";
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
  LoaderCircle,
  RotateCcw,
  Upload,
} from "lucide-vue-next";
import { useLearning } from "@/store.js";
const route = useRoute(),
  store = useLearning(),
  notify = inject("notify");
const issues = computed(() => route.name === "issues"),
  tab = ref("case"),
  source = ref(""),
  title = ref("天平与等式性质"),
  content = ref(
    "先请学生预测，再共同操作。用等式表达两边的变化，追问“同时”和“相同”的意义。学生只记住变号时，回到两边相同运算的完整过程。",
  ),
  reviewed = ref(false),
  fileName = ref(""),
  preview = ref(false),
  resolved = ref(false),
  reply = ref("我们会增加“只改变一边”的对比示例，帮助你观察相等关系。"),
  modal = ref(false),
  retrying = ref(false),
  retried = ref(false);
try {
  const saved = JSON.parse(
    sessionStorage.getItem("shicheng-case-draft") || "null",
  );
  if (saved) {
    source.value = saved.source;
    title.value = saved.title;
    content.value = saved.content;
  }
} catch {
  /* Keep the editable default draft. */
}
function publish() {
  if (!reviewed.value) return notify("请先勾选内容核对确认");
  store.casePublished = true;
  notify("案例已模拟发布到教师案例库");
}
function save() {
  try {
    sessionStorage.setItem(
      "shicheng-case-draft",
      JSON.stringify({
        source: source.value,
        title: title.value,
        content: content.value,
      }),
    );
    notify("当前案例草稿已保存到本次浏览会话");
  } catch {
    notify("保存失败，请检查浏览器存储空间");
  }
}
let timer;
function retry() {
  retrying.value = true;
  timer = window.setTimeout(() => {
    retrying.value = false;
    retried.value = true;
    notify("演示任务重试完成");
  }, 900);
}
onBeforeUnmount(() => window.clearTimeout(timer));
</script>
<template>
  <template v-if="!issues">
    <PageHeading :title="route.name === 'content' ? '课程内容' : '资料与案例'"
      ><Button variant="outline" @click="preview = true"
        ><BookOpen />查看案例预览</Button
      ><Button @click="publish"
        ><Check />{{ store.casePublished ? "更新发布" : "核对并发布" }}</Button
      ></PageHeading
    >
    <div class="content-workflow">
      <span class="workflow-step done"><FileText :size="16" />材料整理</span
      ><ChevronRight :size="14" /><span class="workflow-step current"
        ><FileCheck2 :size="16" />经验核对</span
      ><ChevronRight :size="14" /><span
        :class="['workflow-step', { done: store.casePublished }]"
        ><CheckCircle2 :size="16" />发布应用</span
      ><Status>{{ store.casePublished ? "已模拟发布" : "待核对草稿" }}</Status>
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
            ><Button @click="publish">发布案例<ArrowRight /></Button></div
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
  <template v-else
    ><PageHeading title="反馈与运行" /><Surface
      ><SectionHeading title="内容反馈" />
      <div class="feedback-issue">
        <span class="issue-icon"><CircleAlert :size="21" /></span>
        <div>
          <h3>为什么只改变一边，等式就不成立了？</h3>
          <p>等式性质 · 观察活动</p>
        </div>
        <Status :tone="resolved ? 'green' : 'amber'">{{
          resolved ? "已处理" : "待处理"
        }}</Status
        ><Button variant="outline" @click="modal = true"
          >{{ resolved ? "查看回复" : "处理反馈" }}<ChevronRight
        /></Button></div></Surface
    ><Surface class="runtime-surface"
      ><SectionHeading title="任务运行" />
      <div class="feedback-issue">
        <span class="issue-icon"><RotateCcw :size="21" /></span>
        <div>
          <h3>配套教学内容生成</h3>
          <p>模拟失败</p>
        </div>
        <Status :tone="retried ? 'green' : 'amber'">{{
          retried ? "重试成功" : retrying ? "重试中" : "模拟失败"
        }}</Status
        ><Button
          variant="outline"
          :disabled="retrying || retried"
          @click="retry"
          ><motion.span
            v-if="retrying"
            :animate="{ rotate: 360 }"
            :transition="{ repeat: Infinity, duration: 1, ease: 'linear' }"
            ><LoaderCircle :size="16" /></motion.span
          ><RotateCcw v-else />{{ retried ? "已完成" : "重试任务" }}</Button
        >
      </div></Surface
    ><AppDialog v-model:open="modal" title="回复这次学习中的疑问"
      ><Textarea v-model="reply" aria-label="反馈回复" /><Button
        @click="
          resolved = true;
          modal = false;
          notify('反馈回复已在当前原型中记录');
        "
        >确认处理<Check /></Button></AppDialog
  ></template>
</template>
