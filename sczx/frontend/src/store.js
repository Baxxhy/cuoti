import { defineStore } from "pinia";
import {
  createPlatform,
  createId,
} from "./services/platform.js";
import { api } from "./services/api.js";
import { questions } from "./data.js";

export const useLearning = defineStore("platform", {
  state: () => ({
    data: createPlatform(),
    user: null,
    authChecked: false,
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
      if (!this.task) return null;
      const records = this.data.studentRecords?.[this.task.id];
      if (Array.isArray(records) && records.length) {
        const selected = records.find((item) => item.studentId === this.data.activeStudentId);
        return selected || records[0];
      }
      return this.data.records[this.task.id] || null;
    },
    blocks: (state) => state.data.lessonDraft.blocks,
    lessonGoal: (state) => state.data.lessonDraft.goal,
    students() {
      if (!this.task) return [];
      const records = this.data.studentRecords?.[this.task.id] || (this.record ? [this.record] : []);
      return records.map((record) => ({
          id: record.studentId,
          name: record.studentName || "学生",
          initials: (record.studentName || "学").slice(0, 1),
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
        }));
    },
  },
  actions: {
    async initialize() {
      try {
        const result = await api.me();
        this.user = result.user;
        await this.load();
      } catch (error) {
        this.user = null;
        this.status = "unauthenticated";
        this.error = error.status === 401 ? "" : error.message;
      } finally {
        this.authChecked = true;
      }
    },
    async login(username, password) {
      const result = await api.login(username, password);
      this.user = result.user;
      await this.load();
    },
    async logout() {
      if (!(await this.save())) throw new Error(this.saveError || "当前修改尚未保存，请稍后重试退出。");
      await api.logout();
      this.user = null;
      this.data = createPlatform();
      this.status = "unauthenticated";
    },
    async load() {
      this.status = "loading";
      this.error = "";
      try {
        this.data = await api.platform();
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
          await api.savePlatform(this.data);
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
    selectStudent(id) {
      if (!this.task) return false;
      const record = this.data.studentRecords?.[this.task.id]?.find((item) => item.studentId === id);
      if (!record) return false;
      this.data.activeStudentId = id;
      this.data.records[this.task.id] = record;
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
        if (!(await this.save())) throw new Error(this.saveError || "教案保存失败，请重试。");
        const classroomId = this.data.publishClassId || this.data.classroom?.id;
        if (!classroomId) throw new Error("请先创建班级再发布任务。");
        const response = await api.publish(classroomId, this.data.lessonDraft);
        await this.load();
        this.data.activeTaskId = response.taskId;
        this.touch();
        return this.task;
      } finally {
        this.publishing = false;
      }
    },
    async publishCase() {
      if (!(await this.save())) throw new Error(this.saveError || "案例草稿保存失败，请重试。");
      const saved = await api.saveCase(this.data.caseDraft);
      const result = await api.publishCase(saved.id);
      await this.load();
      return result;
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
          repairs: [],
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
        repairs: [],
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
      const wrong = this.record.wrongQuestions.find((entry) => entry.id === wrongId);
      if (wrong) {
        wrong.repairs ||= [];
        wrong.repairs.push(item);
      }
      this.touch();
      return item;
    },
    async submitLesson() {
      if (!this.record || !this.task) throw new Error("没有找到当前学习任务。");
      if (!(await this.save())) throw new Error(this.saveError || "学习记录保存失败，请重试。");
      const result = await api.submitTask(this.task.id);
      this.record.completed = true;
      this.record.submittedAt = result.submittedAt;
      this.touch();
      return result;
    },
    async saveFeedback(text) {
      if (!text.trim()) throw new Error("请填写反馈内容。");
      if (!this.record) throw new Error("没有找到当前学生的学习记录。");
      const result = await api.saveFeedback(this.record.id, text);
      this.record.feedback = result.feedback;
      this.record.feedbackAt = result.feedbackAt;
      this.data.messages.unshift({
        id: createId("message"),
        taskId: this.task.id,
        title: `${this.task.title} · 教师反馈`,
        createdAt: this.record.feedbackAt,
      });
      this.touch();
    },
    async reset() {
      throw new Error("真实学习记录不能通过演示重置清除。");
    },
    createAccount(payload) { return api.createAccount(payload); },
    createClassroom(payload) { return api.createClassroom(payload); },
    addMember(classId, studentId) { return api.addMember(classId, studentId); },
    importLegacy(payload) { return api.importLegacy(payload); },
  },
});
