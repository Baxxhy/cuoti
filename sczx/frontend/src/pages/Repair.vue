<script setup>
import MemoryReturn from "@/components/MemoryReturn.vue";
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  RefreshCw,
  Send,
  ChevronRight,
} from "lucide-vue-next";
import { wrongApi, wrongStatuses } from "@/services/wrongs.js";
import { modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import { navigate } from "@/lib/navigation.js";
const route = useRoute(),
  wrong = ref(null),
  options = ref({ reasons: [], knowledge: [] }),
  loading = ref(true),
  error = ref(""),
  saving = ref(false),
  response = ref(""),
  answer = ref(""),
  reason = ref(""),
  cause = ref("其他或待确认"),
  confirmed = ref(false),
  lastAttempt = ref(null);
const strategies = [
  ["hint", "给我提示"],
  ["example", "举个例子"],
  ["rephrase", "换种讲法"],
  ["foundation", "补基础"],
];
let version = 0,
  timer,
  requestKeys = {},
  disposed = false;
const job = useModelJob(async (value) => {
  if (value.status === "succeeded") await load(false);
});
const jobs = computed(() => wrong.value?.jobs || []);
const analysis = computed(() =>
  [...jobs.value]
    .reverse()
    .find((j) => j.input.mode === "analysis" && j.status === "succeeded"),
);
const variant = computed(() =>
  [...jobs.value]
    .reverse()
    .find(
      (j) =>
        j.input.mode === "variant" &&
        j.status === "succeeded" &&
        !wrong.value.repairs.some((a) => a.details.variantJobId === j.id),
    ),
);
const parent = computed(() =>
  [...jobs.value]
    .reverse()
    .find(
      (j) =>
        ["analysis", "guidance"].includes(j.input.mode) &&
        j.status === "succeeded",
    ),
);
const guidance = computed(() =>
  jobs.value.filter((j) => j.input.mode === "guidance"),
);
const knowledgeNames = computed(() =>
  options.value.knowledge
    .filter((p) => wrong.value?.details.knowledgeIds?.includes(p.id))
    .map((p) => p.name)
    .join(" · "),
);
async function load(initial = true) {
  const id = String(route.query.wrong || ""),
    token = version;
  if (initial) loading.value = true;
  error.value = "";
  try {
    const [item, opts] = await Promise.all([
      wrongApi.detail(id),
      wrongApi.options(),
    ]);
    if (disposed || token !== version) return;
    wrong.value = item;
    options.value = opts;
    if (initial) {
      const d = item.details.draft || {};
      const sameVariant = d.variantJobId === variant.value?.id;
      answer.value = sameVariant ? d.answer || "" : "";
      reason.value = sameVariant ? d.reason || "" : "";
      response.value = d.response || "";
      cause.value = item.details.cause || "其他或待确认";
      confirmed.value = item.details.causeConfirmed === true;
      lastAttempt.value = item.repairs.at(-1) || null;
      const pending = item.jobs.find((j) =>
        ["queued", "running"].includes(j.status),
      );
      const latest = item.jobs.at(-1);
      if (pending || latest?.status === "failed")
        await job.open(pending || latest);
    }
  } catch (e) {
    if (token === version) error.value = e.message;
  } finally {
    if (token === version) loading.value = false;
  }
}
watch(
  () => route.query.wrong,
  async () => {
    version++;
    clearTimeout(timer);
    wrong.value = null;
    requestKeys = {};
    lastAttempt.value = null;
    await job.open(null);
    load();
  },
  { immediate: true },
);
function schedule() {
  clearTimeout(timer);
  if (!wrong.value || wrong.value.readOnly) return;
  const id = wrong.value.id,
    token = version;
  timer = setTimeout(async () => {
    try {
      await wrongApi.save(id, {
        cause: cause.value,
        causeConfirmed: confirmed.value,
        draft: {
          variantJobId: variant.value?.id || null,
          answer: answer.value,
          reason: reason.value,
          response: response.value,
        },
      });
    } catch (e) {
      if (token === version) error.value = e.message;
    }
  }, 650);
}
watch([answer, reason, response], schedule);
async function confirmCause() {
  saving.value = true;
  try {
    await wrongApi.save(wrong.value.id, {
      cause: cause.value,
      causeConfirmed: confirmed.value,
      draft: {
        variantJobId: variant.value?.id || null,
        answer: answer.value,
        reason: reason.value,
        response: response.value,
      },
    });
    await load(false);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function create(mode, strategy = "hint", phase = "practice") {
  if (!wrong.value || wrong.value.readOnly || job.busy.value) return;
  const data = {
    wrongId: wrong.value.id,
    mode,
    strategy,
    phase,
    prompt: mode === "guidance" ? response.value : "",
    parentJobId: mode === "guidance" ? parent.value?.id : null,
  };
  const key = JSON.stringify(data);
  requestKeys[key] ||= crypto.randomUUID();
  await job.create({
    capability: "text",
    recordId: wrong.value.recordId || null,
    requestKey: requestKeys[key],
    data,
  });
  if (!job.error.value) {
    delete requestKeys[key];
    if (mode === "variant") {
      answer.value = "";
      reason.value = "";
      lastAttempt.value = null;
    }
  }
}
async function submit() {
  if (saving.value || !variant.value) return;
  saving.value = true;
  error.value = "";
  const id = wrong.value.id,
    token = version,
    payload = {
      variantJobId: variant.value.id,
      answer: answer.value,
      reason: reason.value,
    };
  const k = JSON.stringify(payload);
  requestKeys[k] ||= crypto.randomUUID();
  try {
    const result = await wrongApi.attempt(id, {
      ...payload,
      requestKey: requestKeys[k],
    });
    if (token !== version) return;
    lastAttempt.value = result;
    delete requestKeys[k];
    await load(false);
  } catch (e) {
    if (token === version) error.value = e.message;
  } finally {
    if (token === version) saving.value = false;
  }
}
async function stop() {
  try {
    await modelApi.stop(job.job.value.id);
    await job.open({ id: job.job.value.id });
    await load(false);
  } catch (e) {
    error.value = e.message;
  }
}
onBeforeUnmount(() => {
  disposed = true;
  version++;
  clearTimeout(timer);
});
</script>
<template>
<MemoryReturn/>
  <div class="back-line">
    <Button variant="ghost" @click="navigate('wrong')"
      ><ArrowLeft />错题帮</Button
    >
  </div>
  <p v-if="loading" role="status">正在读取原题与补救记录…</p>
  <Surface v-else-if="error && !wrong"
    ><h2>无法打开错题</h2>
    <p role="alert">{{ error }}</p>
    <Button @click="load()">重新读取</Button></Surface
  >
  <template v-else-if="wrong"
    ><PageHeading title="错题订正"
      ><Status :tone="wrong.status === 'retest_passed' ? 'green' : 'amber'">{{
        wrongStatuses[wrong.status]
      }}</Status
      ><Button
        v-if="wrong.taskId"
        variant="outline"
        @click="navigate('result?task=' + wrong.taskId)"
        >返回原任务<ArrowUpRight /></Button
    ></PageHeading>
    <p v-if="wrong.readOnly" role="status" class="inline-notice">
      已移出班级，此任务的原题和历史记录仅供回看。
    </p>
    <div
      class="remediation-workspace"
      :class="{ 'without-guidance': !guidance.length }"
    >
      <aside class="remediation-original">
        <div class="question-meta">
          <Status>{{ wrong.details.subject || "数学" }}</Status
          ><span>{{
            knowledgeNames ||
            { course: "课程作答", manual: "个人录入", image: "题图识别" }[
              wrong.source
            ]
          }}</span>
        </div>
        <h2>{{ wrong.prompt }}</h2>
        <a
          v-if="wrong.image"
          :href="wrong.image"
          target="_blank"
          rel="noreferrer"
          aria-label="打开原始题图"
          ><img
            class="wrong-detail-image"
            :src="wrong.image"
            alt="原始题图" /></a
        ><img
          v-if="wrong.details.cropFileId"
          class="wrong-detail-image"
          :src="'/api/files/' + wrong.details.cropFileId"
          alt="本题裁剪图"
        />
        <div class="original-attempt">
          <h3>原来的作答</h3>
          <p class="math-equation">{{ wrong.answer || "未填写" }}</p>
          <p class="preserve-lines">{{ wrong.reason }}</p>
        </div>
        <label class="field-label" for="cause">错因</label
        ><select id="cause" v-model="cause" :disabled="wrong.readOnly">
          <option v-for="r in options.reasons" :key="r">{{ r }}</option></select
        ><label class="capture-confirm"
          ><input
            v-model="confirmed"
            type="checkbox"
            :disabled="wrong.readOnly"
          />确认本题错因</label
        ><Button
          variant="outline"
          :disabled="wrong.readOnly || saving"
          @click="confirmCause"
          >保存分类</Button
        >
        <details v-if="wrong.repairs.length" class="repair-history">
          <summary>补救记录 · {{ wrong.repairs.length }}</summary>
          <article v-for="a in wrong.repairs" :key="a.id">
            <Status>{{
              a.details.version === "legacy_fixed"
                ? "历史固定示例"
                : a.details.phase === "retest"
                  ? "独立复测"
                  : "有帮助练习"
            }}</Status>
            <p>{{ a.details.equation }}</p>
            <p>作答 {{ a.answer }}</p>
            <p>{{ a.reason }}</p>
            <strong
              >{{
                a.verification?.status === "unverified"
                  ? "需要核对"
                  : a.correct
                    ? "核验正确"
                    : "核验不一致"
              }}{{ a.details.helped ? " · 使用过帮助" : "" }}</strong
            >
            <p v-if="a.details.version === 'legacy_fixed'">
              {{ a.details.scope }}
            </p>
          </article>
        </details>
      </aside>
      <main class="remediation-main">
        <section class="remediation-section">
          <div class="remediation-section-heading">
            <span class="remediation-step">01</span>
            <h2>找到问题</h2>
            <Button
              :disabled="wrong.readOnly || job.busy.value"
              variant="outline"
              size="sm"
              @click="create('analysis')"
              >{{ analysis ? "重新分析" : "分析错因" }}</Button
            >
          </div>
          <template v-if="analysis"
            ><p class="remediation-goal">{{ analysis.result.goal }}</p>
            <blockquote v-if="analysis.result.evidence">
              {{ analysis.result.evidence }}
            </blockquote>
            <p>建议检查：{{ analysis.result.cause }}</p>
            <p class="muted">{{ analysis.result.uncertainty }}</p></template
          >
          <p v-else class="muted">
            {{ wrong.reason || "保留原作答，先确认错误发生在哪一步。" }}
          </p>
        </section>
        <section v-if="analysis" class="remediation-section">
          <div class="remediation-section-heading">
            <span class="remediation-step">02</span>
            <h2>分步订正</h2>
          </div>
          <ol class="remediation-steps">
            <li v-for="(step, i) in analysis.result.steps" :key="i">
              {{ step }}
            </li>
          </ol>
          <div class="remediation-question">
            {{ analysis.result.checkQuestion }}
          </div>
          <label class="field-label" for="repair-response">你的理解</label
          ><Textarea
            id="repair-response"
            v-model="response"
            :disabled="wrong.readOnly"
          />
          <div class="paper-actions">
            <Button
              :disabled="wrong.readOnly || job.busy.value || !response.trim()"
              @click="create('guidance', 'continue')"
              >继续订正<ChevronRight /></Button
            ><Button
              variant="outline"
              :disabled="wrong.readOnly || job.busy.value"
              @click="create('variant')"
              >生成变式练习</Button
            >
          </div>
        </section>
        <section v-if="variant" class="remediation-section">
          <div class="remediation-section-heading">
            <span class="remediation-step">03</span>
            <h2>
              {{ variant.input.phase === "retest" ? "独立新题" : "变式练习" }}
            </h2>
          </div>
          <p>{{ variant.result.variant.prompt }}</p>
          <div class="question-equation">
            {{ variant.result.variant.equation }}
          </div>
          <form @submit.prevent="submit">
            <label class="field-label" for="repair-answer">本题答案</label
            ><Input
              id="repair-answer"
              v-model="answer"
              :disabled="wrong.readOnly || saving"
              required
            /><label class="field-label" for="repair-reason">解题过程</label
            ><Textarea
              id="repair-reason"
              v-model="reason"
              :disabled="wrong.readOnly || saving"
            /><Button
              type="submit"
              :disabled="wrong.readOnly || saving || !answer.trim()"
              >{{ saving ? "正在保存…" : "提交本题" }}</Button
            >
          </form>
        </section>
        <section v-if="lastAttempt" class="remediation-section repair-outcome">
          <CheckCircle2 />
          <h2>
            {{
              lastAttempt.verification?.status === "unverified"
                ? "需要人工核对"
                : lastAttempt.correct
                  ? "本题核验正确"
                  : "再检查这一步"
            }}
          </h2>
          <p>{{ lastAttempt.details.equation }} → {{ lastAttempt.answer }}</p>
          <p v-if="lastAttempt.details.helped">
            本题使用过帮助，原帮助记录已保留。
          </p>
          <p v-if="lastAttempt.details.version === 'legacy_fixed'">
            {{ lastAttempt.details.scope }}
          </p>
          <div class="paper-actions">
            <Button
              v-if="!variant"
              :disabled="wrong.readOnly || job.busy.value"
              @click="create('variant', 'hint', 'retest')"
              >生成独立新题</Button
            ><Button
              variant="outline"
              @click="
                navigate(wrong.taskId ? 'result?task=' + wrong.taskId : 'wrong')
              "
              >{{ wrong.taskId ? "返回原任务" : "返回错题帮" }}</Button
            >
          </div>
        </section>
      </main>
      <aside class="remediation-assistant">
        <div class="remediation-assistant-heading">
          <span class="assistant-orbit" />
          <h2>学习助手</h2>
        </div>
        <div class="remediation-strategies">
          <Button
            v-for="[value, label] in strategies"
            :key="value"
            variant="outline"
            :disabled="wrong.readOnly || job.busy.value"
            @click="create('guidance', value)"
            >{{ label }}</Button
          >
        </div>
        <div v-if="job.busy.value" class="inline-notice" role="status">
          <RefreshCw class="animate-spin" :size="16" />{{
            job.job.value?.step || "正在提交…"
          }}<Button
            v-if="job.job.value?.input?.guidance"
            size="sm"
            variant="ghost"
            @click="stop"
            >结束本轮</Button
          >
        </div>
        <div
          v-if="job.error.value || job.job.value?.status === 'failed'"
          role="alert"
          class="form-error"
        >
          {{ job.error.value || job.job.value.error
          }}<Button
            :disabled="job.busy.value || wrong.readOnly"
            variant="outline"
            @click="
              job.job.value?.status === 'failed' ? job.retry() : load(false)
            "
            >重试</Button
          >
        </div>
        <article v-for="j in guidance" :key="j.id" class="remediation-turn">
          <p class="remediation-student">{{ j.prompt }}</p>
          <template v-if="j.result"
            ><h3>{{ j.result.title }}</h3>
            <p>{{ j.result.hint }}</p>
            <ol>
              <li v-for="step in j.result.steps" :key="step">{{ step }}</li>
            </ol>
            <p class="remediation-question">{{ j.result.question }}</p>
            <a
              v-for="source in j.result.sources || []"
              :key="source.versionId"
              :href="
                '#/source?case=' + source.id + '&version=' + source.versionId
              "
              >{{ source.title }}</a
            ></template
          >
          <p v-else>{{ j.error || j.step }}</p>
        </article>
      </aside>
    </div>
    <div v-if="error" role="alert" class="form-error">
      {{ error
      }}<Button variant="outline" :disabled="saving" @click="confirmCause"
        >重试保存</Button
      >
    </div>
  </template>
</template>
