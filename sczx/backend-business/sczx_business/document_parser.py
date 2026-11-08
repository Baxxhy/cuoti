"""原文件解析、逐位置保存和独立OCR排队。"""
import hashlib
from pathlib import Path

from sqlalchemy import select
from .database import SessionLocal
from .library import enqueue, uid
from .models import FileAsset, MaterialUnit, ModelRun, SourceMaterial
from .model_provider import ModelError


def save_unit(material_id, position, label, kind, text, image=None, details=None, needs_ocr=False):
    from .model_jobs import storage_dir
    with SessionLocal.begin() as db:
        old = db.scalar(select(MaterialUnit).where(MaterialUnit.material_id == material_id, MaterialUnit.position == position))
        if old: return
        material = db.get(SourceMaterial, material_id)
        image_id = None
        if image:
            image_id, key = uid('file'), uid('page')
            (storage_dir() / key).write_bytes(image)
            db.add(FileAsset(id=image_id, owner_id=material.owner_id, original_name=label+'.png', content_type='image/png', size=len(image), storage_key=key)); db.flush()
        item = MaterialUnit(id='unit-'+hashlib.sha256(f'{material_id}:{position}'.encode()).hexdigest()[:32], material_id=material_id, position=position, label=label, kind=kind, text=text, original_text=text, image_file_id=image_id, details=details or {})
        db.add(item); db.flush()
        if needs_ocr:
            job = enqueue(db, material.owner_id, 'document_ocr', {'unitId': item.id, 'materialId': material_id}, image_id)
            item.job_id = job.id


def expected_units(material_id, count):
    with SessionLocal.begin() as db:
        material = db.get(SourceMaterial, material_id)
        material.metadata_json = {**material.metadata_json, 'expectedUnits': count}


def parse_material(material_id, run_id=None):
    import pymupdf
    from .model_jobs import storage_dir, phase
    with SessionLocal() as db:
        material = db.get(SourceMaterial, material_id)
        asset = db.get(FileAsset, material.file_id)
        filename, path, job_id = asset.original_name, storage_dir() / asset.storage_key, material.parse_job_id
    def progress(position):
        if job_id: phase(job_id, f'已保存原文位置 {position}')
    try:
        suffix = Path(filename).suffix.lower()
        if suffix == '.pdf':
            with pymupdf.open(path) as document:
                if document.is_encrypted: raise ModelError('PDF需要密码，请上传可直接阅读的原文件。')
                if document.page_count > 30: raise ModelError('PDF最多30页，请拆分后上传。')
                if not document.page_count: raise ModelError('PDF没有页面。')
                expected_units(material_id, document.page_count)
                for index, page in enumerate(document):
                    native = page.get_text('text', sort=True).strip()
                    image_area = sum(pymupdf.Rect(b[:4]).get_area() for b in page.get_text('blocks') if b[6] == 1)
                    scanned = len(native) < 16 or image_area > page.rect.get_area() * .5
                    scale = min(1.5, 1800 / max(page.rect.width, page.rect.height))
                    image = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
                    save_unit(material_id, index+1, f'第 {index+1} 页', 'pdf', '' if scanned else native, image, {'page': index+1, 'method': 'ocr' if scanned else 'text', 'nativeText': native}, scanned)
                    progress(index+1)
        elif suffix == '.docx':
            from docx import Document
            from docx.text.paragraph import Paragraph
            document = Document(path)
            position = paragraph = table = picture = 0
            blocks = list(document.iter_inner_content())
            expected = 0
            for block in blocks:
                element = block._p if isinstance(block, Paragraph) else block._tbl
                text = block.text if isinstance(block, Paragraph) else '\n'.join(cell.text for row in block.rows for cell in row.cells)
                expected += int(bool(text.strip() or element.xpath('.//m:t')))
                expected += sum(bool(b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')) for b in element.xpath('.//a:blip'))
            expected_units(material_id, expected)
            for block in blocks:
                if isinstance(block, Paragraph):
                    paragraph += 1; label = f'段落 {paragraph}'; text = block.text; element = block._p; kind = 'paragraph'
                else:
                    table += 1; label = f'表格 {table}'; text = '\n'.join(' | '.join(c.text for c in row.cells) for row in block.rows); element = block._tbl; kind = 'table'
                formulas = element.xpath('.//m:t')
                warnings = []
                if formulas:
                    text += '\n[公式] ' + ' '.join(t.text or '' for t in formulas)
                    warnings.append('检测到Word公式，此处为公式文字摘录；分式和上下标请对照原件核对。')
                if text.strip():
                    position += 1
                    if position > 300: raise ModelError('DOCX最多300个正文片段，请拆分后上传；已完成片段已保留。')
                    save_unit(material_id, position, label, kind, text.strip(), details={'paragraph': paragraph, 'table': table, 'warnings': warnings})
                    progress(position)
                for blip in element.xpath('.//a:blip'):
                    embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if not embed: continue
                    part = document.part.related_parts.get(embed)
                    if not part: continue
                    picture += 1; position += 1
                    if position > 300: raise ModelError('DOCX最多300个片段，请拆分后上传。')
                    with pymupdf.open(stream=part.blob) as image_doc:
                        pdf = image_doc.convert_to_pdf()
                    with pymupdf.open(stream=pdf, filetype='pdf') as rendered:
                        image = rendered[0].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3), alpha=False).tobytes('png')
                    save_unit(material_id, position, f'{label} · 插图 {picture}', 'image', '', image, {'paragraph': paragraph, 'table': table}, True)
                    progress(position)
            if not position: raise ModelError('文档没有可读取的正文、表格或插图。')
        else:
            expected_units(material_id, 1)
            with pymupdf.open(path) as image_doc: pdf = image_doc.convert_to_pdf()
            with pymupdf.open(stream=pdf, filetype='pdf') as document:
                page = document[0]; scale = min(1.5, 1800/max(page.rect.width,page.rect.height))
                image = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale), alpha=False).tobytes('png')
            save_unit(material_id, 1, '原始图片', 'image', '', image, {}, True)
            progress(1)
    except ModelError: raise
    except Exception:
        raise ModelError('原文件无法完成解析，请检查文件是否可打开；已完成的位置已保留。') from None
    with SessionLocal() as db:
        total = len(db.scalars(select(MaterialUnit.id).where(MaterialUnit.material_id == material_id)).all())
    return {'materialId': material_id, 'unitCount': total, 'message': '原文位置已保存，图片识别按位置独立执行。'}
