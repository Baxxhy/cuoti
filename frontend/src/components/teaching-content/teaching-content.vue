<template>
  <view class="teaching-content">
    <template v-for="(block, index) in blocks" :key="index">
      <view v-if="allowed.includes(block.kind)" :class="['content-block', block.kind]">
        <button
          v-if="foldable(block)"
          class="expand-action"
          role="button"
          tabindex="0"
          :aria-expanded="expanded.includes(index)"
          @click="toggle(index)"
          @keydown.enter.prevent="toggle(index)"
        >
          {{ expanded.includes(index) ? '收起这段说明' : '展开这段说明' }}
        </button>
        <question-content
          v-if="block.kind === 'question'"
          :text="block.text"
          :images="block.images || []"
        />
        <math-text v-else-if="!foldable(block) || expanded.includes(index)" :text="block.text" />
        <view v-if="block.kind === 'question'" class="question-options">
          <checkbox-group
            v-if="selectable && isMultipleChoice(block.question_type) && block.options?.length"
            @change="$emit('choose', choiceAnswer($event.detail.value, block.options))"
          >
            <text class="choice-instruction">多选题</text>
            <label
              v-for="option in normalizeOptions(block.options)"
              :key="option.label"
              class="question-option selectable-option"
            >
              <checkbox
                :value="option.label"
                :checked="answer.split('、').includes(option.label)"
                :disabled="disabled"
                color="var(--color-primary)"
              />
              <text class="option-label">{{ option.label }}</text>
              <math-text :text="option.text" inline />
            </label>
          </checkbox-group>
          <radio-group
            v-else-if="selectable && block.options?.length"
            @change="$emit('choose', $event.detail.value)"
          >
            <label
              v-for="option in normalizeOptions(block.options)"
              :key="option.label"
              class="question-option selectable-option"
            >
              <radio
                :value="option.label"
                :checked="answer === option.label"
                :disabled="disabled"
                color="var(--color-primary)"
              />
              <text class="option-label">{{ option.label }}</text>
              <math-text :text="option.text" inline />
            </label>
          </radio-group>
          <template v-else>
            <view
              v-for="option in normalizeOptions(block.options)"
              :key="option.label"
              class="question-option"
            >
              <text class="option-label">{{ option.label }}</text>
              <math-text :text="option.text" inline />
            </view>
          </template>
        </view>
      </view>
    </template>
  </view>
</template>
<script setup>
import { ref, watch } from 'vue'
import { normalizeOptions, isMultipleChoice, choiceAnswer } from '@/utils/question.js'
import MathText from '@/components/math-text/math-text.vue'
import QuestionContent from '@/components/question-content/question-content.vue'
const props = defineProps({
  blocks: { type: Array, default: () => [] },
  selectable: Boolean,
  disabled: Boolean,
  answer: { type: String, default: '' },
})
defineEmits(['choose'])
const allowed = ['text', 'formula', 'question']
const expanded = ref([])
const foldable = (block) => block.kind !== 'question' && String(block.text || '').length > 160
function toggle(index) {
  expanded.value = expanded.value.includes(index)
    ? expanded.value.filter((i) => i !== index)
    : [...expanded.value, index]
}
watch(
  () => props.blocks,
  () => {
    expanded.value = []
  },
)
</script>
<style scoped lang="scss">
.question-options {
  margin-top: 12px;
}
.selectable-option {
  min-height: 48px;
  align-items: center;
  padding: 8px 0;
}
.choice-instruction {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.question-option {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 6px 0;
}
.option-label {
  flex: 0 0 20px;
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
}

.content-block {
  margin: 12px 0;
  font-size: 16px;
}
.content-block.question {
  font-size: 17px;
}
.content-block.formula {
  padding: 14px 12px;
  background: var(--color-primary-soft);
  border-radius: 12px;
  font-size: 18px;
}
.expand-action {
  width: 100%;
  min-height: 48px;
  padding: 12px 0;
  margin: 0;
  text-align: left;
  background: transparent;
  font-size: 14px;
  color: var(--color-primary);
}
</style>
