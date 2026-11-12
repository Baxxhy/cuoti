<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';
import { ElButton, ElSlider, ElSpace, ElText, ElAlert } from 'element-plus';
import { Play, Pause, Volume2 } from '@/components/app/icons.js';
const props=defineProps({src:{type:String,required:true}}),media=ref(),playing=ref(false),duration=ref(0),position=ref(0),volume=ref(1),error=ref('');
const time=value=>{const seconds=Math.floor(Number.isFinite(value)?value:0);return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')};
async function toggle(){if(!media.value)return;error.value='';if(!media.value.paused){media.value.pause();return}try{if(media.value.error)media.value.load();await media.value.play()}catch{error.value='音频暂时无法播放，请重试。'}}
function seek(value){if(media.value&&Number.isFinite(duration.value)&&duration.value>0)media.value.currentTime=value}
function metadata(){duration.value=Number.isFinite(media.value?.duration)?media.value.duration:0}
function stop(){media.value?.pause();playing.value=false;position.value=0;duration.value=0;error.value=''}
watch(()=>props.src,stop);watch(volume,value=>{if(media.value)media.value.volume=value});onBeforeUnmount(stop);
</script>
<template><section class="element-audio"><audio ref="media" :src="src" preload="metadata" hidden @loadedmetadata="metadata" @timeupdate="position=media.currentTime" @play="playing=true" @pause="playing=false" @ended="playing=false" @error="error='音频加载失败，请检查文件后重试。'"/><ElSpace wrap><ElButton native-type="button" :aria-label="playing?'暂停音频':'播放音频'" @click="toggle"><Pause v-if="playing"/><Play v-else/></ElButton><ElText>{{time(position)}} / {{time(duration)}}</ElText><Volume2/><ElSlider v-model="volume" :min="0" :max="1" :step="0.1" :show-tooltip="false" aria-label="音量" class="audio-volume"/></ElSpace><ElSlider :model-value="position" :max="duration||1" :disabled="!duration" :show-tooltip="false" aria-label="音频进度" @change="seek"/><ElAlert v-if="error" type="error" :closable="false" show-icon :title="error"/></section></template>
