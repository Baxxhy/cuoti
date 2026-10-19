from pathlib import Path
import zipfile,json,hashlib
B=Path(__file__).resolve().parent;O=B.parent;D=O/'figures/academic_v5'
files=[O/('错题帮_'+kind+'_参赛定稿'+ext) for kind in ['项目说明文档','系统设计文档'] for ext in ['.docx','.md']]
files += [O/name for name in ['参赛定稿交付说明.md','技术事实与验证证据.md','参考资料与案例出处.md','运行与第三方依赖说明.md']]
files += [D/(f'{i:02d}'+ext) for i in range(1,16) for ext in ['.png','_final_prompt.txt']]
files += [D/'提示词与图表说明.md']
files += [O/'figures/screenshots'/name for name in ['today-detail.png','map-detail.png','diagnosis-detail.png','repair-detail.png']]
assert all(f.is_file() for f in files)
assert len(files)==len(set(files))==43
target=O/'错题帮_仓颉杯Word参赛定稿.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for f in files:z.write(f,str(f.relative_to(O)))
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 assert not any(n.endswith('.pdf') or n.startswith(('review/','originals/','build_')) for n in z.namelist())
 for f in files:assert z.read(str(f.relative_to(O)))==f.read_bytes()
report={'zip':target.name,'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'crc_ok':True,'matches_sources':True,'entries':{str(f.relative_to(O)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(B/'package_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report)
