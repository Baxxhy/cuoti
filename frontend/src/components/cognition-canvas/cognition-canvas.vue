<template>
  <view class="graph-wrap">
    <canvas canvas-id="cognition-graph" id="cognition-graph" class="graph-canvas" />
    <button
      tabindex="0"
      role="button"
      v-for="point in points"
      :key="point.id"
      class="graph-node"
      :aria-label="point.name"
      :aria-pressed="selectedId === point.id"
      :class="[{ selected: selectedId === point.id }, point.category]"
      :style="nodeStyle(point)"
      @click.stop="selectPoint(point)"
    >
      <view class="node-dot" />
      <text>{{ shortName(point.name) }}</text>
    </button>
    <text v-if="!graph?.nodes?.length" class="graph-empty">
      完成错题学习后，这里会形成知识与错因关系
    </text>
    <text v-else class="graph-tip">
      {{ selectedId ? '已聚焦该节点，详情显示在图谱下方' : '点击节点查看它的一层关系' }}
    </text>
  </view>
</template>
<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
const props = defineProps({ graph: Object })
const emit = defineEmits(['select'])
const selectedId = ref(''),
  points = ref([])
const colors = {
  knowledge: '#2F6BFF',
  misconception: '#E94B4B',
  question: '#E99A22',
  strategy: '#72809A',
}
function visibleData() {
  const nodes = (props.graph?.nodes || []).slice(0, 10),
    links = props.graph?.links || []
  if (!selectedId.value) return { nodes: nodes.slice(0, 8), links }
  const related = new Set([selectedId.value])
  links.forEach((link) => {
    if (link.source === selectedId.value) related.add(link.target)
    if (link.target === selectedId.value) related.add(link.source)
  })
  return { nodes: nodes.filter((node) => related.has(node.id)).slice(0, 8), links }
}
function draw() {
  const ctx = uni.createCanvasContext('cognition-graph'),
    w = 350,
    h = 300,
    { nodes, links } = visibleData()
  ctx.setFillStyle('#fff')
  ctx.fillRect(0, 0, w, h)
  points.value = nodes.map((node) => {
    if (selectedId.value && node.id === selectedId.value) return { ...node, x: 175, y: 145 }
    const others = nodes.filter((item) => item.id !== selectedId.value),
      position = others.findIndex((item) => item.id === node.id),
      angle = (Math.PI * 2 * Math.max(0, position)) / Math.max(others.length, 1) - Math.PI / 2
    return { ...node, x: 175 + Math.cos(angle) * 105, y: 145 + Math.sin(angle) * 90 }
  })
  ctx.setStrokeStyle('#DCE2E0')
  ctx.setLineWidth(1)
  links.forEach((link) => {
    const a = points.value.find((x) => x.id === link.source),
      b = points.value.find((x) => x.id === link.target)
    if (a && b) {
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
    }
  })
  ctx.draw()
}
function shortName(value) {
  const text = String(value || '')
  return text.length > 9 ? `${text.slice(0, 9)}…` : text
}
function nodeStyle(point) {
  return {
    left: `${point.x / 3.5}%`,
    top: `${point.y / 3}%`,
    '--node-color': colors[point.category] || '#72809A',
  }
}
function selectPoint(point) {
  selectedId.value = selectedId.value === point.id ? '' : point.id
  emit('select', selectedId.value ? point : null)
  nextTick(draw)
}
onMounted(draw)
watch(
  () => props.graph,
  () => {
    selectedId.value = ''
    draw()
  },
  { deep: true },
)
</script>
<style scoped>
.graph-wrap {
  height: 600rpx;
  position: relative;
  background: #fff;
  border: 1rpx solid var(--color-border);
  border-radius: 28rpx;
  overflow: hidden;
}
.graph-canvas {
  width: 700rpx;
  height: 600rpx;
  max-width: 100%;
}
.graph-node {
  background: transparent;
  border: 0;
  margin: 0;
  padding: 0;
  position: absolute;
  width: 190rpx;
  min-height: 108rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  transform: translate(-50%, -38%);
  z-index: 2;
}
.node-dot {
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  background: var(--node-color);
  border: 6rpx solid #fff;
  box-shadow: 0 2rpx 8rpx rgba(15, 23, 42, 0.18);
}
.graph-node text {
  display: block;
  max-width: 190rpx;
  margin-top: 5rpx;
  padding: 2rpx 5rpx;
  border-radius: 7rpx;
  background: rgba(255, 255, 255, 0.9);
  color: #334155;
  font-size: 20rpx;
  line-height: 1.25;
  text-align: center;
}
.graph-node.selected .node-dot {
  width: 68rpx;
  height: 68rpx;
  border-color: #dce8ff;
  box-shadow: 0 0 0 5rpx rgba(47, 107, 255, 0.18);
}
.graph-node.selected text {
  font-weight: 600;
  color: #172b4d;
}
.graph-empty {
  position: absolute;
  inset: 0;
  padding: 100rpx 50rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 24rpx;
}
.graph-tip {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 14rpx;
  z-index: 3;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 21rpx;
  pointer-events: none;
}
</style>
