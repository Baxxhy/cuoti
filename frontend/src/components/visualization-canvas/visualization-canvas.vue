<template>
  <view class="visual-stage">
    <canvas
      :canvas-id="canvasId"
      :id="canvasId"
      class="visual-canvas"
      :data-visualization-type="spec?.type"
    />
    <view v-if="legend.length" class="visual-legend">
      <view v-for="(label, index) in legend" :key="index" class="legend-row">
        <text class="legend-number">{{ index + 1 }}</text>
        <math-text :text="String(label ?? '')" inline />
      </view>
    </view>
  </view>
</template>

<script setup>
import MathText from '../math-text/math-text.vue'
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, watch } from 'vue'
const props = defineProps({
  spec: Object,
  values: Object,
  canvasId: { type: String, default: 'mind-visual' },
})
const legend = computed(() => {
  if (props.spec?.type === 'history_timeline')
    return (props.spec.parameters?.events || ['事件一', '事件二', '事件三']).slice(0, 5)
  if (props.spec?.type === 'timeline_map')
    return (props.spec.parameters?.places || ['甲', '乙', '丙', '丁']).slice(0, 4)
  return []
})
const instance = getCurrentInstance()
const W = 330,
  H = 230,
  ink = '#101828',
  green = '#2F6BFF',
  gold = '#D97706',
  red = '#D92D20',
  blue = '#2F6BFF',
  pale = '#EEF4FF'
let c,
  scaleX = 1,
  scaleY = 1
function line(value, width = 2) {
  c.setStrokeStyle(value)
  c.setLineWidth(width)
}
function text(value, x, y, size = 12, valueColor = ink) {
  c.setFillStyle(valueColor)
  c.setFontSize(size)
  c.fillText(String(value), x, y)
}
function n(name, fallback = 0) {
  const variable = props.spec?.interactive_variables?.find((item) => item.name === name)
  return Number(
    props.values?.[name] ?? props.spec?.parameters?.[name] ?? variable?.value ?? fallback,
  )
}
function arrow(x1, y1, x2, y2, valueColor = green, label = '') {
  const a = Math.atan2(y2 - y1, x2 - x1)
  line(valueColor, 3)
  c.beginPath()
  c.moveTo(x1, y1)
  c.lineTo(x2, y2)
  c.stroke()
  c.setFillStyle(valueColor)
  c.beginPath()
  c.moveTo(x2, y2)
  c.lineTo(x2 - 8 * Math.cos(a - 0.5), y2 - 8 * Math.sin(a - 0.5))
  c.lineTo(x2 - 8 * Math.cos(a + 0.5), y2 - 8 * Math.sin(a + 0.5))
  c.fill()
  if (label) text(label, x2 + 4, y2 - 3, 11, valueColor)
}
function axes(grid = true) {
  if (grid) {
    line('#e2e8f0', 1)
    for (let x = 25; x < W; x += 25) {
      c.beginPath()
      c.moveTo(x, 15)
      c.lineTo(x, H - 18)
      c.stroke()
    }
    for (let y = 20; y < H; y += 25) {
      c.beginPath()
      c.moveTo(20, y)
      c.lineTo(W - 12, y)
      c.stroke()
    }
  }
  line('#94a3b8', 1)
  c.beginPath()
  c.moveTo(20, 125)
  c.lineTo(318, 125)
  c.moveTo(165, 15)
  c.lineTo(165, 215)
  c.stroke()
  text('x', 310, 141, 10, '#64748b')
  text('y', 173, 22, 10, '#64748b')
}
function point(x, y, label, valueColor = green) {
  c.setFillStyle(valueColor)
  c.beginPath()
  c.arc(x, y, 5, 0, Math.PI * 2)
  c.fill()
  if (label) text(label, x + 7, y - 5, 11, valueColor)
}
function triangle() {
  const h = Math.max(45, Math.min(150, n('height', 5) * 18))
  line(green, 4)
  c.beginPath()
  c.moveTo(45, 190)
  c.lineTo(285, 190)
  c.lineTo(195, 190 - h)
  c.closePath()
  c.stroke()
  point(45, 190, 'A', gold)
  point(285, 190, 'B', gold)
  point(195, 190 - h, 'C', gold)
  line('#94a3b8', 1)
  c.beginPath()
  c.moveTo(195, 190 - h)
  c.lineTo(195, 190)
  c.stroke()
  text(`高=${n('height', 5)}，三边满足 a+b>c`, 70, 218)
}
function rightTriangle() {
  const a = Math.max(2, n('a', 3)),
    b = Math.max(2, n('b', 4)),
    s = 24
  line(green, 4)
  c.beginPath()
  c.moveTo(65, 190)
  c.lineTo(65 + a * s, 190)
  c.lineTo(65, 190 - b * s)
  c.closePath()
  c.stroke()
  line(ink, 1)
  c.strokeRect(65, 175, 15, 15)
  text(`a²+b²=${a * a}+${b * b}=${a * a + b * b}`, 180, 65)
  text(`斜边 c=${Math.sqrt(a * a + b * b).toFixed(2)}`, 180, 85)
}
function circle() {
  const cx = 165,
    cy = 125,
    r = 82,
    ang = (n('angle', 80) * Math.PI) / 180,
    A = [cx - r, cy],
    B = [cx + r, cy],
    P = [cx + r * Math.cos(ang), cy - r * Math.sin(ang)]
  line(green, 3)
  c.beginPath()
  c.arc(cx, cy, r, 0, Math.PI * 2)
  c.stroke()
  line(gold, 2)
  c.beginPath()
  c.moveTo(P[0], P[1])
  c.lineTo(A[0], A[1])
  c.moveTo(P[0], P[1])
  c.lineTo(B[0], B[1])
  c.stroke()
  line(red, 2)
  c.beginPath()
  c.moveTo(A[0], A[1])
  c.lineTo(B[0], B[1])
  c.stroke()
  point(P[0], P[1], 'P', gold)
  text('直径所对圆周角始终为90°', 82, 218)
}
function functionGraph(type) {
  const cx = n('center_x', 0),
    cy = n('center_y', 0),
    xs = n('x_span', 6),
    ys = n('y_span', 6),
    pxFor = (x) => 169 + ((x - cx) * 149) / xs,
    pyFor = (y) => 115 - ((y - cy) * 100) / ys,
    tickText = (value) => Number(value.toPrecision(6)).toString()
  line('#e2e8f0', 1)
  for (let i = -3; i <= 3; i++) {
    const x = cx + (i * xs) / 3,
      y = cy + (i * ys) / 3,
      px = pxFor(x),
      py = pyFor(y)
    c.beginPath()
    c.moveTo(px, 15)
    c.lineTo(px, 215)
    c.moveTo(20, py)
    c.lineTo(318, py)
    c.stroke()
    if (i % 2 === 0) {
      text(tickText(x), px - 10, 211, 9, '#64748b')
      text(tickText(y), 22, py - 3, 9, '#64748b')
    }
  }
  line('#94a3b8', 1)
  c.beginPath()
  if (Math.abs(cx) <= xs) {
    c.moveTo(pxFor(0), 15)
    c.lineTo(pxFor(0), 215)
  }
  if (Math.abs(cy) <= ys) {
    c.moveTo(20, pyFor(0))
    c.lineTo(318, pyFor(0))
  }
  c.stroke()
  text('x', 310, 210, 10, '#64748b')
  text('y', 22, 23, 10, '#64748b')
  c.save()
  c.beginPath()
  c.rect(20, 15, 298, 200)
  c.clip()
  line(type === 'linear_function' ? green : red, 3)
  c.beginPath()
  for (let px = 20; px <= 318; px += 2) {
    const x = cx + ((px - 169) * xs) / 149,
      y =
        type === 'linear_function'
          ? n('k', 1) * x + n('b', 0)
          : n('a', 1) * (x - n('h', 0)) ** 2 + n('k', 0),
      py = pyFor(y)
    if (px === 20) c.moveTo(px, py)
    else c.lineTo(px, py)
  }
  c.stroke()
  c.restore()
  text('改变参数，比较图像的位置和形状', 28, 226, 12, type === 'linear_function' ? green : red)
}

function coordinate() {
  axes()
  const p = (x, y) => [165 + x * 28, 125 - y * 24],
    A = p(-3, -2),
    B = p(n('bx', 3), n('by', 2)),
    M = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2]
  line(gold, 3)
  c.beginPath()
  c.moveTo(...A)
  c.lineTo(...B)
  c.stroke()
  point(...A, 'A')
  point(...B, 'B')
  point(...M, 'M', red)
  text(
    `中点 M(${((-3 + n('bx', 3)) / 2).toFixed(1)},${((-2 + n('by', 2)) / 2).toFixed(1)})`,
    26,
    28,
  )
}
function balance() {
  const d = n('delta', 3)
  line(ink, 4)
  c.beginPath()
  c.moveTo(165, 40)
  c.lineTo(165, 178)
  c.moveTo(60, 72)
  c.lineTo(270, 72)
  c.stroke()
  line(ink, 1)
  c.beginPath()
  c.moveTo(60, 72)
  c.lineTo(40, 145)
  c.moveTo(60, 72)
  c.lineTo(95, 145)
  c.moveTo(270, 72)
  c.lineTo(235, 145)
  c.moveTo(270, 72)
  c.lineTo(290, 145)
  c.stroke()
  c.setFillStyle(gold)
  c.fillRect(28, 145, 78, 10)
  c.fillRect(224, 145, 78, 10)
  if (props.spec?.parameters?.task_bound) {
    text('原等式左边', 32, 132)
    text('原等式右边', 228, 132)
    text(`同减 ${d}`, 36, 180)
    text(`同减 ${d}`, 232, 180)
  } else {
    text(`${n('left', 11)}-${d}=${n('left', 11) - d}`, 36, 180)
    text(`${n('right', 11)}-${d}=${n('right', 11) - d}`, 232, 180)
  }
  text('等式两边同操作，平衡不变', 82, 215)
}
function uniformMotion() {
  const t = n('time', 4),
    pos = Math.min(245, t * 28)
  line('#94a3b8', 3)
  c.beginPath()
  c.moveTo(28, 170)
  c.lineTo(305, 170)
  c.stroke()
  for (let i = 0; i <= 10; i++) text(i, 25 + i * 28, 190, 9)
  c.setFillStyle(gold)
  c.fillRect(28 + pos, 145, 34, 18)
  c.beginPath()
  c.arc(37 + pos, 168, 6, 0, 7)
  c.arc(53 + pos, 168, 6, 0, 7)
  c.fill()
  text(`s=vt=2×${t}=${2 * t}`, 110, 48, 15)
}
function acceleration() {
  axes()
  const a = n('acceleration', 1),
    t = n('time', 5)
  c.setFillStyle('rgba(245,158,11,.22)')
  c.beginPath()
  c.moveTo(165, 125)
  c.lineTo(165, 105)
  c.lineTo(165 + t * 24, 105 - a * t * 13)
  c.lineTo(165 + t * 24, 125)
  c.fill()
  line(green, 3)
  c.beginPath()
  c.moveTo(165, 105)
  c.lineTo(165 + t * 24, 105 - a * t * 13)
  c.stroke()
  text(`斜率a=${a}，末速度=${(1 + a * t).toFixed(1)}`, 28, 28)
}
function projectile() {
  const v = n('speed', 9),
    ang = (n('launch_angle', 45) * Math.PI) / 180
  line('#94a3b8', 2)
  c.beginPath()
  c.moveTo(20, 195)
  c.lineTo(315, 195)
  c.stroke()
  line(red, 3)
  c.beginPath()
  let started = false
  for (let t = 0; t < 5; t += 0.04) {
    const px = 30 + v * Math.cos(ang) * t * 7,
      py = 195 - (v * Math.sin(ang) * t - 4.9 * t * t) * 7
    if (py > 195 && t > 0.1) break
    started ? c.lineTo(px, py) : c.moveTo(px, py)
    started = true
  }
  c.stroke()
  arrow(30, 195, 30 + v * Math.cos(ang) * 7, 195 - v * Math.sin(ang) * 7, green, 'v₀')
  text(`初速度${v}，发射角${n('launch_angle', 45)}°`, 94, 35)
}
function force() {
  c.setFillStyle(pale)
  c.fillRect(115, 85, 100, 70)
  line(ink, 2)
  c.strokeRect(115, 85, 100, 70)
  text('物体', 152, 125)
  const f = n('applied', 3)
  arrow(165, 85, 165, 35, blue, 'N')
  arrow(165, 155, 165, 210, red, 'G')
  arrow(f >= 0 ? 215 : 115, 120, f >= 0 ? 215 + f * 13 : 115 + f * 13, 120, gold, 'F')
  text(`水平合力：${f > 0 ? '向右' : f < 0 ? '向左' : '平衡'}`, 105, 24)
}
function energy() {
  const h = Math.max(0, Math.min(10, n('height', 6))),
    total = 10
  c.setFillStyle(green)
  c.fillRect(70, 190 - h * 14, 70, h * 14)
  c.setFillStyle(gold)
  c.fillRect(195, 190 - (total - h) * 14, 70, (total - h) * 14)
  text(`势能 ${h}`, 80, 212)
  text(`动能 ${total - h}`, 200, 212)
  text(`总机械能 ${total} 保持不变`, 92, 35, 14)
}
function pressure() {
  const area = Math.max(1, n('area', 4)),
    w = area * 30
  c.setFillStyle(pale)
  c.fillRect(165 - w / 2, 65, w, 90)
  line(ink, 2)
  c.strokeRect(165 - w / 2, 65, w, 90)
  for (let i = 0; i < Math.max(2, 9 - area); i++) arrow(115 + i * 14, 175, 115 + i * 14, 205, red)
  text(`p=F/S=8/${area}=${(8 / area).toFixed(2)}`, 100, 35, 14)
  text(`接触面积 ${area}`, 130, 168)
}
function buoyancy() {
  const sub = Math.max(0, Math.min(100, n('submerged', 60)))
  c.setFillStyle('rgba(96,165,250,.35)')
  c.fillRect(30, 110, 270, 110)
  line(blue, 2)
  c.beginPath()
  c.moveTo(30, 110)
  c.lineTo(300, 110)
  c.stroke()
  const top = 55 + sub * 0.55
  c.setFillStyle(gold)
  c.fillRect(135, top, 60, 90)
  line(ink, 1)
  c.strokeRect(135, top, 60, 90)
  arrow(165, top + 60, 165, top + 60 - sub * 0.55, green, 'F浮')
  text(`浸入${sub}%：排液体积与浮力同步变化`, 65, 28)
}
function history() {
  const events = props.spec.parameters?.events || ['事件一', '事件二', '事件三'],
    focus = Math.max(0, Math.min(events.length - 1, Math.round(n('focus', 1))))
  line(green, 3)
  c.beginPath()
  c.moveTo(30, 130)
  c.lineTo(300, 130)
  c.stroke()
  events.slice(0, 5).forEach((event, index) => {
    const px = 45 + index * 62
    point(px, 130, '', index === focus ? red : gold)
    text(String(index + 1), px - 18, index % 2 ? 165 : 100, 10, index === focus ? red : ink)
  })
  text(`当前：事件 ${focus + 1}`, 100, 210, 13)
}
function timelineMap() {
  const places = props.spec.parameters?.places || ['甲', '乙', '丙', '丁'],
    stage = Math.max(0, Math.min(places.length - 1, Math.round(n('stage', 2)))),
    points = [
      [45, 150],
      [120, 65],
      [205, 150],
      [285, 75],
    ]
  points.forEach((p, index) => {
    c.setFillStyle(index <= stage ? gold : '#dbe3df')
    c.beginPath()
    c.arc(p[0], p[1], 19, 0, 7)
    c.fill()
    text(String(index + 1), p[0] - 10, p[1] + 4, 10)
    if (index < stage)
      arrow(
        p[0] + 19,
        p[1],
        points[index + 1][0] - 19,
        points[index + 1][1],
        green,
        String(index + 1),
      )
  })
  text(`传播阶段${stage + 1}：时空联系逐步展开`, 65, 215)
}

const drawers = {
  triangle,
  right_triangle: rightTriangle,
  circle,
  linear_function: () => functionGraph('linear_function'),
  quadratic_function: () => functionGraph('quadratic_function'),
  coordinate_geometry: coordinate,
  equation_balance: balance,
  uniform_motion: uniformMotion,
  uniform_acceleration: acceleration,
  projectile_motion: projectile,
  force_diagram: force,
  work_energy: energy,
  pressure,
  buoyancy,
  history_timeline: history,
  timeline_map: timelineMap,
}
function draw() {
  if (!props.spec) return
  c = uni.createCanvasContext(props.canvasId, instance?.proxy)
  c.save?.()
  c.scale?.(scaleX, scaleY)
  c.setFillStyle('#fff')
  c.fillRect(0, 0, W, H)
  c.setLineCap('round')
  c.setLineJoin('round')
  ;(drawers[props.spec.type] || (() => text('暂不支持的演示类型', 95, 120)))()
  c.restore?.()
  c.draw()
}
function measure() {
  const query = uni.createSelectorQuery?.()
  if (!query) {
    draw()
    return
  }
  query
    .in(instance?.proxy)
    .select('.visual-canvas')
    .boundingClientRect((box) => {
      if (box?.width && box?.height) {
        scaleX = box.width / W
        scaleY = box.height / H
      }
      draw()
    })
    .exec()
}
onMounted(() => {
  measure()
  uni.onWindowResize?.(measure)
})
onBeforeUnmount(() => uni.offWindowResize?.(measure))
watch(() => [props.spec, JSON.stringify(props.values)], draw, { deep: true })
</script>

<style scoped>
.visual-stage {
  min-height: 500rpx;
  border-radius: 22rpx;
  background: #fff;
  overflow: hidden;
}
.visual-legend {
  padding: 0 24rpx 24rpx;
}
.legend-row {
  display: flex;
  gap: 16rpx;
  align-items: baseline;
  margin-top: 12rpx;
}
.legend-number {
  flex: none;
  color: #2f6bff;
}
.visual-canvas {
  width: 660rpx;
  height: 460rpx;
  max-width: 100%;
}
</style>
