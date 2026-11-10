export const sameAgentRoute=(a,b)=>String(a.job||'')===String(b.job||'')&&String(a.lesson||'')===String(b.lesson||'')&&String(a.block||'')===String(b.block||'');
