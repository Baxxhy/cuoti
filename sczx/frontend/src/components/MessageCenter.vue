<script setup>
import { ref, onMounted, computed } from "vue";
import { useLearning } from "@/store.js";
import { teachingApi, deadlineText } from "@/services/teaching.js";
import { navigate } from "@/lib/navigation.js";
import { ArrowUpRight, RefreshCw, Check } from "lucide-vue-next";
const props = defineProps({ compact: Boolean });
const emit = defineEmits(["navigate"]);
const store = useLearning(),
  box = ref("inbox"),
  rows = ref([]),
  error = ref(""),
  busy = ref(false);
let generation = 0;
const visible = computed(() =>
  props.compact ? rows.value.slice(0, 3) : rows.value,
);
async function load() {
  const version = ++generation;
  busy.value = true;
  error.value = "";
  try {
    const values = await teachingApi.messages(box.value);
    if (version !== generation) return;
    rows.value = values;
    if (box.value === "inbox") store.notifications = values;
  } catch (e) {
    if (version === generation) error.value = e.message;
  } finally {
    if (version === generation) busy.value = false;
  }
}
async function read(item) {
  try {
    await teachingApi.read(item.id);
    item.readAt = new Date().toISOString();
    store.notifications = store.notifications.map((m) =>
      m.id === item.id ? { ...m, readAt: item.readAt } : m,
    );
  } catch (e) {
    error.value = e.message;
  }
}
async function open(item) {
  if (box.value === "inbox") await read(item);
  if (!(await store.save())) return;
  await store.load(store.data.lesson?.id, true);
  emit("navigate");
  navigate(
    (store.user.role === "teacher"
      ? "insights"
      : item.kind === "feedback"
        ? "result"
        : "learn") +
      "?task=" +
      item.taskId +
      (item.objectId ? "&supplement=" + item.objectId : ""),
  );
}
onMounted(load);
</script>
<template>
  <div :class="['message-center',{'message-center-compact':compact}]">
    <header v-if="!compact">
      <AppTabs
        v-model="box"
        :items="
          store.user.role === 'teacher'
            ? [
                { value: 'inbox', label: '收到的消息' },
                { value: 'sent', label: '发送记录' },
              ]
            : [{ value: 'inbox', label: '我的消息' }]
        "
        @update:model-value="load"
      /><Button
        variant="ghost"
        size="icon-sm"
        aria-label="刷新消息"
        :disabled="busy"
        @click="load"
        ><RefreshCw :size="16"
      /></Button>
    </header>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p>
    <p v-if="busy" role="status">读取中…</p>
    <template v-if="compact"><button v-for="item in visible" :key="item.id" class="compact-message" @click="open(item)"><span :class="{'compact-message-unread':!item.readAt}" aria-hidden="true"/><span><strong>{{item.title.replaceAll('\u00b7',' ')}}</strong><time>{{deadlineText(item.createdAt)}}</time></span><ArrowUpRight :size="14"/></button></template>
    <article v-else
      v-for="item in visible"
      :key="item.id"
      :class="{ unread: !item.readAt }"
    >
      <div>
        <Status>{{ item.readAt ? "已读" : "未读" }}</Status
        ><span
          >{{ item.className }} 　
          {{ box === "sent" ? item.recipientName : item.senderName }}</span
        ><time>{{ deadlineText(item.createdAt) }}</time>
      </div>
      <h3>{{ item.title.replaceAll('\u00b7',' ') }}</h3>
      <p v-if="item.body" class="preserve-lines">{{ item.body }}</p>
      <footer>
        <Button
          v-if="box === 'inbox' && !item.readAt"
          variant="ghost"
          @click="read(item)"
          ><Check :size="14" />标为已读</Button
        ><Button variant="outline" @click="open(item)"
          >查看任务<ArrowUpRight :size="14"
        /></Button>
      </footer>
    </article>
    <p v-if="!busy && !rows.length" class="muted">暂无消息</p>
  </div>
</template>
