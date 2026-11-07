import { defineStore } from "pinia";
import {
  createPlatform,
  createId,
  platformService,
} from "./services/platform.js";
import { questions } from "./data.js";

export const useLearning = defineStore("platform", {
  state: () => ({
    data: createPlatform(),
    status: "loading",
    error: "",
    saveError: "",
    saving: false,
    publishing: false,
    savedAt: null,
    revision: 0,
  }),
  getters: {
    task: (state) =>
      state.data.tasks.find((task) => task.id === state.data.activeTaskId) ||
      null,
    record() {
      return this.task ? this.data.records[this.task.id] : null;
    },
    blocks: (state) => state.data.lessonDraft.blocks,
    lessonGoal: (state) => state.data.lessonDraft.goal,
    students() {
      if (!this.record) return [];
      const record = this.record;
      return [
        {
          id: "student-lin",
          name: "小林同学",
          initials: "林",
          status: record.completed
            ? "已提交"
            : record.observation || record.attempts.length
              ? "学习中"
              : "未开始",
          progress: record.completed
            ? 100
            : record.attempts.length
              ? 80
              : record.observation
                ? 40
                : 0,
          help: `${record.helps.length} 次帮助`,
          result: record.attempts.some((item) => item.correct && !item.helped)
            ? "新题独立完成"
            : "待独立检查",
        },
      ];
    },
  },
  actions: {
    async load() {
      this.status = "loading";
      this.error = "";
      try {
        this.data = await platformService.load();
        this.status = "ready";
      } catch (error) {
        this.error = error.message;
        this.status = "error";
      }
    },
    touch() {
      this.revision++;
      if (this.record) this.record.updatedAt = new Date().toISOString();
    },
    async save() {
      // Serialize writes and repeat when edits arrive during an in-flight save.
      if (this.saving) {
        while (this.saving)
          await new Promise((resolve) => setTimeout(resolve, 20));
        return !this.saveError;
      }
      this.saving = true;
      this.saveError = "";
      try {
        let revision;
        do {
          revision = this.revision;
          await platformService.save(this.data);
        } while (revision !== this.revision);
        this.savedAt = new Date().toISOString();
        return true;
      } catch (error) {
        this.saveError = error.message;
        return false;
      } finally {
        this.saving = false;
      }
    },
    selectTask(id) {
      if (!this.data.tasks.some((task) => task.id === id)) return false;
      this.data.activeTaskId = id;
      this.touch();
      return true;
    },
    async publish() {
      if (this.publishing) return null;
      this.publishing = true;
      try {
        if (this.saving) {
          while (this.saving)
            await new Promise((resolve) => setTimeout(resolve, 20));
        }
        this.data = await platformService.publishLesson(this.data);
        this.touch();
        return this.task;
      } finally {
        this.publishing = false;
      }
    },
    useCase() {
      const example = this.data.publishedCase || this.data.caseDraft;
      this.data.lessonDraft.caseId = example.id;
      this.data.lessonDraft.blocks[0].content = example.content;
      this.data.lessonDraft.updatedAt = new Date().toISOString();
      this.touch();
    },
    requestHelp(question, kind, message, image = "") {
      if (!this.record) return;
      this.record.helps.push({
        id: createId("help"),
        taskId: this.task.id,
        question,
        kind,
        message,
        image,
        attemptNumber: this.record.attempts.length + 1,
        createdAt: new Date().toISOString(),
      });
      this.touch();
    },
    submitAnswer(question, answer, reason, helped) {
      if (!this.record || !answer.trim()) throw new Error("请先填写答案。");
      const item = {
        id: createId("attempt"),
        taskId: this.task.id,
        question,
        answer: answer.trim(),
        reason,
        helped,
        correct:
          answer.trim() === (this.task.questions || questions)[question].answer,
        createdAt: new Date().toISOString(),
      };
      this.record.attempts.push(item);
      if (!item.correct)
        this.record.wrongQuestions.push({
          id: createId("wrong"),
          taskId: this.task.id,
          attemptId: item.id,
          prompt: (this.task.questions || questions)[question].equation,
          answer: item.answer,
          reason,
          image: "",
          createdAt: item.createdAt,
        });
      this.touch();
      return item;
    },
    addWrong(prompt, image) {
      if (!prompt.trim()) throw new Error("请填写题目内容。");
      const item = {
        id: createId("wrong"),
        taskId: this.task.id,
        prompt,
        image,
        answer: "",
        createdAt: new Date().toISOString(),
      };
      this.record.wrongQuestions.push(item);
      this.touch();
      return item;
    },
    submitRepair(wrongId, answer, reason) {
      if (!answer.trim()) throw new Error("请先填写答案。");
      const item = {
        id: createId("repair"),
        taskId: this.task.id,
        wrongId,
        answer,
        reason,
        correct: answer.trim() === "7",
        createdAt: new Date().toISOString(),
      };
      this.record.repairs.push(item);
      this.touch();
      return item;
    },
    submitLesson() {
      this.record.completed = true;
      this.record.submittedAt = new Date().toISOString();
      this.touch();
    },
    saveFeedback(text) {
      if (!text.trim()) throw new Error("请填写反馈内容。");
      this.record.feedback = text;
      this.record.feedbackAt = new Date().toISOString();
      this.data.messages.unshift({
        id: createId("message"),
        taskId: this.task.id,
        title: `${this.task.title} · 教师反馈`,
        createdAt: this.record.feedbackAt,
      });
      this.touch();
    },
    async reset() {
      if (this.saving) {
        while (this.saving)
          await new Promise((resolve) => setTimeout(resolve, 20));
      }
      this.data = await platformService.reset();
      this.saveError = "";
      this.status = "ready";
      this.touch();
    },
  },
});
