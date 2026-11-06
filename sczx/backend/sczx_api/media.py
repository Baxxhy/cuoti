import os
import stat

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from .accounts import secret
from .security import signature, valid_media
from .storage import parts, root


def open_media(path, media_root=None):
    components = parts(path)
    fd = None
    try:
        fd = os.open(media_root if media_root is not None else root(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for index, part in enumerate(components):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(components) - 1: flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd); fd = child
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode): raise OSError
        file = os.fdopen(fd, 'rb'); fd = None
        return file, info
    except OSError:
        raise HTTPException(404, '资源不存在') from None
    finally:
        if fd is not None: os.close(fd)


def media_range(header, length):
    try:
        if not header.startswith('bytes=') or not length: raise ValueError
        start, end = header[6:].split('-', 1)
        if not start:
            count = min(int(end), length)
            if count <= 0: raise ValueError
            return length - count, count
        start = int(start); end = int(end) if end else length - 1
        if start < 0 or start >= length or end < start: raise ValueError
        end = min(end, length - 1)
        return start, end - start + 1
    except (ValueError, TypeError):
        raise HTTPException(416, '范围无效') from None


_TYPES = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp', '.bmp':'image/bmp', '.tif':'image/tiff', '.gif':'image/gif', '.svg':'image/svg+xml', '.mp3':'audio/mpeg', '.wav':'audio/wav', '.webm':'audio/webm', '.m4a':'audio/mp4', '.ogg':'audio/ogg', '.mp4':'video/mp4', '.pdf':'application/pdf', '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.zip':'application/zip', '.json':'application/json', '.txt':'text/plain; charset=utf-8'}


async def serve_media(request, storage_root=None, storage_path=None):
    if not valid_media(request.url.path, request.query_params.get('expires'), request.query_params.get('signature'), secret()):
        raise HTTPException(403, '资源链接已失效，请返回页面刷新')
    path = storage_path if storage_path is not None else request.url.path[1:]
    file, info = open_media(path, storage_root)
    etag = '"' + signature('media-etag-v1', f'{path}:{info.st_size}:{info.st_mtime_ns}:{info.st_ino}').hex() + '"'
    content_type = next((value for suffix, value in _TYPES.items() if path.lower().endswith(suffix)), 'application/octet-stream')
    headers = {'ETag': etag, 'Accept-Ranges':'bytes', 'Cache-Control':'private, max-age=0, must-revalidate', 'X-Content-Type-Options':'nosniff', 'Content-Type': content_type}
    if any(tag.strip() in ['*', etag, 'W/' + etag] for tag in request.headers.get('if-none-match', '').split(',')):
        file.close(); return Response(status_code=304, headers=headers)
    if request.method == 'HEAD':
        file.close(); return Response(headers={**headers, 'Content-Length': str(info.st_size)})
    start, count, status = 0, info.st_size, 200
    header = request.headers.get('range', '')
    if header and ',' not in header and request.headers.get('if-range', etag) == etag:
        try: start, count = media_range(header, info.st_size)
        except HTTPException:
            file.close()
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': '范围无效'}, status_code=416, headers={**headers, 'Content-Range': f'bytes */{info.st_size}'})
        status = 206; headers['Content-Range'] = f'bytes {start}-{start+count-1}/{info.st_size}'
    def stream():
        try:
            file.seek(start); remaining = count
            while remaining:
                chunk = file.read(min(65536, remaining))
                if not chunk: raise OSError('media read interrupted')
                remaining -= len(chunk)
                yield chunk
        finally: file.close()
    return StreamingResponse(stream(), status_code=status, headers=headers)
