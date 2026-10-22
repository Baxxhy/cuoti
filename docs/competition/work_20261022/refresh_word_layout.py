#!/usr/bin/python3
import uno
from pathlib import Path
from com.sun.star.beans import PropertyValue
B=Path(__file__).resolve().parent;O=B.parent/'deliverables'
def p(k,v):
 x=PropertyValue();x.Name=k;x.Value=v;return x
c=uno.getComponentContext();c=c.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',c).resolve('uno:socket,host=127.0.0.1,port=2007;urp;StarOffice.ComponentContext');desk=c.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',c)
for f in sorted(O.glob('*_重写终稿.docx')):
 d=desk.loadComponentFromURL(uno.systemPathToFileUrl(str(f)),'_blank',0,(p('Hidden',True),p('ReadOnly',False)))
 try:
  d.refresh();v=d.CurrentController.getViewCursor();v.jumpToLastPage()
  for _ in range(2):
   for i in range(d.getDocumentIndexes().getCount()):d.getDocumentIndexes().getByIndex(i).update()
   d.refresh();v.jumpToLastPage()
  d.storeAsURL(uno.systemPathToFileUrl(str(f)),(p('FilterName','Office Open XML Text'),p('Overwrite',True)))
  print(f.name,d.CurrentController.PageCount,flush=True)
 finally:d.close(True)
