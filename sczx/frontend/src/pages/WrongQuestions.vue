<script setup>
import { computed, ref, onMounted } from "vue";
import { Plus, ArrowUpRight, Search, NotebookPen } from "@/components/app/icons.js";
import { wrongApi, wrongStatuses } from "@/services/wrongs.js";
import WrongCapture from "@/components/WrongCapture.vue";
import { navigate } from "@/lib/navigation.js";
const items = ref([]),
  options = ref({ knowledge: [], reasons: [] }),
  status = ref("all"),
  subject = ref(""),
  knowledge = ref(""),
  cause = ref(""),
  search = ref(""),
  loading = ref(true),
  error = ref(""),
  open = ref(false);
async function load() {
  loading.value = true;
  error.value = "";
  try {
    [items.value, options.value] = await Promise.all([
      wrongApi.list(),
      wrongApi.options(),
    ]);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
const filtered = computed(() =>
  items.value.filter(
    (i) =>
      (status.value === "all" ||
        (status.value === "done"
          ? i.status === "retest_passed"
          : i.status !== "retest_passed")) &&
      (!subject.value || (i.details.subject || "数学") === subject.value) &&
      (!knowledge.value || i.details.knowledgeIds?.includes(knowledge.value)) &&
      (!cause.value || i.details.cause === cause.value) &&
      (!search.value || (i.prompt + i.answer).includes(search.value)),
  ),
);
const knowledgeName = (i) =>
  options.value.knowledge
    .filter((p) => i.details.knowledgeIds?.includes(p.id))
    .map((p) => p.name)
    .join(" 　 ");
const studentStatus=value=>({pending:'待订正',learning:'订正中',awaiting_retest:'再试一题',retest_passed:'已复测',retest_failed:'继续订正',needs_review:'请老师核对'})[value]||wrongStatuses[value];
function saved(item) {
  open.value = false;
  load();
  navigate("repair?wrong=" + item.id);
}
onMounted(load);
</script>
<template>
  <PageHeading title="我的错题"
    ><AppButton @click="open = true"><Plus />录入错题</AppButton></PageHeading
  >
  <div class="wrong-workspace-toolbar">
    <AppTabs
      v-model="status"
      :items="[
        { value: 'all', label: `全部 ${items.length}` },
        { value: 'pending', label: '待订正' },
        { value: 'done', label: '已复测' },
      ]"
    />
    <div class="wrong-filters">
      <Input
        v-model="search"
        aria-label="搜索错题"
        placeholder="搜索题目"
      /><AppDisclosure class="student-filter-disclosure"><template #title>筛选<span v-if="subject||knowledge||cause"> 　 已筛选</span></template><div class="student-filter-fields"><NativeSelect v-model="subject" aria-label="筛选学科">
        <option value="">全部学科</option>
        <option
          v-for="s in [
            ...new Set(items.map((i) => i.details.subject || '数学')),
          ]"
          :key="s"
        >
          {{ s }}
        </option></NativeSelect
      ><NativeSelect v-model="knowledge" aria-label="筛选知识点">
        <option value="">全部知识点</option>
        <option v-for="p in options.knowledge" :key="p.id" :value="p.id">
          {{ p.name }}
        </option></NativeSelect
      ><NativeSelect v-model="cause" aria-label="筛选错因">
        <option value="">全部错因</option>
        <option v-for="r in options.reasons" :key="r">{{ r }}</option>
      </NativeSelect></div></AppDisclosure>
    </div>
  </div>
  <ElSkeleton v-if="loading" animated :rows="3" aria-label="正在读取错题…"/>
  <Surface v-else-if="error"
    ><AppAlert type="error" role="alert">{{ error }}</AppAlert>
    <AppButton @click="load">重新读取</AppButton></Surface
  >
  <div v-else-if="filtered.length" class="wrong-library">
    <button
      v-for="item in filtered"
      :key="item.id"
      class="wrong-library-row"
      @click="navigate('repair?wrong=' + item.id)"
    >
      <div class="wrong-row-art">
        <AppImage v-if="item.image" :src="item.image" alt="原题" /><NotebookPen
          v-else
        />
      </div>
      <div class="wrong-row-main">
        <div class="question-meta">
          <span>{{ item.details.subject || "数学" }}</span
          ><span>{{
            knowledgeName(item) ||
            { course: "课程作答", manual: "个人录入", image: "题图识别" }[
              item.source
            ]
          }}</span>
        </div>
        <h2>{{ item.prompt }}</h2>
        <p class="wrong-original">
          原作答 <strong>{{ item.answer || "未填写" }}</strong
          ><span v-if="item.details.causeConfirmed">{{
            item.details.cause
          }}</span>
        </p>
      </div>
      <div class="wrong-row-end">
        <Status :tone="item.status === 'retest_passed' ? 'green' : 'amber'">{{
          studentStatus(item.status)
        }}</Status
        ><ArrowUpRight :size="19" />
      </div>
    </button>
  </div>
  <Surface v-else
    ><AppEmpty class="empty-state"><NotebookPen :size="32" /><h2>{{ items.length ? "没有符合条件的错题" : "记录第一道错题" }}</h2><AppButton v-if="!items.length" @click="open = true">录入错题</AppButton></AppEmpty></Surface
  >
  <AppDialog
    v-model:open="open"
    title="录入错题"
    content-class="wrong-capture-dialog"
    ><WrongCapture v-if="open" :options="options" @saved="saved"
  /></AppDialog>
</template>
