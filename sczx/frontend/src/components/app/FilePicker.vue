<script setup>
import { ref, onMounted, useAttrs, computed } from 'vue';
import { ElUpload, ElButton, ElIcon } from 'element-plus';
import { Upload } from '@/components/app/icons.js';
defineOptions({inheritAttrs:false});
const attrs=useAttrs(),emit=defineEmits(['change']),control=ref(),filename=ref('');
const drag=computed(()=>attrs.drag!==undefined&&attrs.drag!==false);
function changed(file){if(!file.raw)return;filename.value=file.name;emit('change',{target:{files:[file.raw],value:''}});control.value?.clearFiles()}
onMounted(()=>{const input=control.value?.$el.querySelector('input[type=file]');if(input&&attrs.id)input.id=attrs.id;if(input&&attrs['aria-label'])input.setAttribute('aria-label',attrs['aria-label'])});
</script>
<template><ElUpload ref="control" :class="['app-file-picker',attrs.class]" :style="attrs.style" :drag="drag" action="#" :auto-upload="false" :show-file-list="false" :accept="attrs.accept" :multiple="attrs.multiple!==undefined&&attrs.multiple!==false" :disabled="attrs.disabled" :on-change="changed"><template v-if="drag"><ElIcon class="el-icon--upload"><Upload/></ElIcon><div class="el-upload__text">{{filename||attrs.label||'拖拽文件或点击上传'}}</div></template><ElButton v-else native-type="button" :disabled="attrs.disabled"><Upload :size="16"/><span>{{filename||attrs.label||'选择文件'}}</span></ElButton></ElUpload></template>
