import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {createPickerMotion} from '../src/platform/picker-motion.js'

let motion,element
const position=()=>Number(element.style.transform.match(/translateY\(([-\d.]+)px\)/)[1])
function setup(count=10){
 const parent=document.createElement('div');element=document.createElement('div');parent.append(element)
 Object.defineProperty(parent,'offsetHeight',{value:238})
 Object.defineProperty(element,'offsetHeight',{value:238+(count-1)*34})
 const selected=vi.fn();motion=createPickerMotion(element,count,0,selected);return selected
}
beforeEach(()=>{
 vi.useFakeTimers();vi.setSystemTime(new Date('2026-11-07T00:00:00Z'))
 vi.stubGlobal('requestAnimationFrame',callback=>setTimeout(callback,16))
 vi.stubGlobal('cancelAnimationFrame',id=>clearTimeout(id))
})
afterEach(()=>{motion?.stop();vi.useRealTimers();vi.unstubAllGlobals()})
describe('picker drag, friction and spring behavior',()=>{
 it('follows a slow drag continuously and snaps to the nearest row',()=>{
  const selected=setup()
  motion.start(400,0);motion.move(361,20)
  expect(position()).toBe(-39)
  motion.end(361)
  expect(position()).toBe(-34)
  expect(selected).toHaveBeenLastCalledWith(1)
 })
 it('continues a fast swipe after release and returns within the wheel bounds',()=>{
  const selected=setup()
  motion.start(400,0);motion.move(350,20);motion.move(300,40);motion.end(300)
  vi.advanceTimersByTime(100)
  expect(position()).toBeLessThan(-100)
  vi.advanceTimersByTime(5000)
  expect(position()).toBeCloseTo(-306,0)
  expect(motion.scrolling()).toBe(false)
  expect(selected).toHaveBeenCalled()
  expect(selected.mock.lastCall[0]).toBeGreaterThanOrEqual(0)
  expect(selected.mock.lastCall[0]).toBeLessThan(10)
 })
 it('resists dragging past the first row and cancels pending animation when closed',()=>{
  setup()
  motion.start(400,0);motion.move(500,20)
  expect(position()).toBe(50)
  motion.end(500)
  vi.advanceTimersByTime(100)
  expect(position()).toBeLessThan(50)
  motion.stop();const stopped=position()
  vi.advanceTimersByTime(5000)
  expect(position()).toBe(stopped)
  expect(motion.scrolling()).toBe(false)
 })
})
