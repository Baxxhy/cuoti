<script setup>
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select/index.js";
defineOptions({ inheritAttrs: false });
defineProps({ options: { default: () => [] }, label: String });
const model = defineModel();
</script>
<template>
  <Select v-model="model"
    ><SelectTrigger :aria-label="label" v-bind="$attrs"
      ><SelectValue /></SelectTrigger
    ><SelectContent
      ><SelectItem
        v-for="option in options"
        :key="option.value"
        :value="option.value"
        >{{ option.label }}</SelectItem
      ></SelectContent
    ></Select
  >
</template>
