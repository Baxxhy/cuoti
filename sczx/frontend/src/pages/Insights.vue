<script setup>
import { computed, inject, ref } from "vue";
import { ArrowUpRight, Check, Plus, Send } from "lucide-vue-next";
import { useLearning } from "@/store.js";

import { questions, demoStudents } from "@/data.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
const store = useLearning(),
  notify = inject("notify"),
  studentOpen = ref(false),
  supplement = ref(false),
  draft = ref(store.record?.feedback || ""),
  supplementText = ref("回看等式两边共同变化的过程，再完成独立检查。"),
  error = ref("");
const independent = computed(
  () =>
    store.record?.attempts.filter((item) => item.correct && !item.helped)
      .length || 0,
);
function feedback() {
  try {
    store.saveFeedback(draft.value);
    notify("反馈已发送到学生结果页");
  } catch (problem) {
    error.value = problem.message;
  }
}
function arrange() {
  if (!supplementText.value.trim()) return notify("请填写补充内容");
  store.data.supplements.push({
    id: crypto.randomUUID(),
    taskId: store.task.id,
    content: supplementText.value,
    createdAt: new Date().toISOString(),
  });
  store.touch();
  supplement.value = false;
  notify("补充学习已安排");
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
        <span>参与学生</span><strong>1<small>人</small></strong>
      </div>
      <div>
        <span>已经提交</span
        ><strong>{{ store.record.completed ? 1 : 0 }}<small>/ 1</small></strong>
      </div>
      <div>
        <span>新题独立完成</span
        ><strong>{{ independent }}<small>次</small></strong>
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
            <tr v-for="student in store.students" :key="student.id">
              <td>
                <span class="student-name avatar-0"
                  ><span>林</span>{{ student.name }}</span
                >
              </td>
              <td>
                <div class="table-progress">
                  <span>{{ student.status }}</span
                  ><Progress
                    :model-value="student.progress"
                    aria-label="小林学习进度"
                  />
                </div>
              </td>
              <td>{{ student.help }}</td>
              <td>
                <Status :tone="independent ? 'green' : 'neutral'">{{
                  student.result
                }}</Status>
              </td>
              <td>
                <Button variant="ghost" @click="studentOpen = true"
                  >查看过程<ArrowUpRight
                /></Button>
              </td>
            </tr>
          </tbody>
        </table></div
    ></Surface>
    <div class="two-column insight-detail">
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
        ><SectionHeading title="给学生的反馈" /><Textarea
          v-model="draft"
          aria-label="教师反馈"
        />
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="paper-actions">
          <Button @click="feedback"><Check />确认并保存</Button>
        </div></Surface
      >
    </div>
    <Surface class="records-surface"
      ><SectionHeading title="固定学情示例" />
      <details>
        <summary>查看示例学生</summary>
        <p v-for="item in demoStudents" :key="item.name">
          {{ item.name }} · {{ item.status }} · {{ item.result }}（固定示例）
        </p>
      </details></Surface
    ><AppDialog
      v-model:open="studentOpen"
      title="小林同学的学习过程"
      content-class="student-detail-dialog"
      ><div class="attempt-timeline">
        <section>
          <h3>自己的解释</h3>
          <p>{{ store.record.observation || "尚未填写" }}</p>
        </section>
        <section v-for="attempt in store.record.attempts" :key="attempt.id">
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
            attempt.correct ? "数值正确" : "需订正"
          }}</Status>
        </section>
        <section v-for="help in store.record.helps" :key="help.id">
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
        <section v-for="repair in store.record.repairs" :key="repair.id">
          <h3>补救变式 z + 2 = 9 → {{ repair.answer }}</h3>
          <p>{{ repair.reason }}</p>
          <Status :tone="repair.correct ? 'green' : 'amber'">{{
            repair.correct ? "数值正确" : "需订正"
          }}</Status>
        </section>
        <p v-if="!store.record.attempts.length && !store.record.helps.length">
          尚无作答和求助记录
        </p>
      </div></AppDialog
    ><AppDialog v-model:open="supplement" title="安排补充学习"
      ><label class="field-label" for="supplement-content">补充内容</label
      ><Textarea id="supplement-content" v-model="supplementText" /><Button
        @click="arrange"
        >确认安排<Send /></Button></AppDialog></template
  ><TaskEmpty v-else />
</template>
