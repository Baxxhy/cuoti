import { initialBlocks, questions } from "../data.js";

export const storageKey = "shicheng-platform-v1";
const clone = (value) => JSON.parse(JSON.stringify(value));
const now = () => new Date().toISOString();
export const createId = (prefix) => `${prefix}-${crypto.randomUUID()}`;
export function createRecord(taskId) {
  return {
    id: createId("record"),
    taskId,
    studentId: "student-lin",
    observation: "",
    drafts: {},
    attempts: [],
    helps: [],
    repairs: [],
    wrongQuestions: [],
    completed: false,
    submittedAt: null,
    feedback: "",
    feedbackAt: null,
    updatedAt: now(),
  };
}
export function createPlatform() {
  return {
    version: 1,
    classroom: { id: "class-7a", name: "七年级一班", studentId: "student-lin" },
    lesson: {
      id: "lesson-equation",
      title: "等式性质",
      courseId: "course-equation",
    },
    caseDraft: {
      id: "case-balance",
      title: "天平与等式性质",
      source: "",
      content: initialBlocks.map((block) => block.content).join("\n\n"),
      reviewed: false,
      fileName: "",
      updatedAt: now(),
    },
    publishedCase: null,
    lessonDraft: {
      id: "draft-equation",
      caseId: "case-balance",
      goal: "理解并应用等式两边的共同变化",
      studentBase: "已理解相等关系，容易机械记忆移项变号",
      dueDate: "2026-11-14",
      blocks: clone(initialBlocks),
      updatedAt: now(),
    },
    tasks: [],
    records: {},
    activeTaskId: null,
    favorite: false,
    issue: {
      id: "issue-observation",
      text: "为什么只改变一边，等式就不成立了？",
      reply: "",
      resolved: false,
      updatedAt: now(),
    },
    runtime: { id: "job-lesson", status: "failed", updatedAt: now() },
    supplements: [],
    messages: [],
  };
}
function validDraft(draft) {
  return (
    draft &&
    typeof draft.goal === "string" &&
    Array.isArray(draft.blocks) &&
    draft.blocks.every(
      (block) =>
        block &&
        typeof block.id === "string" &&
        typeof block.title === "string" &&
        typeof block.content === "string",
    )
  );
}
function validate(data) {
  if (
    !data ||
    data.version !== 1 ||
    !validDraft(data.lessonDraft) ||
    !Array.isArray(data.tasks) ||
    !data.records ||
    !Array.isArray(data.messages)
  )
    throw new Error("保存的数据格式无法读取，请导出记录后重置演示。");
  for (const key of ["classroom", "lesson", "caseDraft", "issue", "runtime"]) {
    if (!data[key] || typeof data[key] !== "object")
      throw new Error("本地记录缺少必要字段，请导出后重置演示。");
  }
  if (
    !Array.isArray(data.supplements) ||
    typeof data.caseDraft.content !== "string" ||
    typeof data.caseDraft.title !== "string" ||
    typeof data.issue.text !== "string"
  )
    throw new Error("本地记录字段格式不正确，请导出后重置演示。");
  for (const task of data.tasks) {
    task.questions ||= clone(questions);
    if (
      !Array.isArray(task.questions) ||
      task.questions.length !== questions.length ||
      task.questions.some(
        (item) =>
          !item ||
          typeof item.equation !== "string" ||
          typeof item.answer !== "string" ||
          typeof item.hint !== "string",
      )
    )
      throw new Error("检查题数据不完整，请导出后重置演示。");
    const record = data.records[task.id];
    if (
      !task.id ||
      !validDraft(task.snapshot) ||
      !record ||
      !Array.isArray(record.attempts) ||
      !Array.isArray(record.helps) ||
      !Array.isArray(record.repairs) ||
      !Array.isArray(record.wrongQuestions) ||
      !record.drafts ||
      typeof record.observation !== "string" ||
      typeof record.feedback !== "string"
    )
      throw new Error("任务记录不完整，请导出记录后重置演示。");
  }
  return data;
}
function migrateLegacy() {
  const raw =
    localStorage.getItem("shicheng-vue-prototype") ||
    localStorage.getItem("shicheng-nova-prototype-v2");
  const data = createPlatform();
  try {
    const draft = JSON.parse(
      sessionStorage.getItem("shicheng-case-draft") || "null",
    );
    if (
      draft &&
      typeof draft.title === "string" &&
      typeof draft.content === "string"
    )
      Object.assign(data.caseDraft, draft);
  } catch {
    /* Old malformed session drafts do not replace the usable default case. */
  }
  if (!raw) return data;
  const parsed = JSON.parse(raw);
  const old = parsed.state || parsed;
  if (!old || typeof old !== "object")
    throw new Error("旧记录无法读取，请导出记录后重置演示。");
  if (
    Array.isArray(old.blocks) &&
    old.blocks.every(
      (block) =>
        typeof block?.content === "string" &&
        typeof block?.id === "string" &&
        typeof block?.title === "string",
    )
  )
    data.lessonDraft.blocks = clone(old.blocks);
  for (const [oldKey, key] of [
    ["lessonGoal", "goal"],
    ["studentBase", "studentBase"],
    ["dueDate", "dueDate"],
  ])
    if (typeof old[oldKey] === "string") data.lessonDraft[key] = old[oldKey];
  data.favorite = old.favorite === true;
  if (old.casePublished)
    data.publishedCase = { ...clone(data.caseDraft), publishedAt: now() };
  const task = {
    id: "task-legacy",
    lessonId: data.lesson.id,
    classId: data.classroom.id,
    title: "等式性质 · 历史记录",
    snapshot: clone(data.lessonDraft),
    publishedAt: now(),
    dueDate: data.lessonDraft.dueDate,
    source: "legacy",
    questions: clone(questions),
  };
  if (
    old.published ||
    old.completed ||
    old.observation ||
    old.feedback ||
    old.wrongQuestion ||
    old.attempts?.length
  ) {
    const record = createRecord(task.id);
    record.observation =
      typeof old.observation === "string" ? old.observation : "";
    record.feedback = typeof old.feedback === "string" ? old.feedback : "";
    record.completed = old.completed === true;
    record.attempts = (Array.isArray(old.attempts) ? old.attempts : [])
      .filter((item) => item && typeof item.answer === "string")
      .map((item) => ({
        ...item,
        id: createId("attempt"),
        taskId: task.id,
        createdAt: now(),
      }));
    if (typeof old.wrongQuestion === "string")
      record.wrongQuestions.push({
        id: createId("wrong"),
        taskId: task.id,
        prompt: old.wrongQuestion,
        image: typeof old.originalImage === "string" ? old.originalImage : "",
        answer: "x = 8 + 3",
        createdAt: now(),
      });
    if (old.repaired)
      record.repairs.push({
        id: createId("repair"),
        taskId: task.id,
        answer: "7",
        wrongId: record.wrongQuestions[0]?.id || null,
        reason: "",
        correct: true,
        createdAt: now(),
      });
    data.tasks.push(task);
    data.records[task.id] = record;
    data.activeTaskId = task.id;
  }
  return data;
}
let failNext = null;
export function simulateNextFailure(operation = "publish") {
  failNext = operation;
}
async function request(operation, name) {
  await new Promise((resolve) => window.setTimeout(resolve, 100));
  if (failNext === name) {
    failNext = null;
    throw new Error("演示请求失败，请重试。");
  }
  return operation();
}
export const platformService = {
  load: () =>
    request(() => {
      try {
        const raw = localStorage.getItem(storageKey);
        return raw ? validate(JSON.parse(raw)) : migrateLegacy();
      } catch (error) {
        throw new Error(
          error instanceof SyntaxError
            ? "本地记录损坏，请导出记录后重置演示。"
            : error.message,
        );
      }
    }, "load"),
  save: (data) =>
    request(() => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(validate(clone(data))));
      } catch (error) {
        throw new Error(
          error.name === "QuotaExceededError"
            ? "浏览器存储空间不足，当前修改尚未保存。请导出记录后清理空间并重试。"
            : error.message,
        );
      }
      return clone(data);
    }, "save"),
  reset: () =>
    request(() => {
      const data = createPlatform();
      localStorage.setItem(storageKey, JSON.stringify(data));
      return data;
    }, "reset"),
  publishLesson(data) {
    return request(() => {
      if (
        !data.lessonDraft.goal.trim() ||
        data.lessonDraft.blocks.some((block) => !block.content.trim())
      )
        throw new Error("请填写学习目标和全部教学活动。");
      if (!data.lessonDraft.dueDate) throw new Error("请选择完成日期。");
      const next = clone(data);
      const task = {
        id: createId("task"),
        lessonId: next.lesson.id,
        classId: next.classroom.id,
        title: next.lesson.title,
        snapshot: clone(next.lessonDraft),
        publishedAt: now(),
        dueDate: next.lessonDraft.dueDate,
        source: "published",
        questions: clone(questions),
      };
      next.tasks.unshift(task);
      next.records[task.id] = createRecord(task.id);
      next.activeTaskId = task.id;
      localStorage.setItem(storageKey, JSON.stringify(next));
      return next;
    }, "publish");
  },
};
