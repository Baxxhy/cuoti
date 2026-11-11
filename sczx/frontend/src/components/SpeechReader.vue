<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { Volume2, Pause, Play, Square } from 'lucide-vue-next';
const props = defineProps({ contextKey: [String, Number], text: { type: String, default: '' } });
const synth = window.speechSynthesis;
const available = !!(synth && window.SpeechSynthesisUtterance);
const state = ref('idle'), error = ref('');
let generation = 0, utterance, timer;
// 浏览器有一个全局朗读队列，切换朗读对象时停止前一个组件。
const ownerKey = Symbol.for('sczx.speechReader');
function stop() {
  generation++; clearTimeout(timer);
  if (window[ownerKey] === stop) { window[ownerKey] = null; synth?.cancel(); }
  utterance = null; state.value = 'idle';
}
async function read() {
  if (!available || !props.text.trim()) return;
  window[ownerKey]?.(); stop(); window[ownerKey] = stop;
  error.value = ''; state.value = 'starting';
  const version = generation;
  let voices = synth.getVoices();
  for (let i = 0; !voices.length && i < 10; i++) {
    await new Promise(resolve => setTimeout(resolve, 150));
    if (version !== generation) return;
    voices = synth.getVoices();
  }
  const chinese = /[\u3400-\u9fff]/.test(props.text);
  const voice = voices.find(v => chinese ? /^zh(?:-|_)/i.test(v.lang) : v.default) || (!chinese && voices[0]);
  if (!voice) { error.value = chinese ? '设备没有可用的中文朗读声音，请继续阅读文字。' : '设备没有可用的朗读声音，请继续阅读文字。'; stop(); return; }
  const chunks = props.text.trim().match(/[\s\S]{1,180}(?:[。！？；.!?\n]|$)|[\s\S]{1,180}/g) || [];
  let index = 0;
  function next() {
    if (version !== generation) return;
    if (index >= chunks.length) { stop(); return; }
    state.value = 'starting';
    utterance = new SpeechSynthesisUtterance(chunks[index++]); utterance.voice = voice; utterance.lang = voice.lang;
    utterance.onstart = () => { if (version === generation) { clearTimeout(timer); state.value = 'speaking'; } };
    utterance.onend = next;
    utterance.onerror = () => { if (version === generation) { error.value = '朗读未能完成，请重试或继续阅读文字。'; stop(); } };
    timer = setTimeout(() => { if (version === generation && state.value === 'starting') { error.value = '朗读未能启动，请继续阅读文字。'; stop(); } }, 8000);
    synth.speak(utterance);
  }
  next();
}
function togglePause() {
  if (state.value === 'paused') { synth.resume(); state.value = 'speaking'; }
  else if (state.value === 'speaking') { synth.pause(); state.value = 'paused'; }
}
watch(() => [props.text, props.contextKey], stop);
onBeforeUnmount(stop);
</script>
<template>
  <div class="speech-reader">
    <Button v-if="state === 'idle'" type="button" variant="ghost" size="sm" :disabled="!available || !text.trim()" @click="read"><Volume2 :size="16" />朗读</Button>
    <template v-else><Button type="button" variant="ghost" size="sm" :disabled="state === 'starting'" @click="togglePause"><Play v-if="state === 'paused'" :size="16" /><Pause v-else :size="16" />{{ state === 'starting' ? '准备朗读…' : state === 'paused' ? '继续' : '暂停' }}</Button><Button type="button" variant="ghost" size="sm" @click="stop"><Square :size="16" />停止朗读</Button></template>
    <InfoTip v-if="!available" label="朗读不可用">当前浏览器不支持朗读，可以直接阅读文字。</InfoTip>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p>
  </div>
</template>
