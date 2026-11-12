<script>
import { defineComponent, h } from 'vue';
import { Check, Clock3, CirclePlay, CircleAlert, Info } from '@/components/app/icons.js';
import { ElTag } from 'element-plus';
import { statusTone, statusText } from '@/lib/status-tone.js';
const icons={success:Check,pending:Clock3,active:CirclePlay,danger:CircleAlert,info:Info};
export default defineComponent({
  props:{tone:{type:String,default:'neutral'}},
  setup(props,{slots}) {
    return()=>{
      const children=slots.default?.()||[];
      const tone=statusTone(statusText(children),props.tone);
      return h(ElTag,{type:({success:'success',pending:'warning',active:'primary',danger:'danger',info:'info',neutral:'info'})[tone],effect:'light',class:['status-badge',`tone-${tone}`],'data-status':tone},{default:()=>[icons[tone]?h(icons[tone],{'aria-hidden':'true',size:13,strokeWidth:2}):null,...children]});
    };
  }
});
</script>
