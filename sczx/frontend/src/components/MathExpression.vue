<script setup>
import {computed} from 'vue';
const props=defineProps({text:{type:String,default:''},inline:Boolean});
const sides=computed(()=>props.text.trim().split('='));
const tokens=value=>value.split(/([a-zA-Z])/).filter(Boolean);
</script>
<template><span :class="['reading-equation',{'is-inline':inline}]" role="math" :aria-label="text.trim()"><template v-for="(side,index) in sides" :key="index"><span v-if="index" class="reading-equals" aria-hidden="true">=</span><span class="reading-equation-side" aria-hidden="true"><span v-for="(token,n) in tokens(side)" :key="n" :class="{'reading-variable':/^[a-zA-Z]$/.test(token)}">{{token}}</span></span></template></span></template>
