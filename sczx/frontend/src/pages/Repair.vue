<script setup>
import { computed, inject, ref, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Lightbulb,
} from "lucide-vue-next";
import { useRoute } from "vue-router";
const store = useLearning(),
  route = useRoute(),
  notify = inject("notify");
const wrong = computed(() =>
  store.record?.wrongQuestions.find((item) => item.id === route.query.wrong),
);
const key = `repair-${route.query.wrong || "practice"}`;
const saved = store.record?.drafts[key] || {};
const repairAnswer = ref(saved.answer || ""),
  repairReason = ref(saved.reason || ""),
  repairSubmitted = ref(saved.submitted === true),
  correct = ref(saved.correct === true);
watch([repairAnswer, repairReason, repairSubmitted, correct], () => {
  if (store.record) {
    store.record.drafts[key] = {
      answer: repairAnswer.value,
      reason: repairReason.value,
      submitted: repairSubmitted.value,
      correct: correct.value,
    };
    store.touch();
  }
});
function submitRepair() {
  try {
    const result = store.submitRepair(
      wrong.value?.id || null,
      repairAnswer.value,
      repairReason.value,
    );
    correct.value = result.correct;
    repairSubmitted.value = true;
    notify("补救尝试已保存");
  } catch (error) {
    notify(error.message);
  }
}
</script>
<template>
  <template v-if="store.task"
    ><div class="back-line">
      <Button variant="ghost" @click="navigate('wrong')"
        ><ArrowLeft />返回错题帮</Button
      >
    </div>
    <PageHeading title="错题订正"
      ><RouteButton route="result" secondary
        >返回原任务</RouteButton
      ></PageHeading
    >
    <div class="two-column">
      <Surface class="repair-paper"
        ><Status tone="amber">等式性质补救</Status>
        <p v-if="wrong">{{ wrong.prompt }}</p>
        <p v-if="wrong?.answer">原作答 · {{ wrong.answer }}</p>
        <img
          v-if="wrong?.image"
          :src="wrong.image"
          class="uploaded-image"
          alt="原始题图" />
        <h2>等式两边要进行相同运算</h2>
        <InfoTip label="补救示例范围"
          >下面使用固定例题讲解，再完成 z + 2 =
          9。此处保存本次补救尝试，暂不自动分析自定义题目。</InfoTip
        >
        <div class="original-attempt">
          <h3>教学示例</h3>
          <div class="math-equation">
            x + 3 = 8<br /><span class="incorrect-step">x = 8 + 3</span>
          </div>
        </div>
        <p>左边去掉了 3，右边却增加了 3。我们对两边做的是同一件事吗？</p>
        <div class="correct-method">
          <Lightbulb :size="18" />
          <div>
            <h3>先把完整过程写下来</h3>
            <div class="math-equation">x + 3 − 3 = 8 − 3<br />x = 5</div>
          </div>
        </div>
        <ExperienceLink
      /></Surface>
      <Surface class="repair-practice"
        ><h2>变式练习</h2>
        <div class="question-equation">z + 2 = 9</div>
        <label class="field-label" for="repair-answer">z 的值是多少？</label
        ><Input
          id="repair-answer"
          v-model="repairAnswer"
          inputmode="decimal"
          placeholder="填写数值"
          @update:model-value="repairSubmitted = false"
        /><label class="field-label" for="repair-reason"
          >你对两边进行了什么运算？</label
        ><Textarea
          id="repair-reason"
          v-model="repairReason"
          placeholder="两边同时……"
        />
        <div v-if="repairSubmitted" class="inline-notice">
          <CheckCircle2 :size="18" />
          <p>
            {{
              correct
                ? "正确。两边同时减去 2，得到 z = 7。"
                : "试着在两边同时减去 2，再计算右边。"
            }}
          </p>
        </div>
        <div class="paper-actions">
          <Button @click="submitRepair">提交尝试<ArrowRight /></Button
          ><RouteButton route="result" secondary>返回任务</RouteButton>
        </div></Surface
      >
    </div></template
  ><TaskEmpty v-else />
</template>
