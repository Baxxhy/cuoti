<template>
  <view class="date-time-input">
    <picker mode="date" :value="dateValue" @change="changeDate($event.detail.value)">
      <view class="date-time-field">{{ dateValue || '选择日期' }}</view>
    </picker>
    <picker mode="time" :value="timeValue" @change="changeTime($event.detail.value)">
      <view class="date-time-field">{{ timeValue || '选择时间' }}</view>
    </picker>
    <button v-if="clearable && modelValue" @click="emit('update:modelValue', '')">清除</button>
  </view>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: { type: String, default: '' }, clearable: Boolean })
const emit = defineEmits(['update:modelValue'])
const selected = computed(() => (props.modelValue ? new Date(props.modelValue) : null))
const pad = (value) => String(value).padStart(2, '0')
function dateText(value) {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
}
const dateValue = computed(() =>
  selected.value && Number.isFinite(selected.value.getTime()) ? dateText(selected.value) : '',
)
const timeValue = computed(() =>
  dateValue.value ? `${pad(selected.value.getHours())}:${pad(selected.value.getMinutes())}` : '',
)
function update(date, time) {
  // Local picker values become an explicit UTC instant for storage and transport.
  const instant = new Date(`${date}T${time}:00`)
  if (Number.isFinite(instant.getTime())) emit('update:modelValue', instant.toISOString())
}
function changeDate(date) {
  update(date, timeValue.value || '18:00')
}
function changeTime(time) {
  update(dateValue.value || dateText(new Date()), time)
}
</script>
<style scoped>
.date-time-input {
  display: flex;
  align-items: center;
  gap: 10px;
}
.date-time-input picker {
  flex: 1;
  min-width: 0;
}
.date-time-field {
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-text-primary);
  background: #fff;
  font-size: 14px;
}
.date-time-input button {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
