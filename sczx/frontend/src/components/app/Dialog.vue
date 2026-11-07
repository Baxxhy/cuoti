<script setup>
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog/index.js";
defineProps({ title: String, description: String, contentClass: String });
const open = defineModel("open", { default: false });
</script>
<template>
  <Dialog v-model:open="open"
    ><DialogContent :class="contentClass"
      ><DialogHeader
        ><DialogTitle>{{ title }}</DialogTitle
        ><DialogDescription class="sr-only">{{
          description || title
        }}</DialogDescription></DialogHeader
      ><slot /></DialogContent
  ></Dialog>
</template>
