<script setup>
import { inject, ref, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import {
  ArrowLeft,
  Check,
  ImagePlus,
  Lightbulb,
  Plus,
  RotateCcw,
  Send,
  Sparkles,
} from "lucide-vue-next";
import { motion, AnimatePresence } from "motion-v";
import Workspace from "@/components/Workspace.vue";
const store = useLearning(),
  notify = inject("notify");
const weight = ref(store.record?.drafts.weight || 0),
  draft = ref(store.record?.observation || ""),
  help = ref(""),
  question = ref(store.record?.drafts.assistant || ""),
  imageName = ref(store.record?.drafts.imageName || ""),
  image = ref(store.record?.drafts.assistantImage || "");
watch(draft, (value) => {
  if (store.record) {
    store.record.observation = value;
    store.touch();
  }
});
watch(question, (value) => {
  if (store.record) {
    store.record.drafts.assistant = value;
    store.touch();
  }
});
watch(help, (value) => {
  if (value) store.requestHelp(null, "讲解", value, image.value);
});
function send() {
  if (!question.value.trim() && !imageName.value)
    return notify("先写下问题或选择题图");
  help.value = `关于“${question.value || "你选择的题图"}”，先比较等式两边进行的运算。此处为预设演示回应。`;
  question.value = "";
}
watch([weight, imageName, image], () => {
  if (store.record) {
    Object.assign(store.record.drafts, {
      weight: weight.value,
      imageName: imageName.value,
      assistantImage: image.value,
    });
    store.touch();
  }
});
function chooseImage(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    imageName.value = file.name;
    image.value = String(reader.result);
  };
  reader.onerror = () => notify("题图读取失败");
  reader.readAsDataURL(file);
}
</script>
<template>
  <template v-if="store.task"
    ><div class="back-line">
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
          <div class="published-activities">
            <h3>学习目标</h3>
            <p>{{ store.task.snapshot.goal }}</p>
            <section
              v-for="block in store.task.snapshot.blocks"
              :key="block.id"
            >
              <h3>{{ block.title }}</h3>
              <p>{{ block.content }}</p>
            </section>
          </div>
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
                store.record.observation = draft;
                store.touch();
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
          <img
            v-if="image"
            :src="image"
            class="upload-thumbnail"
            alt="学习提问题图"
          />
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
                  @change="chooseImage" /></label
              ><span>{{ imageName || "选择题图" }}</span
              ><Button size="icon" aria-label="发送问题" @click="send"
                ><Send
              /></Button>
            </div>
          </div>
          <ExperienceLink /></aside></template></Workspace></template
  ><TaskEmpty v-else />
</template>
