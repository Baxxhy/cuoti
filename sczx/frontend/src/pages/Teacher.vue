<script setup>
import { computed, inject, ref, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import draggable from "vuedraggable";
import { motion } from "motion-v";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Eye,
  FileText,
  GripVertical,
  LibraryBig,
  Plus,
  Save,
  Search,
  Send,
  Sparkles,
  Star,
  Users,
  WandSparkles,
} from "lucide-vue-next";
import Workspace from "@/components/Workspace.vue";
import LessonPreview from "@/components/LessonPreview.vue";
import { navigate } from "@/lib/navigation.js";
import { useLearning } from "@/store.js";
import { demoStudents, initialBlocks } from "@/data.js";
const route = useRoute(),
  store = useLearning(),
  notify = inject("notify");
const page = computed(() => route.name),
  query = ref(""),
  tab = ref("all"),
  grade = ref("math"),
  unit = ref("equation"),
  previewTab = ref("student"),
  modal = ref(""),
  busyBlock = ref(""),
  student = ref(null),
  supplement = ref(false),
  invite = ref(false),
  draft = ref(store.feedback),
  supplementText = ref(
    "回到等式两边同时减去相同数的完整过程，再完成一道独立检查题。",
  ),
  publishClass = ref("demo");
const matches = computed(
  () =>
    !query.value ||
    ["等式", "天平", "同时", "变号", "学生", "困难", "相同"].some((word) =>
      query.value.includes(word),
    ),
);
const dialogOpen = computed({
  get: () => !!modal.value,
  set: (value) => {
    if (!value) modal.value = "";
  },
});
let generationTimer;
function regenerate(id) {
  busyBlock.value = id;
  generationTimer = window.setTimeout(() => {
    store.updateBlock(
      id,
      initialBlocks.find((block) => block.id === id).content +
        " 请学生先表达自己的预测，再用一个具体例子说明理由。",
    );
    busyBlock.value = "";
    notify("演示教学建议已生成，可以继续修改");
  }, 700);
}
onBeforeUnmount(() => window.clearTimeout(generationTimer));
function reorderKeyboard(event, index) {
  if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
  event.preventDefault();
  const target = index + (event.key === "ArrowUp" ? -1 : 1);
  if (target < 0 || target >= store.blocks.length) return;
  const blocks = [...store.blocks];
  [blocks[index], blocks[target]] = [blocks[target], blocks[index]];
  store.blocks = blocks;
  notify("教学活动与学生预览已同步排序");
}
async function copyInvite() {
  try {
    await navigator.clipboard.writeText("SCZX-7A");
    notify("班级口令已复制");
  } catch {
    notify("班级口令：SCZX-7A");
  }
}
</script>
<template>
  <template v-if="page === 'cases'">
    <PageHeading title="教学案例" />
    <div class="case-toolbar">
      <div class="search-field">
        <Search :size="17" /><Input
          v-model="query"
          aria-label="搜索教学案例"
          placeholder="搜索知识点、目标或学生困难"
        />
      </div>
      <AppSelect
        v-model="grade"
        label="选择学科年级"
        :options="[{ value: 'math', label: '七年级数学' }]"
      /><AppSelect
        v-model="unit"
        label="选择单元"
        :options="[{ value: 'equation', label: '一元一次方程' }]"
      />
    </div>
    <AppTabs
      v-model="tab"
      :items="[
        { value: 'all', label: '全部案例' },
        { value: 'favorite', label: '我的收藏' },
      ]"
    />
    <div v-if="matches && (tab === 'all' || store.favorite)" class="case-grid">
      <motion.article class="featured-case" :while-hover="{ y: -3 }"
        ><div class="case-image">
          <img
            src="/images/equation-balance.png"
            alt="天平与等式教学案例封面"
          /><Status>等式性质</Status>
        </div>
        <div class="featured-case-body">
          <div class="case-meta">
            <BookOpen :size="14" /><span>团队编写案例示例</span><span>·</span
            ><span>观察与追问</span>
          </div>
          <h2>天平与等式性质</h2>
          <p>
            当学生会说“移过去变号”，却说不清为什么时，让观察、操作与解释重新连接起来。
          </p>
          <div class="case-footer">
            <span><Users :size="14" />适用初学等式性质的学生</span
            ><RouteButton route="case-detail"
              >阅读案例<ArrowUpRight
            /></RouteButton>
          </div></div
      ></motion.article>
      <aside class="case-reading-guide">
        <h2>学生困难</h2>
        <div class="case-question-links">
          <button
            v-for="item in [
              '学生只改变等式的一边',
              '学生机械记忆移项变号',
              '怎样检查学生独立理解',
            ]"
            :key="item"
            @click="query = item"
          >
            {{ item }}<ArrowUpRight :size="15" />
          </button>
        </div>
        <InfoTip label="内容来源说明"
          >公开来源与使用条件将在内容整理阶段逐项核对。当前为完整流程的自编示例。</InfoTip
        >
      </aside>
    </div>
    <Surface v-else
      ><div class="empty-state">
        <h3>暂时没有匹配的案例</h3>
        <Button
          variant="outline"
          @click="
            query = '';
            tab = 'all';
          "
          >浏览全部案例</Button
        >
      </div></Surface
    >
  </template>
  <template v-else-if="page === 'case-detail'">
    <div class="back-line">
      <Button variant="ghost" @click="navigate('cases')"
        ><ArrowLeft />返回教学案例</Button
      >
    </div>
    <div class="case-detail-header">
      <div>
        <Status tone="blue">等式性质 · 案例示例</Status>
        <h1>天平与等式性质</h1>
      </div>
      <div class="heading-actions">
        <Button
          variant="outline"
          @click="
            store.favorite = !store.favorite;
            notify(store.favorite ? '案例已加入收藏' : '已取消收藏');
          "
          ><Star :fill="store.favorite ? 'currentColor' : 'none'" />{{
            store.favorite ? "已收藏" : "收藏案例"
          }}</Button
        ><RouteButton route="prepare">用于备课</RouteButton>
      </div>
    </div>
    <div class="case-detail-grid">
      <article class="case-article">
        <div class="case-article-section">
          <span class="article-marker"><Eye :size="19" /></span>
          <div>
            <h2>预测与操作</h2>
            <p>
              展示两边相等的天平，请学生预测两边同时加入相同数量的砝码后，平衡会不会改变。让学生先表达自己的理由，再动手验证。
            </p>
            <blockquote>
              “如果只在左边加一个，它还会平衡吗？你为什么这样想？”
            </blockquote>
          </div>
        </div>
        <div class="case-article-section">
          <span class="article-marker"><FileText :size="19" /></span>
          <div>
            <h2>用等式表达</h2>
            <p>
              记录两边共同变化的完整步骤，让学生说出“同时”和“相同”分别意味着什么。再用只改变一边的例子进行对照。
            </p>
            <div class="article-equation">
              a = b <span>⇒</span> a + c = b + c
            </div>
          </div>
        </div>
        <div class="case-article-section">
          <span class="article-marker"><Sparkles :size="19" /></span>
          <div>
            <h2>根据回应调整</h2>
            <p>
              当学生只说“移项变号”时，请其写出两边同时减去同一个数的过程。学生能够解释后，再改变数字给出新题，观察能否独立完成。
            </p>
          </div>
        </div>
      </article>
      <aside>
        <Surface class="case-use-card"
          ><h3>这篇案例适合什么时候？</h3>
          <div>
            <span>学习基础</span>
            <p>理解相等关系，掌握加减法</p>
          </div>
          <div>
            <span>常见困难</span>
            <p>只改变一边，机械记忆变号</p>
          </div>
          <div>
            <span>教学目标</span>
            <p>解释共同变化，独立应用等式性质</p>
          </div>
          <div class="source-box">
            <BookOpen :size="16" />
            <p>
              团队编写示例<InfoTip label="案例出处"
                >当前案例为团队编写示例，真实来源将在内容建设阶段补充。</InfoTip
              >
            </p>
          </div>
          <RouteButton route="prepare">带入我的教案</RouteButton></Surface
        >
      </aside>
    </div>
  </template>
  <template v-else-if="page === 'prepare'">
    <div class="back-line">
      <Button variant="ghost" @click="navigate('teacher')"
        ><ArrowLeft />返回教学概览</Button
      ><span>我的教案 / 等式性质</span>
    </div>
    <PageHeading title="等式性质 · 备课"
      ><Button
        variant="outline"
        @click="
          notify(
            store.save()
              ? '教案内容已保存到本地浏览器'
              : '保存失败，请检查浏览器存储空间',
          )
        "
        ><Save />保存教案</Button
      ><Button variant="outline" @click="modal = 'preview'"
        ><Eye />学生预览</Button
      ><Button @click="modal = 'publish'"
        ><Send />{{ store.published ? "再次发布" : "发布任务" }}</Button
      ></PageHeading
    >
    <Workspace
      ><template #primary
        ><div class="lesson-editor">
          <div class="editor-intro">
            <span><FileText :size="16" />教师教学安排</span
            ><Status>自动保存到本地</Status>
          </div>
          <label class="field-label" for="lesson-goal">本课目标</label
          ><Input id="lesson-goal" v-model="store.lessonGoal" /><label
            class="field-label"
            for="student-base"
            >学生基础</label
          ><Input id="student-base" v-model="store.studentBase" />
          <div class="editor-section-heading">
            <h2>教学活动</h2>
            <InfoTip label="调整活动顺序"
              >拖动手柄或聚焦手柄后按上下方向键调整顺序。</InfoTip
            >
          </div>
          <draggable
            v-model="store.blocks"
            item-key="id"
            handle=".drag-handle"
            :force-fallback="true"
            :fallback-on-body="true"
            :fallback-tolerance="3"
            class="sortable-list"
            :animation="0"
            ghost-class="dragging"
            @end="notify('教学活动与学生预览已同步排序')"
            ><template #item="{ element: block, index }"
              ><div class="editor-block">
                <div class="editor-block-heading">
                  <button
                    class="drag-handle"
                    :aria-label="`拖动排序：${block.title}`"
                    @keydown="reorderKeyboard($event, index)"
                  >
                    <GripVertical :size="16" />
                  </button>
                  <h3>{{ block.title }}</h3>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    :aria-label="`重新生成${block.title}`"
                    :disabled="busyBlock === block.id"
                    @click="regenerate(block.id)"
                    ><WandSparkles
                  /></Button>
                </div>
                <Textarea
                  v-model="block.content"
                  :aria-label="block.title"
                  :disabled="busyBlock === block.id"
                /></div></template></draggable
          ><button class="reference-link" @click="navigate('case-detail')">
            <LibraryBig :size="16" /><span>参考案例 · 天平与等式性质</span
            ><ArrowUpRight :size="15" />
          </button></div></template
      ><template #secondary
        ><div class="preview-pane-tabs">
          <AppTabs
            v-model="previewTab"
            :items="[
              { value: 'student', label: '学生内容' },
              { value: 'source', label: '参考经验' },
            ]"
          />
        </div>
        <LessonPreview v-if="previewTab === 'student'" />
        <div v-else class="preview-source">
          <BookOpen :size="28" />
          <h2>天平与等式性质</h2>
          <p>
            先预测，再操作，最后解释。根据学生回应调整讲法，将“同时”和“相同”落实到每一步。
          </p>
          <RouteButton route="case-detail" secondary>阅读完整案例</RouteButton>
        </div></template
      ></Workspace
    >
    <AppDialog
      v-model:open="dialogOpen"
      :title="modal === 'preview' ? '学生预览' : '发布学习任务'"
      :content-class="
        modal === 'preview' ? 'lesson-preview-dialog' : 'publish-dialog'
      "
      ><template v-if="modal === 'preview'"
        ><LessonPreview /><Button @click="modal = 'publish'"
          >继续发布<ArrowRight /></Button></template
      ><template v-else
        ><div class="publish-course">
          <FileText :size="22" />
          <div>
            <strong>等式性质</strong
            ><small>{{ store.blocks.length }} 个活动</small>
          </div>
        </div>
        <label class="field-label" for="publish-class">发布班级</label
        ><AppSelect
          id="publish-class"
          v-model="publishClass"
          label="选择发布班级"
          :options="[
            { value: 'demo', label: '七年级一班 · 演示班级' },
          ]" /><label class="field-label" for="due-date">建议完成日期</label
        ><Input id="due-date" v-model="store.dueDate" type="date" />
        <p class="small-caption">
          发布后，七年级一班的学生可在任务列表中进入本课。当前为演示发布。
        </p>
        <Button
          @click="
            store.published = true;
            modal = '';
            navigate('class');
            notify('课时已模拟发布给七年级一班');
          "
          >确认发布<ArrowRight /></Button></template
    ></AppDialog>
  </template>
  <template v-else-if="page === 'class'">
    <PageHeading title="七年级一班"
      ><Button variant="outline" @click="invite = true"
        ><Users />邀请学生</Button
      ><RouteButton route="prepare">发布新任务</RouteButton></PageHeading
    >
    <div class="class-banner">
      <div class="class-mark"><Users :size="35" :stroke-width="1.4" /></div>
      <p>3 名演示学生 · 数学 · 一元一次方程</p>
      <div class="student-avatars">
        <span v-for="item in demoStudents" :key="item.name">{{
          item.initials
        }}</span>
      </div>
    </div>
    <SectionHeading title="班级学习任务" /><Surface
      ><div class="class-task">
        <span class="task-icon blue"><FileText :size="23" /></span>
        <div>
          <h3>等式性质 · 观察、解释与应用</h3>
          <div class="class-task-meta">
            <Status :tone="store.published ? 'green' : 'neutral'">{{
              store.published ? "已模拟发布" : "示例任务"
            }}</Status
            ><span>1 / 3 名演示学生已提交</span>
          </div>
        </div>
        <RouteButton route="insights">查看作答与反馈</RouteButton>
      </div></Surface
    ><AppDialog v-model:open="invite" title="邀请学生"
      ><div class="invitation-code">SCZX-7A</div>
      <InfoTip label="班级口令说明"
        >此口令仅用于演示，不会加入真实班级。</InfoTip
      ><Button @click="copyInvite">复制口令</Button></AppDialog
    >
  </template>
  <template v-else>
    <div class="back-line">
      <Button variant="ghost" @click="navigate('class')"
        ><ArrowLeft />七年级一班</Button
      ><span>等式性质 / 学情反馈</span>
    </div>
    <PageHeading title="学情反馈"
      ><Button @click="supplement = true"
        ><Plus />安排补充学习</Button
      ></PageHeading
    >
    <div class="insight-summary">
      <div>
        <span>参与学生</span><strong>3<small>人</small></strong>
      </div>
      <div>
        <span>已经提交</span><strong>1<small>/ 3</small></strong>
      </div>
      <div>
        <span>新题独立完成</span><strong>1<small>人</small></strong>
      </div>
      <div class="summary-context"><Status>演示学情</Status></div>
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
            <tr v-for="(item, index) in demoStudents" :key="item.name">
              <td>
                <span :class="['student-name', `avatar-${index}`]"
                  ><span>{{ item.initials }}</span
                  >{{ item.name }}</span
                >
              </td>
              <td>
                <div class="table-progress">
                  <span>{{ item.status }}</span
                  ><Progress
                    :model-value="item.progress"
                    :aria-label="`${item.name}学习进度`"
                  />
                </div>
              </td>
              <td>{{ item.help }}</td>
              <td>
                <Status
                  :tone="item.result === '新题独立完成' ? 'green' : 'neutral'"
                  >{{ item.result }}</Status
                >
              </td>
              <td>
                <Button variant="ghost" @click="student = index"
                  >查看过程<ArrowUpRight
                /></Button>
              </td>
            </tr>
          </tbody>
        </table></div
    ></Surface>
    <div class="two-column insight-detail">
      <Surface class="common-difficulty"
        ><div class="section-heading">
          <h2>值得关注的共同困难</h2>
          <Sparkles :size="17" />
        </div>
        <h3>会说“变号”，却还没说清为什么。</h3>
        <p>
          在示例作答中，学生消去了等式左边的数，却没有对右边进行相同运算。可以回到完整步骤，再安排新题。
        </p>
        <RouteButton route="cases" secondary
          >查找相关教学经验</RouteButton
        ></Surface
      ><Surface
        ><SectionHeading title="给学生的反馈" /><Textarea
          v-model="draft"
          aria-label="教师反馈"
        />
        <div class="paper-actions">
          <Button
            @click="
              store.feedback = draft;
              notify('反馈已保存，学生可以在本课结果中查看');
            "
            ><Check />确认并保存</Button
          >
        </div></Surface
      >
    </div>
    <AppDialog
      :open="student !== null"
      :title="`${student !== null ? demoStudents[student].name : ''}的学习过程`"
      content-class="student-detail-dialog"
      @update:open="(value) => !value && (student = null)"
      ><div v-if="student === 0" class="attempt-timeline">
        <div>
          <span class="timeline-dot" /><small>最初的作答</small>
          <div class="math-equation">x + 3 = 8 → x = 8 + 3</div>
        </div>
        <div>
          <span class="timeline-dot" /><small>获得提示</small>
          <p>试着在等式两边同时减去 3。</p>
        </div>
        <div>
          <span class="timeline-dot green" /><small>新题独立应用</small>
          <p>y + 4 = 11，回答 y = 7。</p>
          <Status tone="green">独立完成</Status>
        </div>
      </div>
      <div v-else class="empty-state">
        <h3>{{ student !== null ? demoStudents[student].status : "" }}</h3>
        <p>
          {{
            student !== null ? demoStudents[student].help : ""
          }}，后续作答在完成后展示。
        </p>
      </div></AppDialog
    ><AppDialog v-model:open="supplement" title="安排补充学习"
      ><label class="field-label" for="supplement-content">补充内容</label
      ><Textarea id="supplement-content" v-model="supplementText" /><Button
        @click="
          supplement = false;
          notify('已模拟安排补充学习');
        "
        >确认安排<Send /></Button
    ></AppDialog>
  </template>
</template>
