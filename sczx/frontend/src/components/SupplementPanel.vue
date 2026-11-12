<script setup>
import { ref, watch, computed } from "vue";
import { useLearning } from "@/store.js";
import { teachingApi, deadlineText } from "@/services/teaching.js";
import { Plus, Send } from "lucide-vue-next";
const props = defineProps({ taskId: String, teacher: Boolean });
const store = useLearning(),
  items = ref([]),
  error = ref(""),
  busy = ref(false),
  dialog = ref(false),
  kind = ref("learning"),
  content = ref(""),
  dueDate = ref(""),
  scope = ref("all"),
  studentId = ref(""),
  responses = ref({}),
  feedbacks = ref({});
const requestKey = ref(crypto.randomUUID());
let generation = 0;
watch(dialog, (value) => {
  if (value) requestKey.value = crypto.randomUUID();
});
const labels = {
  note: "补充说明",
  correction: "订正要求",
  learning: "补充讲解",
  foundation:"前置知识复习",
  retest:"独立复测",
};
const students = computed(() =>
  (store.data.studentRecords?.[props.taskId] || []).filter(
    (r) => r.memberActive !== false,
  ),
);
async function load() {
  const g = ++generation;
  items.value = [];
  error.value = "";
  try {
    if (props.taskId) {
      const value = await teachingApi.supplements(props.taskId);
      if (g === generation) items.value = value;
    }
  } catch (e) {
    if (g === generation) error.value = e.message;
  }
}
watch(() => props.taskId, load, { immediate: true });
async function arrange() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await teachingApi.arrange(props.taskId, {
      requestKey: requestKey.value,
      kind: kind.value,
      content: content.value,
      dueDate: dueDate.value,
      studentIds: scope.value === "all" ? null : [studentId.value],
    });
    dialog.value = false;
    content.value = "";
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function act(item, action) {
  busy.value = true;
  error.value = "";
  try {
    await teachingApi.act(item.id, action, responses.value[item.id] || "");
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function cancel(item) {
  if (!confirm("取消后学生不能开始这项安排，历史记录保留。继续？")) return;
  try {
    await teachingApi.cancel(item.id);
    await load();
  } catch (e) {
    error.value = e.message;
  }
}
async function feedback(item, rec) {
  try {
    await teachingApi.feedback(
      item.id,
      rec.studentId,
      feedbacks.value[item.id + rec.studentId] || rec.feedback,
    );
    await load();
  } catch (e) {
    error.value = e.message;
  }
}
</script>
<template>
  <section class="supplement-panel">
    <header>
      <h2>补充与订正</h2>
      <Button v-if="teacher" variant="outline" @click="dialog = true"
        ><Plus :size="15" />新增安排</Button
      >
    </header>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <article v-for="item in items" :key="item.id">
      <div>
        <Status>{{ labels[item.kind] }}</Status
        ><Status v-if="item.status === 'cancelled'">已取消</Status
        ><span>{{ item.teacherName }} 　 {{ item.className }}</span
        ><time>{{ deadlineText(item.dueAt) }}</time>
      </div>
      <p class="preserve-lines">{{ item.content }}</p><p v-if="item.case">参考：{{item.case.title}} 　 v{{item.case.version}} 　 {{item.case.source}}<RouteButton :route="'case-detail?caseId='+item.case.id+'&versionId='+item.case.versionId" secondary>案例原文</RouteButton></p>
      <template v-if="!teacher&&item.recipients[0]?.outcome"><p>{{item.recipients[0].outcome.label}}</p><RouteButton v-if="item.recipients[0].outcome.target.wrongId" :route="'repair?wrong='+item.recipients[0].outcome.target.wrongId" secondary>进入原错题</RouteButton><RouteButton v-else :route="item.recipients[0].outcome.target.kind+'?task='+item.recipients[0].outcome.target.taskId" secondary>进入安排内容</RouteButton></template>
      <details v-if="teacher" class="teacher-supplement-recipients"><summary>学生进度 　 {{ item.recipients.filter(r=>r.completedAt).length }} / {{ item.recipients.length }}</summary><div
          v-for="rec in item.recipients"
          :key="rec.studentId"
          class="supplement-recipient"
        >
          <strong>{{ rec.studentName }}</strong
          ><Status>{{ rec.status }}</Status>
          <p v-if="rec.outcome">{{rec.outcome.label}} 　 {{rec.outcome.newAttempts}} 次新作答<span v-if="rec.outcome.needsHelp"> 　 仍需帮助或核对</span></p><p v-if="rec.response">{{ rec.response }}</p>
          <template v-if="rec.completedAt"
            ><Textarea
              v-model="feedbacks[item.id + rec.studentId]"
              :placeholder="rec.feedback || '填写后续反馈'"
              :aria-label="'补充反馈' + rec.studentName"
            /><Button variant="outline" @click="feedback(item, rec)"
              >发送反馈</Button
            ></template
          >
        </div>
        <Button
          v-if="
            item.status !== 'cancelled' &&
            !item.recipients.some((r) => r.startedAt)
          "
          variant="ghost"
          @click="cancel(item)"
          >取消安排</Button
        ></details
      ><template v-else-if="item.kind !== 'note' && item.status !== 'cancelled'"
        ><template v-if="item.recipients[0]?.completedAt"
          ><Status tone="green">学习说明已提交</Status>
          <p>{{ item.recipients[0].response }}</p></template
        ><template v-else
          ><Status v-if="item.recipients[0]?.status === '已逾期'" tone="amber"
            >已逾期</Status
          ><Button
            v-if="!item.recipients[0]?.startedAt"
            variant="outline"
            :disabled="busy || store.task?.readOnly"
            @click="act(item, 'start')"
            >开始处理</Button
          ><label v-else class="field-label"
            >学习或订正说明<Textarea
              v-model="responses[item.id]"
              :disabled="store.task?.readOnly"
            /><Button
              :disabled="
                busy || store.task?.readOnly || !responses[item.id]?.trim()
              "
              @click="act(item, 'submit')"
              ><Send :size="15" />提交说明</Button
            ></label
          ></template
        >
        <p v-if="item.recipients[0]?.feedback">
          教师反馈：{{ item.recipients[0].feedback }}
        </p></template
      >
    </article>
    <p v-if="!items.length" class="muted">暂无补充安排</p>
    <AppDialog v-model:open="dialog" title="补充与订正"
      ><form class="supplement-form" @submit.prevent="arrange">
        <label class="field-label"
          >类型<AppSelect
            v-model="kind"
            label="安排类型"
            :options="
              Object.entries(labels).filter(([key])=>['note','correction','learning'].includes(key)).map(([value, label]) => ({ value, label }))
            " /></label
        ><label class="field-label"
          >内容<Textarea v-model="content" required /></label
        ><label class="field-label"
          >接收范围<AppSelect
            v-model="scope"
            label="接收范围"
            :options="[
              { value: 'all', label: '全班已分配学生' },
              { value: 'one', label: '指定学生' },
            ]" /></label
        ><AppSelect
          v-if="scope === 'one'"
          v-model="studentId"
          label="选择学生"
          :options="
            students.map((s) => ({ value: s.studentId, label: s.studentName }))
          "
        /><label class="field-label"
          >截止日期<Input type="date" v-model="dueDate"
        /></label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <Button
          type="submit"
          :disabled="busy || !content.trim() || (scope === 'one' && !studentId)"
          >确认安排</Button
        >
      </form></AppDialog
    >
  </section>
</template>
