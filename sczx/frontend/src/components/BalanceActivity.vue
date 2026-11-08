<script setup>
import {computed} from 'vue';
import {Plus,RotateCcw,Check} from 'lucide-vue-next';
const props=defineProps({config:{type:Object,default:()=>({base:5,step:1,max:10})},modelValue:{type:Number,default:0}});
const emit=defineEmits(['update:modelValue']);
const value=computed(()=>props.config.base+props.modelValue*props.config.step);
</script>
<template><div class="interactive-balance"><div class="balance-math"><span>{{ value }}</span><span>=</span><span>{{ value }}</span></div><div class="balance-scene"><div class="balance-pillar"/><div class="balance-arm"><div v-for="side in ['left','right']" :key="side" :class="['balance-dish',side]"><div class="balance-block">{{ config.base }}<span v-if="modelValue">+ {{ modelValue*config.step }}</span></div></div></div></div><div class="balance-toolbar"><Status tone="green"><Check :size="12"/>两边仍然相等</Status><Button size="sm" variant="outline" :disabled="modelValue>=config.max" @click="emit('update:modelValue',modelValue+1)"><Plus/>两边同时加 {{ config.step }}</Button><Button variant="ghost" size="icon-sm" aria-label="重置天平" @click="emit('update:modelValue',0)"><RotateCcw/></Button></div></div></template>
