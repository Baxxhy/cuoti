<template>
  <div class="graph-wrap">
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
      <div class="node-dot" />
      <math-text class="node-label" :text="point.name" inline />
    </button>
    <span v-if="!graph?.nodes?.length" class="graph-empty">
      完成错题学习后，这里会形成知识与错因关系
    </span>
    <span v-else class="graph-tip">
      {{ selectedId ? '已聚焦该节点，详情显示在图谱下方' : '点击节点查看它的一层关系' }}
    </span>
  </div>
</template>
<script setup>
import { browser } from '@/platform/browser.js'
import MathText from '@/components/math-text/math-text.vue'
import { getCurrentInstance, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps({ graph: Object })
const emit = defineEmits(['select'])
const instance = getCurrentInstance()
let scaleX = 1,
  scaleY = 1
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
  const ctx = browser.createCanvasContext('cognition-graph', instance?.proxy),
    w = 350,
    h = 300,
    { nodes, links } = visibleData()
  ctx.save?.()
  ctx.scale?.(scaleX, scaleY)
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
  ctx.restore?.()
  ctx.draw()
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
function measure() {
  const query = browser.createSelectorQuery?.()
  if (!query) return draw()
  query
    .in(instance?.proxy)
    .select('.graph-canvas')
    .boundingClientRect((box) => {
      if (box?.width && box?.height) {
        scaleX = box.width / 350
        scaleY = box.height / 300
      }
      draw()
    })
    .exec()
}
onMounted(() => {
  measure()
  browser.onWindowResize?.(measure)
})
onBeforeUnmount(() => browser.offWindowResize?.(measure))
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
  height: 300.0px;
  position: relative;
  background: #fff;
  border: 0.5px solid var(--color-border);
  border-radius: 14.0px;
  overflow: hidden;
}
.graph-canvas {
  width: 100%;
  height: 100%;
}
.graph-node {
  background: transparent;
  border: 0;
  margin: 0;
  padding: 0;
  position: absolute;
  width: 95.0px;
  min-height: 54.0px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  transform: translate(-50%, -13.0px);
  z-index: 2;
}
.node-dot {
  width: 26.0px;
  height: 26.0px;
  border-radius: 50%;
  background: var(--node-color);
  border: 3.0px solid #fff;
  box-shadow: 0 1.0px 4.0px rgba(15, 23, 42, 0.18);
}
.graph-node .node-label {
  display: block;
  max-width: 95.0px;
  margin-top: 2.5px;
  padding: 1.0px 2.5px;
  border-radius: 3.5px;
  background: rgba(255, 255, 255, 0.9);
  color: #334155;
  font-size: 10.0px;
  line-height: 1.8;
  text-align: center;
}
.graph-node.selected .node-dot {
  width: 34.0px;
  height: 34.0px;
  border-color: #dce8ff;
  box-shadow: 0 0 0 2.5px rgba(47, 107, 255, 0.18);
}
.graph-node.selected {
  transform: translate(-50%, -17.0px);
}
.graph-node.selected .node-label {
  font-weight: 600;
  color: #172b4d;
}
.graph-empty {
  position: absolute;
  inset: 0;
  padding: 50.0px 25.0px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 12.0px;
}
.graph-tip {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 7.0px;
  z-index: 3;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 10.5px;
  pointer-events: none;
}
</style>
