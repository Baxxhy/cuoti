<script setup>
import { computed, inject, ref, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Lightbulb,
} from "lucide-vue-next";
import { motion } from "motion-v";
import { questions } from "@/data.js";
const store = useLearning(),
  notify = inject("notify");
const saved = store.record?.drafts.check || {};
const questionIndex = ref(
  Number.isInteger(saved.question) &&
    saved.question < questions.length &&
    saved.question >= 0
    ? saved.question
    : 0,
);
const answer = ref(saved.answer || ""),
  reason = ref(saved.reason || ""),
  helped = ref(saved.helped === true),
  submitted = ref(saved.submitted === true);
const taskQuestions = computed(() => store.task?.questions || questions);
const current = computed(() => taskQuestions.value[questionIndex.value]);
watch(
  [questionIndex, answer, reason, helped, submitted],
  () => {
    if (store.record) {
      store.record.drafts.check = {
        question: questionIndex.value,
        answer: answer.value,
        reason: reason.value,
        helped: helped.value,
        submitted: submitted.value,
      };
      store.touch();
    }
  },
  { flush: "sync" },
);
function askHint() {
  helped.value = true;
  store.requestHelp(questionIndex.value, "提示", current.value.hint);
}
function next() {
  if (questionIndex.value + 1 >= taskQuestions.value.length)
    return notify("本任务两道检查题已完成，可查看学习结果");
  questionIndex.value++;
  answer.value = "";
  reason.value = "";
  helped.value = false;
  submitted.value = false;
}
function submit() {
  if (submitted.value) return;
  try {
    store.submitAnswer(
      questionIndex.value,
      answer.value,
      reason.value,
      helped.value,
    );
    submitted.value = true;
    notify("本次作答已保存");
  } catch (error) {
    notify(error.message);
  }
}
</script>
<template>
  <template v-if="store.task"
    ><div class="back-line">
      <Button variant="ghost" @click="navigate('learn')"
        ><ArrowLeft />返回本课</Button
      >
    </div>
    <PageHeading title="独立检查" />
    <div class="check-grid">
      <Surface class="question-card"
        ><div class="question-meta">
          <span>等式性质 · 检查题 {{ questionIndex + 1 }}</span
          ><Status :tone="helped ? 'amber' : 'green'">{{
            helped ? "本题获得过帮助" : "独立尝试"
          }}</Status>
        </div>
        <h2>{{ current.prompt }}</h2>
        <div class="question-equation">{{ current.equation }}</div>
        <label class="field-label" for="answer">你的答案</label
        ><Input
          id="answer"
          v-model="answer"
          inputmode="decimal"
          placeholder="填写数值"
          @update:model-value="submitted = false"
        /><label class="field-label" for="reason"
          >你是怎样保持等式成立的？</label
        ><Textarea
          id="reason"
          v-model="reason"
          @update:model-value="submitted = false"
          placeholder="说明两边进行了什么运算……"
        /><motion.div
          v-if="helped"
          class="inline-notice"
          :initial="{ opacity: 0 }"
          :animate="{ opacity: 1 }"
          ><Lightbulb :size="17" />
          <div>
            <strong>一点提示</strong>
            <p>{{ current.hint }}</p>
          </div></motion.div
        >
        <div v-if="submitted" class="inline-notice">
          <CheckCircle2 :size="18" />
          <div>
            <strong>{{
              answer.trim() === current.answer ? "数值正确" : "需要订正"
            }}</strong>
            <p>{{ helped ? "已记录帮助" : "已记录独立作答" }}</p>
          </div>
        </div>
        <div class="paper-actions">
          <Button :disabled="submitted" @click="submit"
            >{{ submitted ? "作答已保存" : "提交作答" }}<ArrowRight /></Button
          ><Button variant="ghost" @click="askHint()" :disabled="submitted"
            ><CircleHelp />我需要提示</Button
          >
        </div></Surface
      >
      <aside class="check-aside">
        <InfoTip label="独立检查规则"
          >获得提示后，本题作为指导练习保留；换新题检查时重新记录独立作答。</InfoTip
        ><Button variant="outline" @click="next"
          >换一道新题<ArrowRight /></Button
        ><RouteButton route="result" secondary>查看本课结果</RouteButton>
      </aside>
    </div></template
  ><TaskEmpty v-else />
</template>
