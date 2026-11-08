<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { ArrowRight, BookOpen, LibraryBig, Target } from "lucide-vue-next";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskList from "@/components/TaskList.vue";
const store = useLearning(),
  route = useRoute();
const teacher = computed(() => route.name === "teacher");
</script>
<template>
  <PageHeading :title="teacher ? '教学概览' : '我的学习'" />
  <div class="home-grid">
    <div class="home-main">
      <section class="lesson-hero">
        <img src="/images/equation-balance.png" alt="数学课程插画" />
        <div class="hero-copy">
          <span class="hero-category">{{ teacher?'教师工作区':store.task?.snapshot.lessonSnapshot?.grade||'学习空间' }}</span>
          <h2>{{ teacher?store.data.lesson?.title||'选择课时':store.task?.title||'探索课程' }}</h2>
          <Button
            @click="
              navigate(
                teacher
                  ? 'prepare'
                  : store.task
                    ? `learn?task=${store.task.id}`
                    : 'courses',
              )
            "
            >{{ teacher ? "继续备课" : store.task ? "继续学习" : "探索课程"
            }}<ArrowRight
          /></Button>
        </div>
      </section>
      <section>
        <SectionHeading :title="teacher ? '班级任务' : '学习任务'" /><TaskList
          :teacher="teacher"
        />
      </section>
      <section>
        <SectionHeading :title="teacher ? '教学资源' : '学习入口'" />
        <div class="explore-grid">
          <button
            class="explore-card lilac"
            @click="navigate(teacher ? 'cases' : 'courses')"
          >
            <div class="explore-art"><LibraryBig :size="48" /></div>
            <h3>{{ teacher ? "教学案例" : "课程目录" }}</h3></button
          ><button
            class="explore-card peach"
            @click="navigate(teacher ? 'class' : 'wrong')"
          >
            <div class="explore-art"><BookOpen :size="48" /></div>
            <h3>{{ teacher ? "班级教学" : "错题帮" }}</h3>
          </button>
        </div>
      </section>
    </div>
    <aside class="home-aside">
      <Surface class="learning-rhythm"
        ><div class="section-heading">
          <h2>{{ teacher ? "班级概况" : "当前任务" }}</h2>
          <Target :size="17" />
        </div>
        <div class="rhythm-total">
          <strong>{{
            teacher
              ? store.data.tasks.length
              : store.record?.attempts.length || 0
          }}</strong>
          <p>{{ teacher ? "已发布任务" : "检查题尝试" }}</p>
        </div>
        <Status
          v-if="store.record"
          :tone="store.record.completed ? 'green' : 'blue'"
          >{{ store.record.completed ? "已提交" : "学习中" }}</Status
        ></Surface
      ><Surface class="next-step"
        ><h2>{{ teacher ? "学情反馈" : "独立检查" }}</h2>
        <RouteButton :route="teacher ? 'insights' : 'check'" secondary
          >{{ teacher ? "查看学生作答" : "开始检查"
          }}<ArrowRight /></RouteButton
      ></Surface>
      <div
        v-if="store.record?.feedback && !teacher"
        class="small-learning-record"
      >
        <h3>教师反馈</h3>
        <p>{{ store.record.feedback }}</p>
        <RouteButton route="result" secondary>查看反馈</RouteButton>
      </div>
    </aside>
  </div>
</template>
