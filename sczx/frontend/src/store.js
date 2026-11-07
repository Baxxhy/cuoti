import { defineStore } from "pinia";
import { initialBlocks } from "./data";

const storageKey = "shicheng-vue-prototype";
const legacyKey = "shicheng-nova-prototype-v2";
function initialState() {
  const state = {
    blocks: structuredClone(initialBlocks),
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
  };
  try {
    const current = localStorage.getItem(storageKey);
    const saved = JSON.parse(
      current || localStorage.getItem(legacyKey) || "{}",
    );
    const values = current ? saved : saved.state || saved;
    for (const key of Object.keys(state)) {
      if (Object.hasOwn(values, key)) state[key] = values[key];
    }
  } catch {
    // A fresh in-memory session remains usable if local storage cannot be read.
  }
  return state;
}
export const useLearning = defineStore("learning", {
  state: initialState,
  actions: {
    update(values) {
      this.$patch(values);
    },
    updateBlock(id, content) {
      const block = this.blocks.find((item) => item.id === id);
      if (block) block.content = content;
    },
    addAttempt(attempt) {
      this.attempts.push(attempt);
    },
    save() {
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify({ ...this.$state, originalImage: "" }),
        );
        return true;
      } catch {
        return false;
      }
    },
  },
});
