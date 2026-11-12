<script setup>
import ClassAnalytics from "@/components/ClassAnalytics.vue";
import { computed, inject, ref, watch } from "vue";
import { ArrowUpRight, Check, Plus, Send } from "@/components/app/icons.js";
import { useLearning } from "@/store.js";
import { useRoute } from "vue-router";

import { questions } from "@/data.js";
import SupplementPanel from "@/components/SupplementPanel.vue";
import TaskEmpty from "@/components/TaskEmpty.vue";
import { wrongApi } from "@/services/wrongs.js";
import ModelHistory from "@/components/ModelHistory.vue";
const store = useLearning(),
  notify = inject("notify"),
  studentOpen = ref(false),
  studentTab = ref("answers"),
  feedbackSaving = ref(false),
  draft = ref(store.record?.feedback || ""),
  error = ref("");
async function reviewRepair(repair,correct){
 try{await wrongApi.review(repair.wrongId,{attemptId:repair.id,correct,note:'教师在学情页面人工核对'});await store.refreshRecord();notify('人工确认已保存，程序核验原结果保留。')}catch(e){notify(e.message)}
}
const route=useRoute();
const view = ref(route.query.task ? "task" : "overview");
watch(()=>route.query.task, value=>{if(value)view.value="task"});
const independent = computed(()=>store.record?.metrics?.independentCorrectQuestions || 0);
const records = computed(
  () => store.data.studentRecords?.[store.task?.id] || [],
);
const coveredHelpIds = ref([]);
const visibleHelps = computed(() =>
  (store.record?.helps || []).filter(
    (item) => !coveredHelpIds.value.includes(item.id),
  ),
);
const independentCount = computed(()=>store.task?.summary?.metrics?.independentCorrectQuestions || 0);
// Selecting a row updates activeStudentId in the same event that opens the
// dialog. Reset its content without closing the dialog after Vue flushes it.
watch(() => store.data.activeStudentId, () => {
  draft.value = store.record?.feedback || "";
  coveredHelpIds.value = [];
});
watch(() => store.task?.id, () => {
  draft.value = store.record?.feedback || "";
  coveredHelpIds.value = [];
  studentOpen.value = false;
});
async function feedback() {
  if(feedbackSaving.value)return;
  feedbackSaving.value=true;error.value="";
  try {
    await store.saveFeedback(draft.value);
    notify("反馈已发送到学生结果页");
  } catch (problem) {
    error.value = problem.message;
  } finally {feedbackSaving.value=false}
}
function openStudent(id) {
  studentTab.value="answers";error.value="";
  if (!store.selectStudent(id)) return;
  draft.value = store.record?.feedback || "";
  studentOpen.value = true;
}
</script>
<template>
  <PageHeading title="学情反馈"><RouteButton route="class" secondary>返回班级</RouteButton></PageHeading>
  <AppTabs v-model="view" :items="[{value:'overview',label:'班级概览'},{value:'task',label:'任务与反馈'}]"/>
  <ClassAnalytics v-if="view==='overview'"/>
  <template v-else>
<template v-if="store.task"
    ><div class="back-line">
      <span
        >{{ store.task.className }} 　 {{ store.task.title }} 　
        {{ new Date(store.task.publishedAt).toLocaleString("zh-CN") }}</span
      >
    </div>
    <div class="insight-summary teaching-insight-metrics">
      <div
        v-for="(label, key) in {
          assigned: '已分配',
          submitted: '已提交',
          unsubmitted: '未提交',
          feedback: '已反馈',
        }"
        :key="key"
      >
        <span>{{ label }}</span
        ><strong>{{ store.task.summary?.[key] || 0 }}</strong>
      </div>
      <div>
        <span>独立正确题目</span><strong>{{ independentCount }}</strong>
      </div>
    </div>
    <Surface class="student-table"
      ><SectionHeading title="学生学习过程" />
      <div class="table-container">
        <AppTable>
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
            <tr
              v-for="student in store.students"
              :key="student.id"
              :class="{
                'is-selected': store.data.activeStudentId === student.id,
              }"
            >
              <td>
                <span class="student-name avatar-0"
                  ><span>{{ student.initials }}</span
                  >{{ student.name }}</span
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
                <Status
                  :tone="
                    student.result === '独立检查正确' ? 'green' : 'neutral'
                  "
                  >{{ student.result }}</Status
                >
              </td>
              <td>
                <AppButton variant="ghost" @click="openStudent(student.id)"
                  >查看与反馈<ArrowUpRight
                /></AppButton>
              </td>
            </tr>
          </tbody>
        </AppTable></div
    ></Surface>
    <Surface v-if="!store.record" class="records-surface"><p>还没有学生作答记录。</p></Surface>
    <AppDialog
      v-model:open="studentOpen"
      :title="`${store.record?.studentName || '学生'}的学习过程`"
      content-class="student-detail-dialog"
      ><AppTabs v-model="studentTab" :items="[{value:'answers',label:'作答'},{value:'help',label:'求助'},{value:'repairs',label:'补救'},{value:'feedback',label:'教师反馈'}]"/><div v-if="studentTab==='feedback'&&store.record" class="focus-student-feedback"><label class="field-label" for="student-feedback">给{{store.record.studentName||'学生'}}的反馈</label><Textarea id="student-feedback" v-model="draft" :disabled="feedbackSaving"/><AppAlert type="error" v-if="error" class="form-error" role="alert">{{error}}</AppAlert><AppButton :disabled="feedbackSaving" @click="feedback"><Check :size="16"/>{{feedbackSaving?'保存中…':'保存反馈'}}</AppButton></div><div v-else class="attempt-timeline">
        <section v-if="store.record&&studentTab==='answers'"><RouteButton :route="'memory?studentId='+store.record.studentId+'&classId='+store.task.classId" secondary>查看学习记忆</RouteButton>
          <h3 v-if="store.record.observation">自己的解释</h3>
          <p v-if="store.record.observation">{{ store.record.observation }}</p>
        </section>
        <section
          v-for="attempt in studentTab==='answers'?store.record?.attempts || []:[]"
          :key="attempt.id"
        >
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
            attempt.verification?.status === "unverified"
              ? "需核对"
              : attempt.correct
                ? "数值正确"
                : "需订正"
          }}</Status>
        </section>
        <ModelHistory v-if="studentTab==='help'"
          :record-id="store.record?.id"
          @covered-helps="coveredHelpIds = $event"
        />
        <section v-for="help in studentTab==='help'?visibleHelps:[]" :key="help.id">
          <h3>{{ help.kind }}</h3>
          <p>{{ help.message }}</p>
          <AppImage
            v-if="help.image"
            :src="help.image"
            alt="求助原始题图"
            class="upload-thumbnail"
          />
          <small>{{ new Date(help.createdAt).toLocaleString("zh-CN") }}</small>
        </section>
        <section v-for="repair in studentTab==='repairs'?store.record?.repairs || []:[]" :key="repair.id">
          <h3>{{ repair.details?.equation || '历史固定示例 z + 2 = 9' }} → {{ repair.answer }}</h3>
          <p>{{ repair.reason }}</p><p v-if="repair.details?.version==='dynamic_v1'">{{repair.details.phase==='retest'?'独立新题':'补救练习'}}{{repair.details.helped?' 　 使用过帮助':''}}</p><p v-else>历史固定示例，不能证明原题已掌握。</p><div v-if="repair.verification?.status==='unverified'" class="paper-actions"><AppButton variant="outline" @click="reviewRepair(repair,true)">人工确认正确</AppButton><AppButton variant="outline" @click="reviewRepair(repair,false)">人工确认有误</AppButton></div><p v-if="repair.details?.teacherReview">教师核对：{{repair.details.teacherReview.correct?'正确':'有误'}}</p>
          <Status :tone="repair.correct ? 'green' : 'amber'">{{
            repair.verification?.status === "unverified"
              ? "需核对"
              : repair.correct
                ? "数值正确"
                : "需订正"
          }}</Status>
        </section>
        <p
          v-if="store.record&&(studentTab==='answers'&&!store.record.attempts.length||studentTab==='help'&&!store.record.helps.length||studentTab==='repairs'&&!store.record.repairs.length)"
        >
          暂无对应记录
        </p>
      </div></AppDialog
    ><SupplementPanel :task-id="store.task.id" teacher /></template
  ><TaskEmpty v-else />
  </template>
</template>
