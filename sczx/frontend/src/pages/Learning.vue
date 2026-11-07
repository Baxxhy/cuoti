<script setup>
import { computed, inject, ref } from "vue";
import { useRoute } from "vue-router";
import { motion, AnimatePresence } from "motion-v";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  ImagePlus,
  Lightbulb,
  Plus,
  RotateCcw,
  Send,
  Sparkles,
  Upload,
} from "lucide-vue-next";
import Workspace from "@/components/Workspace.vue";
import { useLearning } from "@/store.js";
import { questions } from "@/data.js";
import { navigate } from "@/lib/navigation.js";
const route = useRoute(),
  store = useLearning(),
  notify = inject("notify");
const page = computed(() => route.name);
const weight = ref(0),
  draft = ref(store.observation),
  help = ref(""),
  question = ref(""),
  imageName = ref("");
const answer = ref(""),
  reason = ref(""),
  submitted = ref(false),
  filter = ref("all"),
  open = ref(false),
  text = ref(store.wrongQuestion),
  image = ref(store.originalImage),
  repairAnswer = ref(""),
  repairReason = ref(""),
  repairSubmitted = ref(false);
const current = computed(() => questions[store.question] || questions[0]);
const showQuestion = computed(
  () =>
    filter.value === "all" ||
    (filter.value === "done" ? store.repaired : !store.repaired),
);
function send() {
  if (!question.value.trim() && !imageName.value)
    return notify("先写下问题或选择题图");
  help.value = `关于“${question.value || "你选择的题图"}”，请比较等式两边进行的运算，再说说是否保持相等。此处为预设演示回应。`;
  question.value = "";
}
function next() {
  if (store.question + 1 >= questions.length)
    return notify("两道示例题已展示，可以保存结果，稍后继续");
  store.update({ question: store.question + 1, helped: false });
  answer.value = "";
  reason.value = "";
  submitted.value = false;
}
function submit() {
  if (!answer.value.trim()) return notify("请先填写答案");
  store.addAttempt({
    question: store.question,
    answer: answer.value,
    reason: reason.value,
    helped: store.helped,
    correct: answer.value.trim() === current.value.answer,
  });
  submitted.value = true;
  notify("本次作答已保存");
}
function upload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    image.value = String(reader.result);
  };
  reader.readAsDataURL(file);
}
function record() {
  if (!text.value.trim()) return notify("请填写题目内容");
  store.update({
    wrongQuestion: text.value,
    originalImage: image.value,
    repaired: false,
  });
  open.value = false;
  notify("题目已录入当前原型");
}
function submitRepair() {
  if (!repairAnswer.value.trim()) return notify("请先填写答案");
  store.repaired = repairAnswer.value.trim() === "7";
  repairSubmitted.value = true;
  notify("这次补救尝试已记录");
}
</script>
<template>
  <template v-if="page === 'learn'">
    <div class="back-line">
      <Button variant="ghost" size="sm" @click="navigate('home')"
        ><ArrowLeft />返回我的学习</Button
      ><span>七年级数学 / 一元一次方程</span>
    </div>
    <PageHeading title="等式性质"
      ><Status tone="blue">学习中</Status
      ><RouteButton route="result" secondary>学习结果</RouteButton></PageHeading
    >
    <div class="learning-tabs">
      <AppTabs
        model-value="observe"
        :items="[
          { value: 'observe', label: '观察与理解' },
          { value: 'check', label: '独立检查' },
          { value: 'review', label: '订正与补救' },
        ]"
        @update:model-value="
          (value) =>
            value !== 'observe' &&
            navigate(value === 'check' ? 'check' : 'repair')
        "
      /><span
        >本课活动 2 / 5<Progress :model-value="40" aria-label="课时进度"
      /></span>
    </div>
    <Workspace
      ><template #primary
        ><article class="lesson-paper">
          <h2>如果两边一起变化，<br />相等关系会改变吗？</h2>
          <div class="interactive-balance">
            <div class="balance-math">
              <span>{{ 5 + weight }}</span
              ><span>=</span><span>{{ 5 + weight }}</span>
            </div>
            <div class="balance-scene">
              <div class="balance-pillar" />
              <motion.div
                class="balance-arm"
                :animate="{
                  rotate: weight % 2 ? [0, 3, -2, 0] : [0, -2, 2, 0],
                }"
                :transition="{ duration: 0.6 }"
                ><div
                  v-for="side in ['left', 'right']"
                  :key="side"
                  :class="['balance-dish', side]"
                >
                  <motion.div
                    :key="weight"
                    class="balance-block"
                    :initial="{ y: -8 }"
                    :animate="{ y: 0 }"
                    >5<span v-if="weight">+ {{ weight }}</span></motion.div
                  >
                </div></motion.div
              >
            </div>
            <div class="balance-toolbar">
              <Status tone="green"><Check :size="12" />两边仍然相等</Status
              ><Button size="sm" variant="outline" @click="weight++"
                ><Plus />两边同时加 1</Button
              ><Button
                variant="ghost"
                size="icon-sm"
                aria-label="重置天平"
                @click="weight = 0"
                ><RotateCcw
              /></Button>
            </div>
          </div>
          <div class="lesson-explanation">
            <span class="explanation-icon"><Lightbulb :size="19" /></span>
            <div>
              <h3>把观察写成数学</h3>
              <p>等式两边同时加上同一个数，结果仍然相等。</p>
              <div class="math-equation">
                a = b <span>⇒</span> a + c = b + c
              </div>
            </div>
          </div>
          <label class="field-label" for="observation">用自己的话解释一下</label
          ><Textarea
            id="observation"
            v-model="draft"
            placeholder="如果只改变左边，你认为会发生什么？"
          />
          <div class="paper-actions">
            <Button
              variant="outline"
              @click="
                store.observation = draft;
                notify('你的解释已保存');
              "
              ><Check />保存解释</Button
            ><RouteButton route="check">独立试一试</RouteButton>
          </div>
        </article></template
      ><template #secondary
        ><aside class="assistant-panel">
          <div class="assistant-title">
            <span class="assistant-symbol"><Sparkles :size="19" /></span>
            <h3>学习助手</h3>
          </div>
          <div class="assistant-message">
            <p>先想一想，天平平衡的时候，两边有什么共同的特点？</p>
          </div>
          <div class="help-options">
            <Button
              variant="outline"
              @click="
                help =
                  '例如 5 = 5，两边都加 2，得到 7 = 7。如果只给左边加 2，就变成 7 和 5。你能解释它们有什么不同吗？'
              "
              ><Lightbulb />举个例子</Button
            ><Button
              variant="outline"
              @click="
                help =
                  '把两边想成两组一样多的物品。两边增加同样多，仍然一样多。只增加一边时，它们就不一样多了。'
              "
              ><RotateCcw />换种讲法</Button
            >
          </div>
          <AnimatePresence
            ><motion.div
              v-if="help"
              class="assistant-answer"
              :initial="{ opacity: 0, y: 8 }"
              :animate="{ opacity: 1, y: 0 }"
              :exit="{ opacity: 0 }"
              ><span><Sparkles :size="13" />演示指导</span>
              <p>{{ help }}</p></motion.div
            ></AnimatePresence
          >
          <div class="assistant-compose">
            <Textarea
              v-model="question"
              aria-label="向学习助手提问"
              placeholder="写下你还没想明白的地方……"
            />
            <div>
              <label class="image-input" aria-label="选择题图"
                ><ImagePlus :size="18" /><input
                  type="file"
                  accept="image/*"
                  @change="
                    imageName = $event.target.files?.[0]?.name || ''
                  " /></label
              ><span>{{ imageName || "选择题图" }}</span
              ><Button size="icon" aria-label="发送问题" @click="send"
                ><Send
              /></Button>
            </div>
          </div>
          <ExperienceLink /></aside></template
    ></Workspace>
  </template>
  <template v-else-if="page === 'check'">
    <div class="back-line">
      <Button variant="ghost" @click="navigate('learn')"
        ><ArrowLeft />返回本课</Button
      >
    </div>
    <PageHeading title="独立检查" />
    <div class="check-grid">
      <Surface class="question-card"
        ><div class="question-meta">
          <span>等式性质 · 检查题 {{ store.question + 1 }}</span
          ><Status :tone="store.helped ? 'amber' : 'green'">{{
            store.helped ? "本题获得过帮助" : "独立尝试"
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
          placeholder="说明两边进行了什么运算……"
        /><motion.div
          v-if="store.helped"
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
            <p>{{ store.helped ? "已记录帮助" : "已记录独立作答" }}</p>
          </div>
        </div>
        <div class="paper-actions">
          <Button :disabled="submitted" @click="submit"
            >{{ submitted ? "作答已保存" : "提交作答" }}<ArrowRight /></Button
          ><Button variant="ghost" @click="store.helped = true"
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
    </div>
  </template>
  <template v-else-if="page === 'result'">
    <PageHeading title="本课结果"
      ><RouteButton route="learn" secondary>返回本课</RouteButton></PageHeading
    >
    <div class="result-banner">
      <span><CheckCircle2 :size="32" :stroke-width="1.4" /></span>
      <div>
        <h2>{{ store.completed ? "已提交" : "待提交" }}</h2>
      </div>
      <Button
        @click="
          store.completed = true;
          notify('本课结果已模拟提交给教师');
        "
        >{{ store.completed ? "再次提交结果" : "提交本课结果" }}<ArrowRight
      /></Button>
    </div>
    <div class="two-column">
      <Surface
        ><SectionHeading title="本次学习记录" /><button
          v-for="item in [
            {
              title: '检查题尝试',
              text: `${store.attempts.length} 次作答，原答案和解释均已记录`,
              route: 'records',
            },
            {
              title: '独立应用',
              text: `${store.attempts.filter((i) => i.correct && !i.helped).length} 次未使用帮助且数值正确`,
              route: 'check',
            },
            {
              title: '错题补救',
              text: store.repaired
                ? '已完成一次变式尝试'
                : '还可以回看等式两边的共同变化',
              route: 'repair',
            },
          ]"
          :key="item.title"
          class="result-row"
          @click="navigate(item.route)"
        >
          <CheckCircle2 :size="18" /><span
            ><strong>{{ item.title }}</strong
            ><small>{{ item.text }}</small></span
          ><ChevronRight :size="17" /></button></Surface
      ><Surface class="teacher-feedback"
        ><div class="feedback-avatar">
          <span>师</span>
          <h3>教师的反馈</h3>
        </div>
        <blockquote>{{ store.feedback }}</blockquote>
        <RouteButton route="check" secondary>继续检查新题</RouteButton></Surface
      >
    </div>
  </template>
  <template v-else-if="page === 'wrong'">
    <PageHeading title="错题帮"
      ><Button
        @click="
          text = store.wrongQuestion;
          image = store.originalImage;
          open = true;
        "
        ><Plus />录入一道题</Button
      ></PageHeading
    >
    <div class="wrong-summary">
      <BookOpen :size="27" />
      <div><p>一元一次方程 · 1 道演示题</p></div>
      <Status :tone="store.repaired ? 'green' : 'amber'">{{
        store.repaired ? "已订正，待复习" : "待补救 1 道"
      }}</Status>
    </div>
    <AppTabs
      v-model="filter"
      :items="[
        { value: 'all', label: '全部错题' },
        { value: 'pending', label: '待补救' },
        { value: 'done', label: '已订正' },
      ]"
    />
    <div v-if="showQuestion" class="wrong-layout">
      <Surface class="wrong-question"
        ><div class="question-meta">
          <Status>等式性质</Status><span>来自课程随堂练习 · 演示</span>
        </div>
        <h2>{{ store.wrongQuestion }}</h2>
        <img
          v-if="store.originalImage"
          class="uploaded-image"
          :src="store.originalImage"
          alt="本地选择的原始题图" />
        <div class="original-attempt">
          <span>原来的作答</span>
          <div class="math-equation">x = 8 + 3</div>
          <span class="mistake-note">左边去掉了 3，右边应该怎样变化？</span>
        </div>
        <div class="paper-actions">
          <RouteButton route="repair">开始补救</RouteButton
          ><RouteButton route="result" secondary
            >查看来源任务<ArrowUpRight
          /></RouteButton></div
      ></Surface>
    </div>
    <Surface v-else
      ><div class="empty-state"><h3>这个分类还没有题目</h3></div></Surface
    >
    <AppDialog
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
        >确认录入<Check /></Button
    ></AppDialog>
  </template>
  <template v-else>
    <div class="back-line">
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
        ><Status tone="amber">原作答回看</Status>
        <h2>为什么这里需要减去 3？</h2>
        <div class="original-attempt">
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
              store.repaired
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
    </div>
  </template>
</template>
