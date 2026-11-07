import { create } from "zustand";
import { persist } from "zustand/middleware";

export type LessonBlock = { id: string; title: string; content: string };
export type Attempt = {
  question: number;
  answer: string;
  reason: string;
  helped: boolean;
  correct: boolean;
};
export const initialBlocks: LessonBlock[] = [
  {
    id: "observe",
    title: "从天平开始观察",
    content:
      "展示保持平衡的天平。请学生预测：如果两边同时增加相同数量的砝码，天平会怎样变化？先说出理由，再实际操作。",
  },
  {
    id: "express",
    title: "把观察写成等式",
    content:
      "把两边同时增加的过程写下来。引导学生用“同时”和“相同”解释等式性质，比较只改变一边的情况。",
  },
  {
    id: "practice",
    title: "在新题中独立应用",
    content:
      "给出 x − 3 = 5，请学生解释两边的运算。需要帮助时提供提示，再用 y + 4 = 11 检查能否独立完成。",
  },
];
interface LearningStore {
  blocks: LessonBlock[];
  lessonGoal: string;
  studentBase: string;
  dueDate: string;
  published: boolean;
  casePublished: boolean;
  observation: string;
  attempts: Attempt[];
  question: number;
  helped: boolean;
  completed: boolean;
  favorite: boolean;
  repaired: boolean;
  feedback: string;
  wrongQuestion: string;
  originalImage: string;
  updateBlock: (id: string, content: string) => void;
  reorder: (from: number, to: number) => void;
  update: (
    values: Partial<
      Omit<LearningStore, "update" | "updateBlock" | "reorder" | "addAttempt">
    >,
  ) => void;
  addAttempt: (attempt: Attempt) => void;
}
export const useLearning = create<LearningStore>()(
  persist(
    (set) => ({
      blocks: initialBlocks,
      lessonGoal: "理解并应用等式两边的共同变化",
      studentBase: "已理解相等关系，容易机械记忆移项变号",
      dueDate: "2026-11-14",
      published: false,
      casePublished: false,
      observation: "",
      attempts: [],
      question: 0,
      helped: false,
      completed: false,
      favorite: false,
      repaired: false,
      feedback:
        "你已经能解释两边共同变化的原因。接下来，试着在新题中独立写出每一步。",
      wrongQuestion: "x + 3 = 8，求 x 的值。",
      originalImage: "",
      updateBlock: (id, content) =>
        set((state) => ({
          blocks: state.blocks.map((block) =>
            block.id === id ? { ...block, content } : block,
          ),
        })),
      reorder: (from, to) =>
        set((state) => {
          const blocks = [...state.blocks];
          const [block] = blocks.splice(from, 1);
          blocks.splice(to, 0, block);
          return { blocks };
        }),
      update: (values) => set(values),
      addAttempt: (attempt) =>
        set((state) => ({ attempts: [...state.attempts, attempt] })),
    }),
    {
      name: "shicheng-nova-prototype-v2",
      partialize: (state) => ({ ...state, originalImage: "" }),
    },
  ),
);

export const questions = [
  {
    equation: "x − 3 = 5",
    prompt: "等式两边同时加上 3，x 等于多少？",
    answer: "8",
    hint: "左边的 −3 与 +3 抵消。右边也要加上 3。",
  },
  {
    equation: "y + 4 = 11",
    prompt: "等式两边同时减去 4，y 等于多少？",
    answer: "7",
    hint: "在左右两边同时减去 4，右边变为 11 − 4。",
  },
];
export const demoStudents = [
  {
    name: "林同学",
    initials: "林",
    status: "已提交",
    help: "提示 1 次",
    result: "新题独立完成",
    progress: 100,
  },
  {
    name: "陈同学",
    initials: "陈",
    status: "学习中",
    help: "换讲法 1 次",
    result: "待独立检查",
    progress: 60,
  },
  {
    name: "周同学",
    initials: "周",
    status: "未开始",
    help: "尚未使用",
    result: "待学习",
    progress: 0,
  },
];
