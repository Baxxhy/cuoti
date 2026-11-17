import hmac
import mimetypes
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from .protocol import ApiError
from .security import signature

router = APIRouter()


class MediaStore:
    def __init__(self, root, secret):
        self.root = Path(root)
        self.secret = secret

    @contextmanager
    def parent(self, path, create=False):
        parts = path.split("/")
        if (
            any(part in ["", ".", ".."] for part in parts)
            or "\\" in path
            or "\0" in path
        ):
            raise ApiError(404, "资源不存在")
        if create:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def open(self, path):
        try:
            with self.parent(path) as (parent, leaf):
                fd = os.open(
                    leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                )
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise ApiError(404, "资源不存在")
            return fd
        except OSError:
            raise ApiError(404, "资源不存在") from None

    def read(self, path):
        with os.fdopen(self.open(path), "rb") as file:
            if not 0 < os.fstat(file.fileno()).st_size <= 64 * 1024 * 1024:
                raise ApiError(422, "图片文件大小无效")
            return file.read()

    def write(self, path, data):
        try:
            with self.parent(path, create=True) as (parent, leaf):
                fd = os.open(
                    leaf,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                try:
                    with os.fdopen(fd, "wb") as file:
                        file.write(data)
                        file.flush()
                        os.fsync(file.fileno())
                except BaseException:
                    os.unlink(leaf, dir_fd=parent)
                    raise
        except OSError:
            raise ApiError(503, "资源保存失败") from None

    def remove(self, path):
        try:
            with self.parent(path) as (parent, leaf):
                os.unlink(leaf, dir_fd=parent)
        except FileNotFoundError:
            pass

    def url(self, path):
        if not path.startswith(
            ("/uploads/", "/reports/", "/api/v1/practice/questions/")
        ):
            return path
        expires = int(time.time()) + 14400
        tag = signature(self.secret, f"media:v1:{expires}:{path}").hex()
        return quote(path, safe="/~") + f"?expires={expires}&signature={tag}"

    def valid(self, path, expires, supplied):
        try:
            expires = int(expires)
            if (
                not int(time.time()) < expires <= int(time.time()) + 14400
                or len(self.secret.encode()) < 32
            ):
                return False
            expected = signature(self.secret, f"media:v1:{expires}:{path}").hex()
            return hmac.compare_digest(expected.encode(), supplied.encode())
        except (ValueError, TypeError, UnicodeError):
            return False


def range_values(header, length):
    try:
        if not header.startswith("bytes=") or length == 0:
            raise ValueError
        first, last = header[6:].split("-", 1)
        if not first:
            suffix = int(last)
            if suffix <= 0:
                raise ValueError
            start = max(0, length - suffix)
            return start, length - start
        start = int(first)
        end = min(length - 1, int(last)) if last else length - 1
        if start < 0 or start >= length or end < start:
            raise ValueError
        return start, end - start + 1
    except (ValueError, TypeError):
        raise ApiError(416, "范围无效") from None


@router.get("/uploads/{path:path}")
@router.head("/uploads/{path:path}")
@router.get("/reports/{path:path}")
@router.head("/reports/{path:path}")
def serve_media(request: Request, path: str):
    store = request.app.state.media
    full_path = request.url.path
    if not store.valid(
        full_path,
        request.query_params.get("expires"),
        request.query_params.get("signature", ""),
    ):
        raise ApiError(403, "资源链接已失效，请返回页面刷新")
    if request.headers.get("authorization"):
        from .accounts import current_user
        from .question_data import rows

        with request.app.state.database.session() as db, db.begin():
            user = current_user(request, db)
            matches = rows(
                db,
                "SELECT a.id FROM question_assets a JOIN questions q ON a.question_id=q.id WHERE a.path=? AND q.user_id=? LIMIT 1",
                [full_path[1:], user.id],
            )
            if full_path.startswith("/reports/"):
                matches = rows(
                    db,
                    "SELECT e.id FROM export_jobs e JOIN papers p ON e.paper_id=p.id WHERE e.path=? AND p.user_id=? LIMIT 1",
                    [full_path[1:], user.id],
                )
            if not matches and not full_path.startswith(
                "/uploads/answers/" + user.id + "/"
            ):
                raise ApiError(404, "资源不存在或无权访问")
    return file_response(request, store, full_path[1:])


def file_response(request, store, path):
    full_path = request.url.path
    fd = store.open(path)
    info = os.fstat(fd)
    length = info.st_size
    etag_data = f"{full_path[1:]}:{length}:{info.st_mtime_ns}:{info.st_ino}"
    etag = '"' + signature("media-etag-v1", etag_data).hex() + '"'
    headers = {
        "ETag": etag,
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0, must-revalidate",
        "X-Content-Type-Options": "nosniff",
        "Content-Type": mimetypes.guess_type(path)[0] or "application/octet-stream",
    }
    tags = [tag.strip() for tag in request.headers.get("if-none-match", "").split(",")]
    if any(tag in ["*", etag, "W/" + etag] for tag in tags):
        os.close(fd)
        return Response(status_code=304, headers=headers)
    if request.method == "HEAD":
        os.close(fd)
        return Response(headers={**headers, "Content-Length": str(length)})
    offset, count, status = 0, length, 200
    header = request.headers.get("range", "")
    if header and "," not in header and request.headers.get("if-range", etag) == etag:
        try:
            offset, count = range_values(header, length)
        except ApiError:
            os.close(fd)
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"detail": "范围无效"},
                status_code=416,
                headers={
                    **headers,
                    "Content-Type": "application/json",
                    "Content-Range": f"bytes */{length}",
                },
            )
        status = 206
        headers["Content-Range"] = f"bytes {offset}-{offset + count - 1}/{length}"
    file = os.fdopen(fd, "rb")

    def chunks():
        remaining, start = count, offset
        try:
            while remaining:
                data = os.pread(file.fileno(), min(65536, remaining), start)
                if not data:
                    raise OSError("file truncated")
                yield data
                remaining -= len(data)
                start += len(data)
        finally:
            file.close()

    # Ensure descriptor closes even if a client disconnects before iteration.
    from starlette.background import BackgroundTask

    return StreamingResponse(
        chunks(),
        status_code=status,
        headers=headers,
        background=BackgroundTask(file.close),
    )
