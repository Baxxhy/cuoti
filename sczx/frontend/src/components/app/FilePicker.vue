<script setup>
import{ref,onMounted,useAttrs}from'vue';import{ElUpload,ElButton}from'element-plus';import{Upload}from'lucide-vue-next';defineOptions({inheritAttrs:false});const attrs=useAttrs(),emit=defineEmits(['change']),control=ref(),filename=ref('');function changed(file){if(!file.raw)return;filename.value=file.name;emit('change',{target:{files:[file.raw],value:''}});control.value?.clearFiles()}
onMounted(()=>{const input=control.value?.$el.querySelector('input[type=file]');if(input&&attrs.id)input.id=attrs.id});
</script>
<template><ElUpload ref="control" class="app-file-picker" action="#" :auto-upload="false" :show-file-list="false" :accept="attrs.accept" :multiple="attrs.multiple!==undefined&&attrs.multiple!==false" :disabled="attrs.disabled" :on-change="changed"><ElButton native-type="button" :disabled="attrs.disabled"><Upload :size="16"/><span>{{filename||'选择文件'}}</span></ElButton></ElUpload></template>
