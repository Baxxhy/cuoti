from pathlib import Path
import hashlib,json
root=Path.cwd();old=json.loads(Path('/tmp/sczx-step20/private.json').read_text());manifest=json.loads((Path(old['releaseRoot'])/'release-manifest.json').read_text());checked=[];changed=[]
for path,digest in manifest['files'].items():
 if path.startswith(('backend-business/sczx_business/','frontend/src/','frontend/dist/')) and path not in ['frontend/dist/build-info.json','frontend/dist/sw.js']:
  p=root/path;checked.append(path)
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:changed.append(path)
assert not changed,changed
Path('/tmp/sczx-local-final/component-provenance.json').write_text(json.dumps({'baseline':old['releaseSha'],'sameSourceAndBuiltApplicationFiles':len(checked),'changedApplicationFiles':changed,'generatedServiceWorker':'重新构建更新sw.js缓存版本；源文件未变，另在本地重新验证离线关闭重开和同步','changes':'本轮新增本地启动控制、测试及文档；业务服务和前端未改','reusedEvidence':'docs/verification/final_20261111_v1；旧35项结果保留，不将复用写成新执行'},ensure_ascii=False,indent=2));print('unchanged app files',len(checked))
