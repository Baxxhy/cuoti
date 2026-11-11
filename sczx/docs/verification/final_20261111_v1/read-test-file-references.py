import json
from pathlib import Path
from sqlalchemy import create_engine,text
out=Path('/tmp/sczx-step20');p=out/'storage-audit.json';r=json.loads(p.read_text());e=create_engine('mysql+pymysql://root@127.0.0.1:23317/sczx');counts={}
with e.connect() as c:
 for key in r['addedDigests']:counts[key]=c.execute(text('SELECT COUNT(*) FROM file_assets WHERE storage_key=:k'),{'k':key}).scalar()
e.dispose();assert all(n==0 for n in counts.values());r.update(formalReferenceCounts=counts,filesMoved=False,filesDeleted=False,pendingUserApproval=True);p.write_text(json.dumps(r,indent=2));print('6 test uploads have0 formal file_assets references; all remain in place')
