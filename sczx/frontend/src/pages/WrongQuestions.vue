<script setup>
import { computed, inject, ref } from "vue";
import { useLearning } from "@/store.js";

import TaskEmpty from "@/components/TaskEmpty.vue";
import { ArrowUpRight, BookOpen, Check, Plus, Upload } from "lucide-vue-next";
const store = useLearning(),
  notify = inject("notify");
const filter = ref("all"),
  open = ref(false),
  text = ref(""),
  image = ref("");
const isRepaired = (id) =>
  store.record.repairs.some((item) => item.wrongId === id && item.correct);
const filtered = computed(() =>
  store.record.wrongQuestions.filter(
    (item) =>
      filter.value === "all" ||
      (filter.value === "done" ? isRepaired(item.id) : !isRepaired(item.id)),
  ),
);
function upload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    image.value = String(reader.result);
  };
  reader.onerror = () => notify("图片读取失败，请重新选择");
  reader.readAsDataURL(file);
}
function record() {
  try {
    store.addWrong(text.value, image.value);
    open.value = false;
    notify("题目和原图已保存到当前任务");
  } catch (error) {
    notify(error.message);
  }
}
</script>
<template>
  <template v-if="store.task"
    ><PageHeading title="错题帮"
      ><Button
        @click="
          text = '';
          image = '';
          open = true;
        "
        ><Plus />录入一道题</Button
      ></PageHeading
    >
    <div class="wrong-summary">
      <BookOpen :size="27" />
      <div>
        <p>{{ store.record.wrongQuestions.length }} 道错题</p>
      </div>
      <Status
        >{{
          store.record.repairs.filter((item) => item.correct).length
        }}
        次补救完成</Status
      >
    </div>
    <AppTabs
      v-model="filter"
      :items="[
        { value: 'all', label: '全部错题' },
        { value: 'pending', label: '待补救' },
        { value: 'done', label: '已订正' },
      ]" />
    <div v-if="filtered.length" class="wrong-layout">
      <Surface v-for="item in filtered" :key="item.id" class="wrong-question"
        ><div class="question-meta">
          <Status>等式性质</Status><span>来自当前任务 · 演示</span>
        </div>
        <h2>{{ item.prompt }}</h2>
        <img
          v-if="item.image"
          class="uploaded-image"
          :src="item.image"
          alt="本地选择的原始题图" />
        <div class="original-attempt">
          <span>原来的作答</span>
          <div class="math-equation">{{ item.answer || "手动录入" }}</div>
          <p v-if="item.reason" class="preserve-lines">{{ item.reason }}</p>
        </div>
        <div class="paper-actions">
          <RouteButton :route="`repair?wrong=${item.id}&task=${store.task.id}`"
            >开始补救</RouteButton
          ><RouteButton route="result" secondary
            >查看来源任务<ArrowUpRight
          /></RouteButton></div
      ></Surface>
    </div>
    <Surface v-else
      ><div class="empty-state"><h3>这个分类还没有题目</h3></div></Surface
    ><AppDialog
      v-model:open="open"
      title="录入题目"
      content-class="upload-dialog"
      ><label class="upload-dropzone"
        ><Upload :size="26" /><strong>点击选择题图</strong
        ><input type="file" accept="image/*" @change="upload" /></label
      ><img
        v-if="image"
        class="upload-thumbnail"
        :src="image"
        alt="已选择的原始题图" /><label class="field-label" for="wrong-question"
        >题目内容</label
      ><Textarea id="wrong-question" v-model="text" /><Button @click="record"
        >确认录入<Check /></Button></AppDialog></template
  ><TaskEmpty v-else />
</template>
