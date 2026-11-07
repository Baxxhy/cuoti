<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { motion } from "motion-v";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Calculator,
  ChevronRight,
  CircleCheck,
  FileText,
  Lightbulb,
  Target,
} from "lucide-vue-next";
import { navigate } from "@/lib/navigation.js";
import { useLearning } from "@/store.js";
const route = useRoute();
const store = useLearning();
const teacher = computed(() => route.name === "teacher");
const independent = computed(
  () => store.attempts.filter((item) => !item.helped && item.correct).length,
);
</script>
<template>
  <template v-if="route.name === 'home' || teacher">
    <PageHeading :title="teacher ? '教学概览' : '我的学习'" />
    <div class="home-grid">
      <div class="home-main">
        <motion.section class="lesson-hero" :while-hover="{ y: -2 }"
          ><img
            src="/images/equation-balance.png"
            alt="等式性质课程的天平封面"
            fetchpriority="high" />
          <div class="hero-copy">
            <span class="hero-category">七年级数学 · 一元一次方程</span>
            <h2>等式性质</h2>
            <Button size="lg" @click="navigate(teacher ? 'prepare' : 'learn')"
              >{{
                teacher
                  ? "继续备课"
                  : store.completed
                    ? "回看本课"
                    : "继续学习"
              }}<ArrowRight :size="16"
            /></Button></div
        ></motion.section>
        <section class="task-section">
          <SectionHeading
            :title="teacher ? '班级任务' : '学习任务'"
            action="全部任务"
            :route="teacher ? 'class' : 'courses'"
          />
          <div class="task-row">
            <span class="task-icon blue"><FileText :size="20" /></span>
            <div class="task-description">
              <h3>等式性质</h3>
              <p>七年级一班</p>
            </div>
            <Status :tone="store.completed ? 'green' : 'blue'">{{
              store.completed ? "已提交" : store.published ? "已发布" : "学习中"
            }}</Status
            ><Button
              variant="ghost"
              @click="navigate(teacher ? 'insights' : 'learn')"
              >{{ teacher ? "查看作答" : "继续" }}<ChevronRight
            /></Button>
          </div>
          <div class="task-row">
            <span class="task-icon amber"><Lightbulb :size="20" /></span>
            <div class="task-description">
              <h3>
                {{ teacher ? "等式性质 · 待反馈" : "等式性质 · 错题订正" }}
              </h3>
            </div>
            <Status>{{ teacher ? "待反馈" : "待复习" }}</Status
            ><Button
              variant="ghost"
              @click="navigate(teacher ? 'insights' : 'repair')"
              >{{ teacher ? "查看" : "订正" }}<ChevronRight
            /></Button>
          </div>
        </section>
        <section>
          <SectionHeading :title="teacher ? '教学资源' : '学习入口'" />
          <div class="explore-grid">
            <button
              class="explore-card lilac"
              @click="navigate(teacher ? 'case-detail' : 'courses')"
            >
              <div class="explore-art">
                <Calculator :size="48" :stroke-width="1.2" /><span
                  class="formula-detail"
                  >x + a = b</span
                >
              </div>
              <h3>{{ teacher ? "天平与等式性质" : "一元一次方程" }}</h3>
              <ArrowUpRight class="explore-arrow" :size="18" /></button
            ><button
              class="explore-card peach"
              @click="navigate(teacher ? 'cases' : 'wrong')"
            >
              <div class="explore-art">
                <BookOpen :size="48" :stroke-width="1.2" />
              </div>
              <h3>{{ teacher ? "教学案例" : "错题帮" }}</h3>
              <ArrowUpRight class="explore-arrow" :size="18" />
            </button>
          </div>
        </section>
      </div>
      <aside class="home-aside">
        <Surface class="learning-rhythm"
          ><div class="section-heading">
            <h2>本课进度</h2>
            <Target :size="17" class="muted" />
          </div>
          <div class="rhythm-total">
            <strong>{{ store.completed ? 5 : 2 }}<span>/ 5</span></strong>
            <p>已完成活动</p>
          </div>
          <div class="activity-dots">
            <div
              v-for="(label, index) in ['观察', '解释', '练习', '检查', '反馈']"
              :key="label"
            >
              <span :class="{ done: index < (store.completed ? 5 : 2) }"
                ><CircleCheck
                  v-if="index < (store.completed ? 5 : 2)"
                  :size="17" /><span v-else class="dot-inner" /></span
              ><small>{{ label }}</small>
            </div>
          </div></Surface
        ><Surface class="next-step"
          ><h2>{{ teacher ? "学情反馈" : "独立检查" }}</h2>
          <Button
            variant="outline"
            class="w-full"
            @click="navigate(teacher ? 'insights' : 'check')"
            >{{ teacher ? "查看学生作答" : "开始检查" }}<ArrowRight /></Button
        ></Surface>
        <div class="small-learning-record">
          <div class="section-heading"><h3>检查记录</h3></div>
          <div>
            <span>尝试次数</span><strong>{{ store.attempts.length }} 次</strong>
          </div>
          <div>
            <span>独立答对</span><strong>{{ independent }} 次</strong>
          </div>
          <button @click="navigate('records')">
            全部记录<ChevronRight :size="14" />
          </button>
        </div>
      </aside>
    </div>
  </template>
  <template v-else-if="route.name === 'courses'"
    ><PageHeading title="课程" />
    <div class="course-collection">
      <div class="course-cover">
        <img src="/images/equation-balance.png" alt="一元一次方程课程封面" />
      </div>
      <div class="course-overview">
        <Status tone="blue">七年级数学</Status>
        <h2>一元一次方程</h2>
        <RouteButton route="learn">开始等式性质</RouteButton>
      </div>
    </div>
    <SectionHeading title="单元课时" /><Surface
      ><div class="lesson-row">
        <span class="lesson-number">1</span>
        <div><h3>等式性质</h3></div>
        <Status tone="green">已开放</Status
        ><RouteButton route="learn" secondary>进入课时</RouteButton>
      </div>
      <div
        v-for="(name, index) in ['解简单的一元一次方程', '用方程解决生活问题']"
        :key="name"
        class="lesson-row"
      >
        <span class="lesson-number">{{ index + 2 }}</span>
        <div>
          <h3>{{ name }}</h3>
        </div>
        <Status>待开放</Status>
      </div></Surface
    ></template
  >
  <template v-else
    ><PageHeading title="学习记录" /><Surface
      ><SectionHeading title="等式性质 · 检查记录" />
      <div
        v-for="(attempt, index) in store.attempts"
        :key="index"
        class="record-row"
      >
        <span class="record-icon"><CircleCheck :size="18" /></span>
        <div>
          <h3>第 {{ index + 1 }} 次作答 · {{ attempt.answer }}</h3>
          <p v-if="attempt.reason">{{ attempt.reason }}</p>
        </div>
        <Status :tone="attempt.correct ? 'green' : 'amber'">{{
          attempt.correct ? "数值正确" : "需订正"
        }}</Status
        ><Status>{{ attempt.helped ? "获得帮助" : "独立作答" }}</Status>
      </div>
      <div v-if="!store.attempts.length" class="empty-state">
        <h3>暂无检查记录</h3>
        <RouteButton route="check">开始检查</RouteButton>
      </div></Surface
    ></template
  >
</template>
