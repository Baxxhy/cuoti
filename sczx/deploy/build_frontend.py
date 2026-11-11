#!/usr/bin/env python3
"""Build and record input hashes; usable for current or previous compatible source."""
import argparse,hashlib,json,subprocess,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',default=str(Path(__file__).resolve().parents[1]));a=p.parse_args();root=Path(a.source).resolve()
subprocess.run(['npm','--prefix',str(root/'frontend'),'run','build'],env={**os.environ,'VITE_API_BASE':''},check=True)
files=[x for x in (root/'frontend/src').rglob('*') if x.is_file()]+[root/'frontend'/x for x in ['package.json','package-lock.json','vite.config.js']]
data={'schema':1,'sources':{str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(files)}}
(root/'frontend/dist/build-info.json').write_text(json.dumps(data,indent=2)+'\n')
print('frontend build inputs recorded; no private runtime configuration included')
