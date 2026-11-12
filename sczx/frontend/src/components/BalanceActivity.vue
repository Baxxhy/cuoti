<script setup>
import { computed, ref } from "vue";
import { Plus, Minus, RotateCcw } from "@/components/app/icons.js";
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
  <AppAlert type="error" v-if="!spec" role="alert">不支持的互动参数，请联系教师。</AppAlert>
  <Surface data-ui="card" v-else class="interactive-balance">
    <div class="balance-math" aria-live="polite">
      <span>{{ current.left }}</span
      ><span>{{ balanced ? "=" : "≠" }}</span
      ><span>{{ current.right }}</span>
    </div>
    <div class="balance-scene">
      <Surface data-ui="card" class="balance-pillar" :body-style="{padding:0}" />
      <Surface data-ui="card"
        class="balance-arm" :body-style="{padding:0,height:'100%'}"
        :style="{
          transform: `rotate(${balanced ? 0 : current.left > current.right ? -6 : 6}deg)`,
        }"
      >
        <div
          v-for="side in ['left', 'right']"
          :key="side"
          :class="['balance-dish', side]"
        >
          <Surface data-ui="card" class="balance-block" :body-style="{padding:0,height:'100%',display:'grid',placeItems:'center'}">{{ current[side] }}</Surface>
        </div>
      </Surface>
    </div>
    <div class="balance-side-controls"><div v-for="side in ['left','right']" :key="side"><span>{{side==='left'?'左边':'右边'}}</span><AppButton v-if="spec.actions.includes(side+'_subtract')" variant="outline" size="icon-sm" :aria-label="(side==='left'?'左边':'右边')+'减'+spec.step" :disabled="disabled(side+'_subtract')" @click="act(side+'_subtract')"><Minus :size="15"/></AppButton><AppButton v-if="spec.actions.includes(side+'_add')" variant="outline" size="icon-sm" :aria-label="(side==='left'?'左边':'右边')+'加'+spec.step" :disabled="disabled(side+'_add')" @click="act(side+'_add')"><Plus :size="15"/></AppButton></div></div>
    <ElSpace wrap :size="12" class="balance-common-controls"><span>两边一起</span><AppButton v-if="spec.actions.includes('both_add')" size="sm" :disabled="disabled('both_add')" :aria-label="'两边同时加'+spec.step" @click="act('both_add')"><Plus :size="15"/>{{spec.step}}</AppButton><AppButton v-if="spec.actions.includes('both_subtract')" variant="outline" size="sm" :disabled="disabled('both_subtract')" :aria-label="'两边同时减'+spec.step" @click="act('both_subtract')"><Minus :size="15"/>{{spec.step}}</AppButton><AppButton v-if="spec.actions.includes('reset')" variant="ghost" size="icon-sm" aria-label="重置天平" title="重置天平" @click="act('reset')"><RotateCcw :size="15"/></AppButton></ElSpace><p class="sr-only" role="status">{{balanced?'两边相等':'两边不相等'}}</p>
    <AppAlert type="error" v-if="failure" role="alert">{{ failure }}</AppAlert>
  </Surface>
</template>
