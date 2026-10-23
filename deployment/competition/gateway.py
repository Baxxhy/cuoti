"""Same-origin gateway for the packaged H5 site and the native business API."""
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Request
from starlette.responses import Response,FileResponse
from starlette.staticfiles import StaticFiles
ROOT=Path('/opt/app/web')
@asynccontextmanager
async def lifespan(app):
 async with httpx.AsyncClient(timeout=300,trust_env=False) as client:
  app.state.client=client
  yield
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
@app.api_route('/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'])
async def route(path:str,request:Request):
 if path.startswith(('api/','uploads/','reports/')) or path in ('livez','readyz'):
  hop={'host','connection','transfer-encoding','content-length','accept-encoding'}
  headers={k:v for k,v in request.headers.items() if k.lower() not in hop}
  try:
   result=await request.app.state.client.request(request.method,'http://127.0.0.1:8002/'+path,params=request.query_params,headers=headers,content=await request.body())
  except httpx.HTTPError:return Response('服务暂未就绪',status_code=503)
  return Response(result.content,result.status_code,{k:v for k,v in result.headers.items() if k.lower() not in hop and k.lower()!='content-encoding'})
 target=(ROOT/path).resolve()
 if not target.is_relative_to(ROOT):return Response(status_code=403)
 if target.is_file():return FileResponse(target)
 return FileResponse(ROOT/'index.html')
