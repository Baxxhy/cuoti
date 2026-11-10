<script setup>
import { computed, ref, watch } from "vue";
import { Plus, Minus, RotateCcw, Scale } from "lucide-vue-next";
import { balanceSpec, applyBalance } from "@/lib/visualization.js";
const props = defineProps({
    config: {
      type: Object,
      default: () => ({ type: "balance", base: 5, step: 1, max: 10 }),
    },
    modelValue: { type: Number, default: 0 },
    state: { type: Object, default: null },
  }),
  emit = defineEmits(["update:modelValue", "change"]);
const failure = ref("");
const spec = computed(() => {
  try {
    return balanceSpec(props.config);
  } catch (e) {
    return null;
  }
});
const current = computed(
  () =>
    props.state?.state || {
      left:
        (spec.value?.initial.left || 0) +
        props.modelValue * (spec.value?.step || 1),
      right:
        (spec.value?.initial.right || 0) +
        props.modelValue * (spec.value?.step || 1),
    },
);
const balanced = computed(() => current.value.left === current.value.right);
const labels = {
  left_add: "左侧加",
  right_add: "右侧加",
  both_add: "两边同时加",
  left_subtract: "左侧减",
  right_subtract: "右侧减",
  both_subtract: "两边同时减",
  reset: "重置天平",
};
function disabled(a) {
  if (!spec.value) return true;
  try {
    applyBalance(spec.value, current.value, a);
    return a !== "reset" && (props.state?.actions.length || 0) >= 200;
  } catch {
    return true;
  }
}
function act(action) {
  failure.value = "";
  try {
    const value = applyBalance(spec.value, current.value, action),
      history =
        action === "reset"
          ? []
          : [
              ...(props.state?.actions ||
                Array.from(
                  {
                    length: Math.max(
                      0,
                      Math.min(100, Math.floor(props.modelValue)),
                    ),
                  },
                  () => "both_add",
                )),
              action,
            ];
    emit("change", { state: value, actions: history });
    emit(
      "update:modelValue",
      value.left === value.right && history.length ? history.length : 0,
    );
  } catch (e) {
    failure.value = e.message;
  }
}
</script>
<template>
  <p v-if="!spec" role="alert">不支持的互动参数，请联系教师。</p>
  <div v-else class="interactive-balance">
    <div class="balance-math" aria-live="polite">
      <span>{{ current.left }}</span
      ><span>{{ balanced ? "=" : "≠" }}</span
      ><span>{{ current.right }}</span>
    </div>
    <div class="balance-scene">
      <div class="balance-pillar" />
      <div
        class="balance-arm"
        :style="{
          transform: `rotate(${balanced ? 0 : current.left > current.right ? -6 : 6}deg)`,
        }"
      >
        <div
          v-for="side in ['left', 'right']"
          :key="side"
          :class="['balance-dish', side]"
        >
          <div class="balance-block">{{ current[side] }}</div>
        </div>
      </div>
    </div>
    <div class="balance-toolbar">
      <Status :tone="balanced ? 'green' : 'amber'"
        ><Scale :size="14" />{{ balanced ? "两边相等" : "两边不相等" }}</Status
      ><Button
        v-for="action in spec.actions"
        :key="action"
        size="sm"
        :variant="action.startsWith('both') ? 'outline' : 'ghost'"
        :disabled="disabled(action)"
        @click="act(action)"
        ><RotateCcw v-if="action === 'reset'" /><Minus
          v-else-if="action.endsWith('subtract')"
        /><Plus v-else />{{ labels[action]
        }}{{ action === "reset" ? "" : " " + spec.step }}</Button
      >
    </div>
    <p v-if="failure" role="alert">{{ failure }}</p>
  </div>
</template>
