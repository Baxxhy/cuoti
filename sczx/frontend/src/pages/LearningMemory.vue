<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useLearning } from "@/store.js";
import { memoryApi, memoryTarget, memoryAuditFor, memoryTeacherTask } from "@/services/memory.js";
import { teachingApi } from "@/services/teaching.js";
import { api } from "@/services/api.js";
import { navigate } from "@/lib/navigation.js";
import {
  ArrowRight,
  ArrowLeft,
  History,
  Search,
  RotateCcw,
  BookOpen,
  ChevronRight,
  FileCheck2,
} from "lucide-vue-next";
const route = useRoute(),
  router = useRouter(),
  store = useLearning(),
  teacher = computed(() => store.user.role === "teacher");
const data = ref(null),
  loading = ref(false),
  error = ref(""),
  saving = ref(false),
  classes = ref([]),
  students = ref([]),
  selectedClass = ref(String(route.query.classId || "")),
  selectedStudent = ref(String(route.query.studentId || "")),
  query = ref(""),
  filter = ref("all"),
  evidenceOpen=ref(null),
  editing = ref(null),
  reason = ref(""),
  note = ref(""),
  knowledgeIds = ref([]),
  kind = ref(""),
  target = ref("");
let version = 0,
  requestKey = crypto.randomUUID();
const independentTotal = computed(
  () =>
    new Set(
      data.value?.items.flatMap((i) =>
        i.evidence
          .filter((e) =>
            ["independent_correct", "retest_passed"].includes(e.outcome),
          )
          .map((e) => e.eventId),
      ) || [],
    ).size,
);
const selected = computed(
  () => data.value?.items.find((i) => i.id === route.query.knowledge) || null,
);
const auditEntries = computed(() =>
  memoryAuditFor(data.value?.audit, selected.value),
);
const filtered = computed(
  () =>
    data.value?.items.filter(
      (i) =>
        (!query.value || i.name.includes(query.value)) &&
        (filter.value === "all" ||
          (filter.value === "needs"
            ? ["strengthen", "insufficient", "review_due"].includes(
                i.state.status,
              )
            : i.state.status === "independent")),
    ) || [],
);
const evidence = computed(
  () => selected.value?.evidence || data.value?.unlinkedEvidence || [],
);
const studentState=item=>teacher.value?item.state.statusLabel:({none:'还没有练习',improving:'正在进步',insufficient:'还需练习',strengthen:'再练一练',review_due:'该复习了',independent:'有独立答对记录'})[item.state.status]||item.state.statusLabel;
const evidenceLabel=e=>teacher.value?e.label:({independent_correct:'独立答对',independent_incorrect:'需要订正',helped_correct:'提示后答对',retest_passed:'独立复测答对',retest_failed:'复测需订正'})[e.outcome]||e.label;
const time = (value) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "暂无";
function url(r) {
  return memoryTarget(r.target, route.query.returnTask, r.knowledgeId).slice(1);
}
function openTarget(target,knowledgeId){
 if(teacher.value){const task=memoryTeacherTask(target,data.value.items);if(!task)return;store.selectTask(task);store.selectStudent(data.value.studentId);navigate('insights?task='+task);return;}
 navigate(memoryTarget(target,route.query.returnTask,knowledgeId).slice(1));
}
async function load() {
  const g = ++version;
  loading.value = true;
  error.value = "";
  data.value = null;
  try {
    if (teacher.value) {
      const classRows = await teachingApi.classes();
      if (g !== version) return;
      classes.value = classRows;
      selectedClass.value = String(
        route.query.classId || classes.value[0]?.id || "",
      );
      if (!selectedClass.value) {
        students.value = [];
        return;
      }
      const memberRows = await api.classroomMembers(selectedClass.value);
      if (g !== version) return;
      students.value = memberRows;
      selectedStudent.value = String(
        route.query.studentId || students.value[0]?.id || "",
      );
      if (!selectedStudent.value) return;
    }
    const value = await memoryApi.overview(
      teacher.value
        ? { studentId: selectedStudent.value, classId: selectedClass.value }
        : {},
    );
    if (g === version) data.value = value;
  } catch (e) {
    if (g === version) error.value = e.message;
  } finally {
    if (g === version) loading.value = false;
  }
}
watch(() => [route.query.studentId, route.query.classId], load, {
  immediate: true,
});
onBeforeUnmount(() => version++);
async function selectClass() {
  await router.replace({ query: { classId: selectedClass.value } });
}
async function selectStudent() {
  await router.replace({
    query: { classId: selectedClass.value, studentId: selectedStudent.value },
  });
}
function choose(id) {
  router.push({ query: { ...route.query, knowledge: id } });
}
function edit(e) {
  editing.value = e;
  reason.value = "";
  note.value = "";
  knowledgeIds.value = e.knowledgeIds || [];
  kind.value = teacher.value ? "knowledge_correction" : "correction_request";
  target.value = "";
  requestKey = crypto.randomUUID();
}
async function submit() {
  if (saving.value || loading.value || !data.value || !editing.value) return;
  saving.value = true;
  error.value = "";
  try {
    await memoryApi.change({
      studentId: data.value.studentId,
      classId: teacher.value ? selectedClass.value : undefined,
      kind: kind.value,
      knowledgeId: editing.value.knowledgeId || null,
      evidenceId: editing.value.evidenceId,
      reason: reason.value,
      note: note.value,
      knowledgeIds: knowledgeIds.value,
      target: target.value,
      correctionRequestId:
        kind.value === "knowledge_correction"
          ? data.value.audit
              .filter(
                (a) =>
                  a.kind === "correction_request" &&
                  a.eventId === editing.value.eventId,
              )
              .at(-1)?.id
          : undefined,
      expectedRevision: data.value.revision,
      requestKey,
    });
    editing.value = null;
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function snooze(r) {
  saving.value = true;
  try {
    await memoryApi.change({
      kind: "snooze",
      knowledgeId: r.knowledgeId,
      expectedRevision: data.value.revision,
      requestKey: crypto.randomUUID(),
    });
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
function lessonContext(lesson) {
  const task=store.data.tasks.find(t=>t.id===lesson.taskId);
  const published=task?.publishedAt;
  return [published?new Date(published).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'',lesson.readOnly?'历史任务':task?.summary?.status||task?.status||''].filter(Boolean).join(' 　 ');
}
const targets = computed(() => {
  const rows =
    data.value?.items.flatMap((i) =>
      i.lessons
        .filter((l) => !l.readOnly)
        .map((l) => ({ target: l.target, title: l.title })),
    ) || [];
  const wrongs =
    data.value?.items.flatMap((i) =>
      i.evidence
        .filter((e) => e.sourceType === "wrong" && !e.readOnly)
        .map((e) => ({ target: e.target, title: e.equation || e.prompt })),
    ) || [];
  return [...new Map([...rows, ...wrongs].map((x) => [x.target, x])).values()];
});
</script>
<template>
  <PageHeading :title="teacher ? '学生学习记忆' : '复习'"
    ><Button
      v-if="route.query.returnTask"
      variant="outline"
      @click="navigate('learn?task=' + route.query.returnTask)"
      ><ArrowLeft />返回当前课时</Button
    ><Button variant="ghost" :disabled="loading" @click="load"
      ><RotateCcw />刷新</Button
    ></PageHeading
  >
  <div v-if="teacher" class="memory-scope">
    <label
      >班级<select
        v-model="selectedClass"
        aria-label="记忆班级"
        @change="selectClass"
      >
        <option v-for="c in classes" :key="c.id" :value="c.id">
          {{ c.name }}
        </option>
      </select></label
    ><label
      >学生<select
        v-model="selectedStudent"
        aria-label="记忆学生"
        @change="selectStudent"
      >
        <option v-for="s in students" :key="s.id" :value="s.id">
          {{ s.displayName }}
        </option>
      </select></label
    >
  </div>
  <p v-if="loading" role="status">正在读取学习记录…</p>
  <div v-if="error" class="form-error" role="alert">
    {{ error }}<Button variant="ghost" @click="load">重新读取</Button>
  </div>
  <div
    v-if="data && route.query.knowledge && !selected"
    class="inline-notice"
    role="status"
  >
    没有找到当前学习范围内的知识点。<Button
      variant="ghost"
      @click="
        router.replace({ query: { ...route.query, knowledge: undefined } })
      "
      >返回知识列表</Button
    >
  </div>
  <template v-if="data"
    ><div v-if="!selected&&teacher" class="memory-summary">
      <div>
        <span>{{ teacher ? data.studentName : "我的知识点" }}</span
        ><strong>{{ data.items.length }}</strong>
      </div>
      <div>
        <span>待复习建议</span
        ><strong>{{ data.recommendations.length }}</strong>
      </div>
      <div>
        <span>独立答对次数</span><strong>{{ independentTotal }}</strong>
      </div>
      <InfoTip label="状态计算范围"
        >规则建议，依据实际作答与核验；不代表已掌握。近期{{
          data.rules.recentHours
        }}小时，复习间隔{{ data.rules.reviewDays }}天。</InfoTip
      >
    </div>
    <div v-if="!selected&&!teacher" class="student-review-context"><span>{{data.recommendations.length?data.recommendations.length+'项待复习':'查看学过的知识点'}}</span><InfoTip label="学习记录统计">{{data.items.length}}个知识点，{{independentTotal}}次独立数值正确记录；不代表已经掌握。</InfoTip></div>
    <section
      v-if="!selected && data.recommendations.length"
      class="memory-review-strip"
      :style="{
        gridTemplateColumns: '1fr',
      }"
    >
      <article v-for="r in data.recommendations.slice(0, 1)" :key="r.id">
        <span>{{ data.items.find((i) => i.id === r.knowledgeId)?.name }}</span>
        <h2>{{r.label==='继续补救'?'继续订正':r.label}}</h2>
        <InfoTip label="为什么建议复习">{{r.reason}}</InfoTip>
        <div>
          <Button @click="openTarget(r.target,r.knowledgeId)">{{teacher?'查看对应任务':'开始复习'}}<ArrowRight /></Button
          ><Button
            v-if="!teacher"
            variant="ghost"
            :disabled="saving"
            @click="snooze(r)"
            >稍后</Button
          >
        </div>
      </article>
    </section>
    <div class="memory-workspace" :class="{ 'has-detail': selected,'student-memory-focus':!teacher,'teacher-memory-focus':teacher }">
      <section v-if="!selected" class="memory-list-pane">
        <div class="memory-list-tools">
          <Input
            v-model="query"
            aria-label="搜索知识点"
            placeholder="搜索知识点"
          /><select v-model="filter" aria-label="筛选学习状态">
            <option value="all">全部状态</option>
            <option value="needs">待检查</option>
            <option value="independent">有独立答对次数</option>
          </select>
        </div>
        <div v-if="filtered.length" class="memory-table">
          <button
            v-for="item in filtered"
            :key="item.id"
            class="memory-knowledge-row"
            :class="{ selected: selected?.id === item.id }"
            @click="choose(item.id)"
          >
            <div>
              <strong>{{ item.name }}</strong
              ><span>{{ studentState(item) }}</span>
            </div>
            <div class="memory-row-counts">
              <span>{{ item.state.independentCorrect }} 次独立答对</span
              ><span>{{ item.state.evidenceCount }} 次练习</span>
            </div>
            <time>{{ time(item.state.lastPracticedAt) }}</time
            ><ChevronRight :size="17" />
          </button>
        </div>
        <div v-else class="empty-state">
          <BookOpen />
          <h2>
            {{ data.items.length ? "没有匹配的知识点" : "还没有学习记录" }}
          </h2>
          <RouteButton v-if="!teacher" route="courses">查看课程</RouteButton>
        </div>
      </section>
      <section
        v-if="selected || data.unlinkedEvidence.length"
        class="memory-detail"
      >
        <div class="memory-detail-context"><div class="memory-detail-heading">
          <div>
            <h2>{{ selected?.name || "尚未关联知识点" }}</h2>
          </div>
          <Button
            v-if="selected"
            variant="ghost"
            @click="
              router.push({ query: { ...route.query, knowledge: undefined } })
            "
            >收起</Button
          >
        </div>
        <template v-if="selected"
          ><Status>{{ studentState(selected) }}</Status>
          <InfoTip label="当前状态说明">{{selected.state.reason}}</InfoTip>
          <p v-if="selected.state.reviewRequested" class="inline-notice">
            教师已标记需要复核，原核验结果保留。
          </p>
          <div
            v-if="selected.prerequisites.length"
            class="memory-prerequisites"
          >
            <span>先前学过</span
            ><Button
              v-for="p in selected.prerequisites"
              :key="p.id"
              variant="outline"
              size="sm"
              @click="choose(p.id)"
              >{{ p.name }}</Button
            >
          </div>
          <div v-if="selected.recommendation" class="memory-next">
            <InfoTip label="复习建议说明">{{selected.recommendation.reason}}</InfoTip>
            <Button
              variant="outline"
              @click="openTarget(selected.recommendation.target,selected.id)"
              >{{teacher?'查看对应任务':selected.recommendation.label}}<ArrowRight
            /></Button>
          </div>
          <div class="memory-linked-lessons">
            <Button
              v-for="l in selected.lessons"
              :key="l.taskId"
              variant="ghost"
              size="sm"
              @click="openTarget(l.target,selected.id)"
              ><BookOpen :size="16"/><span><strong>{{ l.title }}</strong><small v-if="lessonContext(l)">{{ lessonContext(l) }}</small></span></Button
            >
          </div></template
        ></div>
        <div class="memory-evidence-list"><article
          v-for="e in [...evidence].reverse()"
          :key="e.evidenceId"
          class="memory-evidence"
          :data-evidence-id="e.evidenceId"
          :data-source-type="e.sourceType"
        >
          <div>
            <Status
              :tone="
                ['independent_incorrect', 'retest_failed'].includes(e.outcome)
                  ? 'amber'
                  : 'neutral'
              "
              >{{ evidenceLabel(e) }}</Status
            ><time>{{ e.timeReliable===false?'时间待核对':time(e.occurredAt) }}</time>
          </div>
          <button class="student-memory-evidence-toggle" :aria-expanded="evidenceOpen===e.evidenceId" @click="evidenceOpen=evidenceOpen===e.evidenceId?null:e.evidenceId"><h3>{{e.equation||e.prompt||e.label}}</h3><ChevronRight :size="16"/></button>
          <template v-if="evidenceOpen===e.evidenceId">
          <p v-if="e.answer" class="memory-answer">原作答 {{ e.answer }}</p>
          <p v-if="e.reason" class="preserve-lines">{{ e.reason }}</p>
          <p v-if="e.sourceType === 'wrong'">
            {{ e.causeConfirmed ? "已确认错因" : "错因待确认"
            }}{{ e.cause ? " 　 " + e.cause : "" }}
          </p>
          <div class="memory-evidence-actions">
            <Button
              v-if="e.target"
              variant="ghost"
              size="sm"
              @click="
                openTarget(e.target,selected?.id)
              "
              >{{teacher?'查看原任务':e.wrongId?'打开错题':'查看原任务'}}<ArrowRight /></Button
            ><Button variant="ghost" size="sm" @click="edit(e)">{{
              teacher ? "核对与修订" : "提出纠正"
            }}</Button>
          </div>
          <details>
            <summary>来源</summary>
            <p>{{ e.evidenceId }}</p><p v-if="e.timeReliable===false">原始时间 {{e.rawOccurredAt}} 　 {{e.timeBasis}}</p>
            <p>{{ e.lessonVersionId || "个人独立记录，无课程版本" }}</p>
            <p>{{ e.verification }}{{ e.helped ? " 　 使用帮助" : "" }}</p>
          </details>
          </template>
        </article>
        <details v-if="selected?.stateHistory.length" class="memory-audit">
          <summary>
            状态变化<InfoTip label="历史状态范围"
              >按当前规则与当时已有事实回算，不覆盖原始记录。</InfoTip
            >
          </summary>
          <p v-for="s in selected.stateHistory" :key="s.evidenceId">
            {{ time(s.at) }} 　 {{ s.label }}
          </p>
        </details>
        <p v-if="!evidence.length" class="memory-empty-evidence">
          再完成一些独立练习后，这里会更新。
        </p>
        <details v-if="data.audit.length" class="memory-audit">
          <summary>修订记录</summary>
          <article v-for="a in auditEntries" :key="a.id">
            <time>{{ time(a.createdAt) }}</time
            ><strong>{{
              {
                knowledge_correction: "教师修订关联",
                correction_request: "学生纠正请求",
                observation: "教师观察",
                review_required: "需要复核",
                review_content: "教师指定复习",
                snooze: "稍后处理",
              }[a.kind]
            }}</strong>
            <p>{{ a.details.reason }}</p>
            <p v-if="a.kind === 'knowledge_correction'">
              {{ a.details.original.knowledgeIds.join("、") }} →
              {{ a.details.knowledgeIds.join("、") }}
            </p>
            <p v-if="a.details.note">{{ a.details.note }}</p>
          </article>
        </details>
      </div></section>
    </div></template
  >
  <Surface v-else-if="!loading && !error"
    ><div class="empty-state">
      <h2>{{ teacher ? "选择班级与学生" : "暂无学习记忆" }}</h2>
    </div></Surface
  >
  <AppDialog
    :open="!!editing"
    title="核对学习记录"
    @update:open="!$event && (editing = null)"
    ><template v-if="editing"
      ><p>{{ editing.equation || editing.prompt || editing.label }}</p>
      <label v-if="teacher" class="field-label" for="memory-kind"
        >处理方式</label
      ><select v-if="teacher" id="memory-kind" v-model="kind">
        <option value="knowledge_correction">修订知识点关联</option>
        <option value="observation">补充教学观察</option>
        <option value="review_required">标记需要复核</option>
        <option value="review_content">指定复习内容</option></select
      ><label
        v-if="['knowledge_correction', 'correction_request'].includes(kind)"
        class="field-label"
        for="memory-knowledge"
        >{{ teacher ? "修订后知识点" : "建议关联知识点" }}</label
      ><select
        v-if="['knowledge_correction', 'correction_request'].includes(kind)"
        id="memory-knowledge"
        v-model="knowledgeIds"
        multiple
      >
        <option
          v-for="p in data?.knowledgeOptions || []"
          :key="p.id"
          :value="p.id"
        >
          {{ p.name }}
        </option></select
      ><label
        v-if="kind === 'review_content'"
        class="field-label"
        for="memory-target"
        >复习内容</label
      ><select
        v-if="kind === 'review_content'"
        id="memory-target"
        v-model="target"
      >
        <option value="">选择实际课时或错题</option>
        <option v-for="t in targets" :key="t.target" :value="t.target">
          {{ t.title }}
        </option></select
      ><label class="field-label" for="memory-reason">理由</label
      ><Textarea id="memory-reason" v-model="reason" /><label
        v-if="teacher"
        class="field-label"
        for="memory-note"
        >教学观察</label
      ><Textarea v-if="teacher" id="memory-note" v-model="note" />
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <Button
        :disabled="
          saving ||
          loading ||
          !reason.trim() ||
          (kind === 'knowledge_correction' && !knowledgeIds.length)
        "
        @click="submit"
        >{{ saving ? "正在保存…" : "确认保存修订" }}</Button
      ></template
    ></AppDialog
  >
</template>

<style scoped>
.teacher-memory-focus.has-detail{display:block}
.teacher-memory-focus.has-detail .memory-detail{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(0,1.2fr);gap:32px;border-left:0}
.memory-detail-context,.memory-evidence-list{min-width:0}
.teacher-memory-focus .memory-evidence:first-child{padding-top:0;border-top:0}
.memory-linked-lessons{flex-direction:column;align-items:stretch}
.memory-linked-lessons>button{justify-content:flex-start;text-align:left;height:auto;min-height:42px;white-space:normal;padding:9px 10px;gap:10px}
.memory-linked-lessons>button>svg{flex-shrink:0}
.memory-linked-lessons strong{display:block;font-size:13px;font-weight:500}
.memory-linked-lessons small{display:block;font-size:11px;line-height:1.7;color:var(--muted-foreground);font-variant-numeric:tabular-nums}
@media(max-width:1100px){.teacher-memory-focus.has-detail .memory-detail{grid-template-columns:1fr}.teacher-memory-focus .memory-evidence:first-child{padding-top:20px;border-top:1px solid var(--border)}}
</style>
