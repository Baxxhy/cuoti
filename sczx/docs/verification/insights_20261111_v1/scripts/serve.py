import os,json,sys
from pathlib import Path
fx=json.loads(Path('/tmp/sczx-step15/browser-private.json').read_text())
os.environ['SCZX_DATABASE_URL']=fx['databaseUrl'];os.environ['SCZX_STORAGE_DIR']='/tmp/sczx-step15/uploads';os.environ['SCZX_COOKIE_SECURE']='false';sys.path.insert(0,str(Path('backend-business').resolve()))
import uvicorn
uvicorn.run('sczx_business.main:app',host='127.0.0.1',port=8015)
