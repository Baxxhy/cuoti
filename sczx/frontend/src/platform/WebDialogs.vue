<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {modalState,actionSheetState,closeModal,closeActionSheet} from './browser.js'
const content=ref('')
watch(modalState,value=>{content.value=value?.content||''},{immediate:true})
function keydown(event){
 if(event.key==='Escape'){
  if(actionSheetState.value)closeActionSheet()
  else if(modalState.value)closeModal(false)
 }else if(event.key==='Enter'&&modalState.value&&!modalState.value.editable)closeModal(true)
}
onMounted(()=>window.addEventListener('keydown',keydown))
onBeforeUnmount(()=>window.removeEventListener('keydown',keydown))
</script>
<template>
 <div v-if="modalState" class="web-popup web-modal-host" @touchmove.prevent>
  <div class="web-popup-mask" />
  <div class="uni-modal" role="dialog" aria-modal="true" :aria-label="modalState.title">
   <div v-if="modalState.title" class="uni-modal__hd"><strong class="uni-modal__title">{{modalState.title}}</strong></div>
   <textarea v-if="modalState.editable" v-model="content" class="uni-modal__textarea" rows="1" :placeholder="modalState.placeholderText" />
   <div v-else class="uni-modal__bd">{{modalState.content}}</div>
   <div class="uni-modal__ft">
    <div v-if="modalState.showCancel" class="uni-modal__btn uni-modal__btn_default" role="button" tabindex="0" :style="{color:modalState.cancelColor}" @click="closeModal(false)" @keydown.space.prevent="closeModal(false)">{{modalState.cancelText}}</div>
    <div class="uni-modal__btn uni-modal__btn_primary" role="button" tabindex="0" :style="{color:modalState.confirmColor}" @click="closeModal(true,content)" @keydown.space.prevent="closeModal(true,content)">{{modalState.confirmText}}</div>
   </div>
  </div>
 </div>
 <div v-if="actionSheetState" class="web-popup web-sheet-host" @touchmove.prevent>
  <div class="web-popup-mask uni-actionsheet__mask" @click="closeActionSheet()" />
  <div class="uni-actionsheet uni-actionsheet_toggle" role="dialog" aria-modal="true" aria-label="操作菜单">
   <div class="uni-actionsheet__menu">
    <div v-if="actionSheetState.title" class="web-sheet-title">{{actionSheetState.title}}</div>
    <div class="web-sheet-items" @touchmove.stop>
     <div v-for="(item,index) in actionSheetState.itemList" :key="index" class="uni-actionsheet__cell" role="button" tabindex="0" :style="{color:actionSheetState.itemColor}" @click="closeActionSheet(index)" @keydown.enter.prevent.stop="closeActionSheet(index)" @keydown.space.prevent="closeActionSheet(index)">{{item}}</div>
    </div>
   </div>
   <div class="uni-actionsheet__action"><div class="uni-actionsheet__cell" role="button" tabindex="0" :style="{color:actionSheetState.itemColor}" @click="closeActionSheet()" @keydown.enter.prevent="closeActionSheet()">取消</div></div>
  </div>
 </div>
</template>
<style lang="scss">
@import '../styles/platform-dialogs.scss';
</style>
