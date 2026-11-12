import {defineComponent,h} from 'vue';
import {ElEmpty} from 'element-plus';
import {statusText} from '@/lib/status-tone.js';
export default defineComponent({setup(_, {slots}) {return()=>{
 const nodes=slots.default?.()||[];
 const heading=nodes.find(node=>['h1','h2','h3'].includes(node.type));
 const description=heading||nodes.find(node=>node.type==='p')||nodes.find(node=>typeof node.type==='symbol'&&typeof node.children==='string'&&node.children.trim());
 const actions=nodes.filter(node=>node!==description&&node.type!=='svg'&&typeof node.type!=='function'&&typeof node.props?.size!=='number');
 return h(ElEmpty,{description:statusText(description?.children)||'暂无内容',imageSize:88,class:'app-element-empty'},{description:()=>description||'暂无内容',default:()=>actions});
}}});
