import { initialBlocks } from "../data.js";

const clone = (value) => JSON.parse(JSON.stringify(value));
const now = () => new Date().toISOString();

export const createId = (prefix) => `${prefix}-${crypto.randomUUID().replaceAll("-", "")}`;

// Unauthenticated shell state only. Logged-in platform data always comes from the API.
export function createPlatform() {
  return {
    version: 2,
    classroom: null,
    classrooms: [],
    members: [],
    lesson: null,
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
      studentBase: "",
      dueDate: "",
      blocks: clone(initialBlocks),
      questions: [],
      updatedAt: now(),
    },
    tasks: [],
    records: {},
    studentRecords: {},
    activeTaskId: null,
    activeStudentId: null,
    favoriteCaseIds: [],
    issue: { id: "issue-empty", text: "", reply: "", resolved: false },
    supplements: [],
    messages: [],
  };
}
