<template>
  <view class="field account-field">
    <!-- H5 uses native elements so labels and password managers reach the actual input. -->
    <!-- #ifdef H5 -->
    <component :is="'label'" class="field-label" :for="id">{{ label }}</component>
    <component
      :is="'input'"
      :id="id"
      class="field-input account-input"
      :name="id"
      :value="modelValue"
      :type="type"
      :inputmode="inputmode"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :aria-describedby="descriptionIds || undefined"
      :disabled="disabled"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown.enter.prevent="$emit('confirm')"
    />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <label class="field-label" :for="id">{{ label }}</label>
    <input
      :id="id"
      class="field-input account-input"
      :value="modelValue"
      :type="type"
      :password="type === 'password'"
      :inputmode="inputmode"
      :placeholder="placeholder"
      :maxlength="maxlength"
      :aria-label="label"
      :disabled="disabled"
      confirm-type="done"
      @input="$emit('update:modelValue', $event.detail.value)"
      @confirm="$emit('confirm')"
    />
    <!-- #endif -->
    <text v-if="hint" :id="`${id}-hint`" class="account-hint">{{ hint }}</text>
  </view>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  type: { type: String, default: 'text' },
  inputmode: { type: String, default: 'text' },
  autocomplete: { type: String, default: 'off' },
  placeholder: String,
  hint: String,
  describedBy: String,
  maxlength: { type: Number, default: 256 },
  disabled: Boolean,
})
defineEmits(['update:modelValue', 'confirm'])
const descriptionIds = computed(() =>
  [props.hint ? `${props.id}-hint` : '', props.describedBy].filter(Boolean).join(' '),
)
</script>

<style scoped>
.account-input {
  box-sizing: border-box;
  display: block;
  height: calc(1.5em + 26px);
  min-height: 50px;
  font-size: 16px;
  line-height: 1.5;
}
.account-hint {
  display: block;
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
</style>
