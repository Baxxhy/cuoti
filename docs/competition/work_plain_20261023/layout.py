#!/usr/bin/python3
"""Update Word TOC, paginate, and optionally render DOCX directly to PNG."""
from pathlib import Path
import sys,json,time,hashlib,shutil
import uno
from com.sun.star.beans import PropertyValue
B=Path(__file__).resolve().parent
def prop(k,v):
 p=PropertyValue();p.Name=k;p.Value=v;return p
def url(p):return uno.systemPathToFileUrl(str(Path(p).resolve()))
ctx=uno.getComponentContext();resolver=ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',ctx)
ctx=resolver.resolve('uno:socket,host=127.0.0.1,port=2012;urp;StarOffice.ComponentContext')
desk=ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
report={}; render='--render' in sys.argv; readonly='--readonly' in sys.argv
for item in json.loads((B/'build_manifest.json').read_text()):
 src=Path(item['final'] if readonly or '--update-final' in sys.argv else item['raw']);out=Path(item['final'])
 temp=Path('/tmp/cuoti-plain-input');temp.mkdir(exist_ok=True)
 ascii_src=temp/(item['key']+'-input.docx');ascii_out=temp/(item['key']+'-output.docx')
 shutil.copy2(src,ascii_src)
 d=desk.loadComponentFromURL(url(ascii_src),'_blank',0,(prop('Hidden',True),prop('ReadOnly',readonly),prop('UpdateDocMode',3)))
 if not d:raise RuntimeError('Cannot open '+str(src))
 try:
  if not readonly:
   if not d.getDocumentIndexes().getCount():
    search=d.createSearchDescriptor();search.SearchString='[[AUTO_TOC]]';anchor=d.findFirst(search)
    idx=d.createInstance('com.sun.star.text.ContentIndex');idx.CreateFromOutline=True;idx.Level=2;idx.Title='';d.Text.insertTextContent(anchor,idx,True)
   families=d.getStyleFamilies()
   for family in ['CharacterStyles','ParagraphStyles']:
    for n in families[family].getElementNames():
     s=families[family][n]
     if s.getPropertySetInfo().hasPropertyByName('CharColor'):s.CharColor=0
   ps=families['ParagraphStyles']
   for n in ps.getElementNames():
    if n in ['Contents 1','Contents 2']:
     st=ps[n];st.CharFontName='SimSun';st.CharFontNameAsian='SimSun';st.CharHeight=12;st.CharHeightAsian=12;st.ParaTopMargin=0;st.ParaBottomMargin=20;st.NumberingStyleName=''
     spacing=uno.createUnoStruct('com.sun.star.style.LineSpacing');spacing.Mode=3;spacing.Height=635;st.ParaLineSpacing=spacing;st.ParaKeepTogether=False
   for _ in range(3):
    d.refresh();d.CurrentController.getViewCursor().jumpToLastPage()
    for i in range(d.getDocumentIndexes().getCount()):d.getDocumentIndexes().getByIndex(i).update()
   for i in range(d.getDocumentIndexes().getCount()):
    idx=d.getDocumentIndexes().getByIndex(i);cur=d.Text.createTextCursorByRange(idx.Anchor.Start);cur.gotoRange(idx.Anchor.End,True);cur.NumberingStyleName='';cur.CharColor=0
   d.storeAsURL(url(ascii_out),(prop('FilterName','Office Open XML Text'),prop('Overwrite',True)))
   shutil.copy2(ascii_out,out)
  d.refresh();d.CurrentController.getViewCursor().jumpToLastPage();count=d.CurrentController.PageCount
  headings=[];paras=[];enum=d.Text.createEnumeration();vc=d.CurrentController.getViewCursor()
  while enum.hasMoreElements():
   e=enum.nextElement()
   if e.supportsService('com.sun.star.text.Paragraph'):
    vc.gotoRange(e.Start,False);page=vc.getPage();txt=e.String
    paras.append({'text':txt,'style':e.ParaStyleName,'page':page})
    if e.ParaStyleName.startswith('Heading'):headings.append({'text':txt,'page':page,'style':e.ParaStyleName})
  toc=d.getDocumentIndexes().getByIndex(0).Anchor.String
  if render:
   target=B/'word_previews'/item['key'];target.mkdir(parents=True,exist_ok=True)
   for old in target.glob('*.png'):old.unlink()
   for i in range(1,count+1):
    vc.jumpToPage(i);vc.jumpToEndOfPage();assert vc.getPage()==i
    png=temp/(item['key']+f'-{i:02d}.png')
    d.storeToURL(url(png),(prop('FilterName','writer_png_Export'),prop('Overwrite',True),prop('FilterData',(prop('PageNumber',i),))))
    shutil.move(png,target/f'{i:02d}.png')
  report[item['key']]={'file':str(out),'pages':count,'headings':headings,'toc':toc,'paragraph_pages':paras,'rendered':render,'pdf_created':False,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
  print(item['key'],count,'pages',len(headings),'headings',flush=True)
 finally:d.close(True)
(B/('render_audit.json' if render else 'layout_audit.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
