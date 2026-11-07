import {Scroller,Friction,Spring} from './vendor/picker-scroll.js'

// The wheel's geometry is fixed by web-picker.css. Initialize after its DOM exists;
// do not measure the temporary unpadded layout during component construction.
export function createPickerMotion(element,count,index,onSelect){
 const motion=new Scroller(element,{enableY:true,enableX:false,enableSnap:true,itemSize:34,friction:new Friction(1e-4),spring:new Spring(2,90,20),onSnap:value=>onSelect(Math.max(0,Math.min(count-1,value)))})
 motion._extent=Math.max(0,(count-1)*34)
 motion._scroll._extent=motion._extent
 motion.scrollTo(index*34)
 motion.onTransitionEnd()
 let startY=0,history=[]
 return {
  scrolling:()=>Boolean(motion.isScrolling()),
  select:value=>motion.scrollTo(value*34),
  start(y,time){startY=y;history=[{y:0,time}];motion.onTouchStart()},
  move(y,time){const delta=y-startY;history.push({y:delta,time});if(history.length>10)history.shift();motion.onTouchMove(0,delta)},
  end(y){
   let velocity=0
   if(history.length>2){const last=history.at(-1);for(let i=history.length-2;i>=0;i--){const elapsed=last.time-history[i].time;if(elapsed>30&&elapsed<50){velocity=(last.y-history[i].y)/(elapsed/1000);break}}}
   motion.onTouchEnd(0,y-startY,{x:0,y:velocity});history=[]
  },
  stop(){motion._animation?.cancel();motion._scrolling=false;motion._snapping=false;motion.onTransitionEnd();history=[]}
 }
}
