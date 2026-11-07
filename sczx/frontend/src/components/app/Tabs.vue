<script setup>
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs/index.js";
defineProps({ items: { default: () => [] } });
const model = defineModel();
</script>
<template>
  <Tabs v-model="model"
    ><TabsList
      ><TabsTrigger
        v-for="item in items"
        :key="item.value"
        :value="item.value"
        >{{ item.label }}</TabsTrigger
      ></TabsList
    ></Tabs
  >
</template>
