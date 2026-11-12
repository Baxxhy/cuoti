// Shared presentation semantics. These labels never change the stored business status.
const aliases = { green:'success', amber:'pending', blue:'active', red:'danger', cyan:'info' };
export function statusTone(label, fallback='neutral') {
  const text=String(label||'').trim();
  // Negative/uncertain evidence takes precedence over a positive word in the same label.
  if (/失败|错误|异常|不一致|不正确|逾期|已过期|已失效/.test(text)) return 'danger';
  if (/草稿|已取消|已撤|已停|已结束|已关闭|已移出|历史|仅.*回看|未开放|待开放|未配置/.test(text)) return 'neutral';
  if (/未完成|未开始|未答|未提交|未审核|未读|待|等待|排队|逾期|需.*核对|需要订正|证据不足|尚无|未通过/.test(text)) return 'pending';
  if (/进行中|学习中|考试中|处理中|生成中|正在|保存中|识别中|上传中/.test(text)) return 'active';
  if (/已完成|已提交|已交卷|已反馈|已发布|已审核|已核验|已保存|已生成|已就绪|已确认|已掌握|已通过|已解决|成功|正确|有效|^就绪$/.test(text)) return 'success';
  if (/帮助|提示|独立作答|独立练习|已有独立正确证据/.test(text)) return 'info';
  const tone=aliases[fallback]||fallback;
  return ['neutral','pending','active','success','danger','info'].includes(tone)?tone:'neutral';
}
export function statusText(nodes) {
  if (typeof nodes==='string'||typeof nodes==='number') return String(nodes);
  if (Array.isArray(nodes)) return nodes.map(statusText).join('');
  return nodes&&typeof nodes==='object'?statusText(nodes.children):'';
}
