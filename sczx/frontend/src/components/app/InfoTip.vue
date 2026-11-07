<script setup>
import { useId } from "vue";
import { Info } from "lucide-vue-next";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip/index.js";
defineProps({ label: String });
const descriptionId = useId();
</script>
<template>
  <Tooltip
    ><TooltipTrigger as-child
      ><Button
        variant="ghost"
        size="icon-sm"
        class="info-tip"
        :aria-label="label"
        :aria-describedby="descriptionId"
        ><Info :size="15" /></Button></TooltipTrigger
    ><TooltipContent
      :id="descriptionId"
      role="tooltip"
      class="max-w-72 text-xs leading-relaxed"
      ><slot /></TooltipContent
  ></Tooltip>
</template>
