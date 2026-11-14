#!/usr/bin/env python3
"""Preview by default; publish only exact human-reviewed bundle entries. No migrations."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sczx_business.curated_resources import import_resources,load_bundle,reviewed

def main():
    p=argparse.ArgumentParser();p.add_argument('--admin-id');p.add_argument('--apply',action='store_true');p.add_argument('--check-only',action='store_true');p.add_argument('--output');args=p.parse_args()
    if args.check_only:
        bundle,sources,review=load_bundle();result={'entries':len(bundle['entries']),'subjects':len({r['subject'] for r in bundle['entries']}),'reviewedSummaries':sum(bool(reviewed(r,sources[r['sourceId']],review)) for r in bundle['entries']),'originalMaterialsIncluded':False}
    else:
        from sczx_business.database import engine,SessionLocal
        if not engine.url.database or not engine.url.database.startswith('sczx_test_'):raise SystemExit('本轮脚本仅允许sczx_test_*隔离库；不迁移或修改正式库。')
        if not args.admin_id:p.error('预览或导入需要现有--admin-id')
        with SessionLocal.begin() as db:result=import_resources(db,args.admin_id,apply=args.apply)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(text)
    print(text)
if __name__=='__main__':main()
