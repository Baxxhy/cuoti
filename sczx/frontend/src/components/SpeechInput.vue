<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { Mic, Square } from 'lucide-vue-next';
const props = defineProps({ disabled: Boolean, contextKey: [String, Number] });
const emit = defineEmits(['text']);
const Engine = window.SpeechRecognition || window.webkitSpeechRecognition;
const listening = ref(false), starting = ref(false), interim = ref(''), error = ref('');
let recognition, timer, generation = 0;
function stop() {
  generation++; clearTimeout(timer);
  if (recognition) { recognition.onresult = recognition.onerror = recognition.onend = recognition.onstart = null; recognition.abort(); recognition = null; }
  listening.value = starting.value = false; interim.value = '';
}
function toggle() {
  if (listening.value || starting.value) { stop(); return; }
  if (props.disabled || !Engine) return;
  error.value = ''; starting.value = true;
  const version = ++generation;
  try {
    const instance = new Engine(); recognition = instance;
    let received = false;
    instance.lang = 'zh-CN'; instance.continuous = false; instance.interimResults = true;
    instance.onstart = () => { if (version === generation) { clearTimeout(timer); starting.value = false; listening.value = true; } };
    instance.onresult = (event) => {
      if (version !== generation) return;
      let final = '', partial = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript;
        else partial += event.results[i][0].transcript;
      }
      interim.value = partial;
      if (final.trim()) { received = true; emit('text', final.trim()); }
    };
    instance.onerror = (event) => {
      if (version !== generation) return;
      const messages = { 'not-allowed': '未获得麦克风权限，请继续文字输入。', 'service-not-allowed': '浏览器未开放语音服务，请继续文字输入。', 'audio-capture': '未找到可用麦克风，请继续文字输入。', 'no-speech': '没有听清，请重试或直接输入。', network: '语音服务连接失败，请继续文字输入。' };
      error.value = messages[event.error] || '语音输入未完成，请重试或直接输入。'; stop();
    };
    instance.onend = () => { if (version === generation) { if (!received && !error.value) error.value = '未识别到文字，请重试或直接输入。'; stop(); } };
    timer = setTimeout(() => { if (version === generation) { error.value = '语音服务未能启动，请继续文字输入。'; stop(); } }, 8000);
    instance.start();
  } catch { error.value = '无法启动语音输入，请继续文字输入。'; stop(); }
}
watch(() => [props.contextKey, props.disabled], stop);
onBeforeUnmount(stop);
</script>
<template>
  <div class="speech-input">
    <Button type="button" variant="ghost" size="sm" :disabled="disabled || !Engine" :aria-pressed="listening || starting" :aria-label="listening || starting ? '停止语音输入' : '语音输入'" @click="toggle"><Square v-if="listening || starting" :size="16" /><Mic v-else :size="16" />{{ listening ? '停止' : starting ? '连接中…' : '语音输入' }}</Button>
    <InfoTip v-if="!Engine" label="语音输入不可用">当前浏览器不支持语音输入，可以直接打字。</InfoTip>
    <span v-if="listening || interim" role="status" aria-live="polite" class="speech-interim">{{ interim || '正在聆听…' }}</span>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  </div>
</template>
