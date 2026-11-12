/* Verify application-owned primitives; Element Plus generates its own native DOM. */
const fs=require('node:fs'),path=require('node:path'),postcss=require('postcss');
const {parse}=require('@vue/compiler-sfc'),{baseParse}=require('@vue/compiler-dom');
const root=path.resolve(__dirname,'../src'),files=[],frames=new Set(),tags={},native=[],manual=[],hidden=[],adapters={};
function scan(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())scan(p);else files.push(p)}}
function css(text){postcss.parse(text).walkRules(rule=>{if(!rule.nodes.some(d=>d.type==='decl'&&/^(?:border(?:-(?:top|right|bottom|left))?(?:-(?:radius|width|style|color))?|box-shadow|background(?:-color)?)$/.test(d.prop)&&!/^0(?:px)?(?:\s|$)|^(?:none|transparent)$/.test(d.value)))return;for(const selector of rule.selectors||[]){const m=selector.trim().split(/[>+~\s]+/).pop().match(/^\.([\w-]+)(?::\w+)?$/);if(m)frames.add(m[1])}})}
scan(root);
for(const file of files){const text=fs.readFileSync(file,'utf8');if(file.endsWith('.css'))css(text);if(file.endsWith('.vue'))for(const s of parse(text).descriptor.styles)css(s.content)}
for(const file of files){if(!file.endsWith('.vue'))continue;const text=fs.readFileSync(file,'utf8'),parsed=parse(text),d=parsed.descriptor,name=path.relative(root,file);if(parsed.errors.length)throw Error(name+': invalid template');if(name.startsWith('components/app/'))adapters[path.basename(file)]=[...new Set(text.match(/\bEl[A-Z]\w+/g)||[])];if(!d.template)continue;
 function walk(n){if(n.type===1){tags[n.tag]=(tags[n.tag]||0)+1;if(['button','input','textarea','select','img','dialog','details','summary','form','a','progress','meter','video','svg'].includes(n.tag))native.push({file:name,tag:n.tag});if(n.tag==='audio'){if(!n.props.some(p=>p.name==='hidden')||n.props.some(p=>p.name==='controls'))native.push({file:name,tag:n.tag});else hidden.push({file:name,kind:'hidden playback engine; no native UI'})}if(/^[a-z]/.test(n.tag)&&n.tag!=='component')for(const c of n.props.find(x=>x.name==='class')?.value?.content?.split(/\s+/)||[])if(frames.has(c))manual.push({file:name,tag:n.tag,class:c})}for(const c of n.children||[])walk(c)}walk(baseParse(d.template.content));
}
const pkg=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../package.json'),'utf8'));
const report={nativeUiNodes:native,cssDrawnNativeFrames:manual,hiddenMediaEngines:hidden,iconProvider:'@element-plus/icons-vue',uiProviders:['element-plus','@element-plus/icons-vue'],dependencies:pkg.dependencies,adapters,templateTags:tags};
if(native.length||manual.length)throw Error(JSON.stringify({native,manual}));
if(process.argv[2])fs.writeFileSync(path.resolve(process.argv[2]),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({nativeUiNodes:native.length,cssDrawnNativeFrames:manual.length,hiddenMediaEngines:hidden.length,cardSites:tags.Surface,buttonSites:tags.AppButton}));
