<script setup>
import { computed, inject, ref, watch } from "vue";
import { ArrowUpRight, Check, Plus, Send } from "lucide-vue-next";
import { useLearning } from "@/store.js";

import { questions } from "@/data.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import ModelHistory from "@/components/ModelHistory.vue";
const store = useLearning(),
  notify = inject("notify"),
  studentOpen = ref(false),
  supplement = ref(false),
  supplementBusy = ref(false),
  draft = ref(store.record?.feedback || ""),
  supplementText = ref("回看等式两边共同变化的过程，再完成独立检查。"),
  error = ref("");
const independent = computed(
  () =>
    store.record?.attempts.filter((item) => item.correct && !item.helped && store.task?.questions[item.question]?.kind!=='practice')
      .length || 0,
);
const records = computed(() => store.data.studentRecords?.[store.task?.id] || []);
const coveredHelpIds = ref([]);
const visibleHelps = computed(() => (store.record?.helps || []).filter(item => !coveredHelpIds.value.includes(item.id)));
const submittedCount = computed(() => records.value.filter((record) => record.completed).length);
const independentCount = computed(() => records.value.reduce((sum, record) => sum + record.attempts.filter((item) => item.correct && !item.helped && store.task?.questions[item.question]?.kind!=='practice').length, 0));
watch(() => store.data.activeStudentId, () => { draft.value = store.record?.feedback || ""; });
async function feedback() {
  try {
    await store.saveFeedback(draft.value);
    notify("反馈已发送到学生结果页");
  } catch (problem) {
    error.value = problem.message;
  }
}
function openStudent(id) {
  store.selectStudent(id);
  draft.value = store.record?.feedback || "";
  studentOpen.value = true;
}
async function arrange() {
  if (!supplementText.value.trim()) return notify("请填写补充内容");
  if (supplementBusy.value) return;
  supplementBusy.value = true;
  store.data.supplements.push({
    id: crypto.randomUUID(),
    taskId: store.task.id,
    content: supplementText.value,
    createdAt: new Date().toISOString(),
  });
  store.touch();
  if (await store.save()) {
    supplement.value = false;
    notify("补充学习已安排");
  } else {
    error.value = store.saveError;
  }
  supplementBusy.value = false;
}
</script>
<template>
  <PageHeading title="学情反馈"
    ><RouteButton route="class" secondary>返回班级</RouteButton
    ><Button v-if="store.task" @click="supplement = true"
      ><Plus />安排补充学习</Button
    ></PageHeading
  ><template v-if="store.task"
    ><div class="back-line">
      <span
        >{{ store.task.title }} ·
        {{ new Date(store.task.publishedAt).toLocaleString("zh-CN") }}</span
      >
    </div>
    <div class="insight-summary">
      <div>
        <span>参与学生</span><strong>{{ records.length }}<small>人</small></strong>
      </div>
      <div>
        <span>已经提交</span
        ><strong>{{ submittedCount }}<small>/ {{ records.length }}</small></strong>
      </div>
      <div>
        <span>独立检查正确</span
        ><strong>{{ independentCount }}<small>次</small></strong>
      </div>
      <div class="summary-context"><Status>本次操作记录</Status></div>
    </div>
    <Surface class="student-table"
      ><SectionHeading title="学生学习过程" />
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>学生</th>
              <th>学习进度</th>
              <th>获得的帮助</th>
              <th>独立检查</th>
              <th><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="student in store.students" :key="student.id" :class="{ 'is-selected': store.data.activeStudentId === student.id }">
              <td>
                <span class="student-name avatar-0"
                  ><span>{{ student.initials }}</span>{{ student.name }}</span
                >
              </td>
              <td>
                <div class="table-progress">
                  <span>{{ student.status }}</span
                  ><Progress
                    :model-value="student.progress"
                    :aria-label="`${student.name}学习进度`"
                  />
                </div>
              </td>
              <td>{{ student.help }}</td>
              <td>
                <Status :tone="student.result === '独立检查正确' ? 'green' : 'neutral'">{{
                  student.result
                }}</Status>
              </td>
              <td>
                <Button variant="ghost" @click="openStudent(student.id)"
                  >查看过程<ArrowUpRight
                /></Button>
              </td>
            </tr>
          </tbody>
        </table></div
    ></Surface>
    <div v-if="store.record" class="two-column insight-detail">
      <Surface
        ><SectionHeading title="作答概况" />
        <h3>
          {{ store.record.attempts.length }} 次尝试 ·
          {{ store.record.repairs.length }} 次补救
        </h3>
        <p v-if="store.record.observation" class="preserve-lines">
          {{ store.record.observation }}
        </p>
        <RouteButton route="cases" secondary>查找教学案例</RouteButton></Surface
      ><Surface
        ><SectionHeading :title="`给${store.record.studentName || '学生'}的反馈`" /><Textarea
          v-model="draft"
          aria-label="教师反馈"
        />
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="paper-actions">
          <Button @click="feedback"><Check />确认并保存</Button>
        </div></Surface
      >
    </div>
    <Surface v-else class="records-surface"><SectionHeading title="学生学习过程" /><p>班级还没有学生。先添加学生账号，再发布学习任务。</p></Surface>
    <AppDialog
      v-model:open="studentOpen"
      :title="`${store.record?.studentName || '学生'}的学习过程`"
      content-class="student-detail-dialog"
      ><div class="attempt-timeline">
        <section v-if="store.record">
          <h3>自己的解释</h3>
          <p>{{ store.record.observation || "尚未填写" }}</p>
        </section>
        <section v-for="attempt in store.record?.attempts || []" :key="attempt.id">
          <small>{{
            new Date(attempt.createdAt).toLocaleString("zh-CN")
          }}</small>
          <h3>
            {{
              (store.task.questions || questions)[attempt.question]?.equation
            }}
            → {{ attempt.answer }}
          </h3>
          <p>{{ attempt.reason || "未填写解释" }}</p>
          <Status>{{ attempt.helped ? "获得帮助" : "独立作答" }}</Status
          ><Status :tone="attempt.correct ? 'green' : 'amber'">{{
            attempt.verification?.status === "unverified" ? "需核对" : attempt.correct ? "数值正确" : "需订正"
          }}</Status>
        </section>
        <ModelHistory :record-id="store.record?.id" @covered-helps="coveredHelpIds = $event" />
        <section v-for="help in visibleHelps" :key="help.id">
          <h3>{{ help.kind }}</h3>
          <p>{{ help.message }}</p>
          <img
            v-if="help.image"
            :src="help.image"
            alt="求助原始题图"
            class="upload-thumbnail"
          />
          <small>{{ new Date(help.createdAt).toLocaleString("zh-CN") }}</small>
        </section>
        <section v-for="repair in store.record?.repairs || []" :key="repair.id">
          <h3>补救变式 z + 2 = 9 → {{ repair.answer }}</h3>
          <p>{{ repair.reason }}</p>
          <Status :tone="repair.correct ? 'green' : 'amber'">{{
            repair.verification?.status === "unverified" ? "需核对" : repair.correct ? "数值正确" : "需订正"
          }}</Status>
        </section>
        <p v-if="store.record && !store.record.attempts.length && !store.record.helps.length">
          尚无作答和求助记录
        </p>
      </div></AppDialog
    ><AppDialog v-model:open="supplement" title="安排补充学习"
      ><label class="field-label" for="supplement-content">补充内容</label
      ><Textarea id="supplement-content" v-model="supplementText" /><Button
        :disabled="supplementBusy"
        @click="arrange"
        >{{ supplementBusy ? "保存中…" : "确认安排" }}<Send /></Button></AppDialog></template
  ><TaskEmpty v-else />
</template>
