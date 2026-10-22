#!/usr/bin/python3
"""Render DOCX pages directly to PNG through Writer; no PDF intermediate."""
import uno,json,sys,hashlib
from pathlib import Path
from com.sun.star.beans import PropertyValue
B=Path(__file__).resolve().parent;O=B.parent/'deliverables/插图优化版'

def prop(k,v):
 p=PropertyValue();p.Name=k;p.Value=v;return p
ctx=uno.getComponentContext();resolver=ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',ctx);ctx=resolver.resolve('uno:socket,host=127.0.0.1,port=2007;urp;StarOffice.ComponentContext');desktop=ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
report={}
for f in sorted(O.glob('*_插图优化版.docx')):
 doc=desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(f)),'_blank',0,(prop('Hidden',True),prop('ReadOnly',True)))
 try:
  doc.refresh();count=doc.CurrentController.PageCount;headings=[];items=doc.Text.createEnumeration()
  while items.hasMoreElements():
   item=items.nextElement()
   if item.supportsService('com.sun.star.text.Paragraph') and item.ParaStyleName.startswith('Heading'):
    doc.CurrentController.getViewCursor().gotoRange(item.Start,False);headings.append({'text':item.String,'page':doc.CurrentController.getViewCursor().getPage()})
  indexes=doc.getDocumentIndexes();toc=indexes.getByIndex(0).Anchor.String if indexes.getCount() else ''
  out=B/'word_previews'/f.stem;out.mkdir(parents=True,exist_ok=True)
  for p in out.glob('*.png'):p.unlink()
  for i in range(1,count+1):
   vc=doc.CurrentController.getViewCursor();vc.jumpToPage(i);vc.jumpToEndOfPage()
   assert vc.getPage()==i,(f.name,i,vc.getPage())
   doc.storeToURL(uno.systemPathToFileUrl(str(out/('%02d.png'%i))),(prop('FilterName','writer_png_Export'),prop('Overwrite',True),prop('FilterData',(prop('PageNumber',i),))))
  report[f.name]={'pages':count,'headings':headings,'toc_text':toc,'renderer':'LibreOffice writer_png_Export (direct DOCX → PNG)','pdf_created':False,'preview_font_note':'宿主有SimSun，SimHei缺失时使用系统回退；Word显式指定宋体/黑体','sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
  print(f.name,count,'pages rendered',flush=True)
 finally:doc.close(True)
(B/'word_render_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
