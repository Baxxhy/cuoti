<script setup>
import { computed, useAttrs } from 'vue';
import { ElButton } from 'element-plus';
defineOptions({inheritAttrs:false});
const props=defineProps({variant:{default:'default'},size:{default:'default'}}),attrs=useAttrs();
const kind=computed(()=>({default:'primary',selected:'primary',destructive:'danger'}[props.variant]||''));
</script>
<template><ElButton v-bind="attrs" :type="kind" :native-type="attrs.type||'submit'" :text="['ghost','link'].includes(variant)" :link="variant==='link'" :plain="['outline','selected'].includes(variant)" :size="size==='sm'||size==='icon-sm'?'small':size==='lg'?'large':'default'" :circle="size==='icon'||size==='icon-sm'" data-slot="button" :data-variant="variant" :data-size="size"><slot/></ElButton></template>
