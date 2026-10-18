#!/usr/bin/python3
"""Usage: /usr/bin/python3 cuoti_update_export.py input.docx out.docx out.pdf [port]."""
import sys,time
from pathlib import Path
import uno
from com.sun.star.beans import PropertyValue

def prop(name,value):
 p=PropertyValue();p.Name=name;p.Value=value;return p

def file_url(path):return uno.systemPathToFileUrl(str(Path(path).resolve()))

source,docx_out,pdf_out=sys.argv[1:4]
port=sys.argv[4] if len(sys.argv)>4 else '2004'
local=uno.getComponentContext()
resolver=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
for attempt in range(25):
 try:
  ctx=resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext');break
 except Exception:
  if attempt==24:raise
  time.sleep(.4)
smgr=ctx.ServiceManager
desktop=smgr.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
doc=desktop.loadComponentFromURL(file_url(source),'_blank',0,(prop('Hidden',True),prop('ReadOnly',False),prop('UpdateDocMode',3)))
if doc is None:raise RuntimeError('LibreOffice load returned no document')
try:
 doc.refresh()
 doc.getTextFields().refresh()
 indexes=doc.getDocumentIndexes()
 if indexes.getCount()==0:
  search=doc.createSearchDescriptor();search.SearchString='[[AUTO_TOC]]'
  anchor=doc.findFirst(search)
  if anchor is not None:
   index=doc.createInstance('com.sun.star.text.ContentIndex')
   index.CreateFromOutline=True;index.Level=1;index.Title=''
   doc.Text.insertTextContent(anchor,index,True)
   indexes=doc.getDocumentIndexes()
   print('Created real TOC at [[AUTO_TOC]] marker',flush=True)
 for i in range(indexes.getCount()):indexes.getByIndex(i).update()
 print('Loaded',Path(source).name,'indexes=',indexes.getCount(),flush=True)
 # Repagination and second update ensure index page numbers follow current layout.
 doc.calculateAll() if hasattr(doc,'calculateAll') else None
 doc.refresh()
 for i in range(indexes.getCount()):indexes.getByIndex(i).update()
 doc.storeAsURL(file_url(docx_out),(prop('FilterName','Office Open XML Text'),prop('Overwrite',True)))
 doc.storeToURL(file_url(pdf_out),(prop('FilterName','writer_pdf_Export'),prop('Overwrite',True)))
 print('Saved DOCX',docx_out,'PDF',pdf_out,flush=True)
finally:
 doc.close(True)
