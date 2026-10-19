import uno,json
from pathlib import Path
from com.sun.star.beans import PropertyValue
def prop(k,v):
 p=PropertyValue();p.Name=k;p.Value=v;return p
ctx=uno.getComponentContext();r=ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',ctx);ctx=r.resolve('uno:socket,host=127.0.0.1,port=2007;urp;StarOffice.ComponentContext');d=ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
out=Path('/tmp/cuoti-reference-previews');out.mkdir(exist_ok=True)
for ix,f in enumerate(Path('/root/.codex/attachments/8406691f-086c-429f-af4c-612759c34123').glob('*.docx'),1):
 doc=d.loadComponentFromURL(uno.systemPathToFileUrl(str(f)),'_blank',0,(prop('Hidden',True),prop('ReadOnly',True)))
 try:
  count=doc.CurrentController.PageCount
  for n in [min(4,count),min(7,count)]:
   c=doc.CurrentController.getViewCursor();c.jumpToPage(n);c.jumpToEndOfPage();doc.storeToURL(uno.systemPathToFileUrl(str(out/(str(ix)+'_'+str(n)+'.png'))),(prop('FilterName','writer_png_Export'),prop('Overwrite',True)))
  print(ix,f.name,count,flush=True)
 finally:doc.close(True)
