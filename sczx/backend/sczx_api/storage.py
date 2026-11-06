"""Independent media root with no-follow file access."""
import os
import stat
from pathlib import Path

from fastapi import HTTPException


def root():
    return Path(os.environ.get('SCZX_MEDIA_ROOT', 'media')).absolute()


def parts(path):
    if not path or path.startswith('/') or '\\' in path or '\x00' in path or any(p in ['', '.', '..'] for p in path.split('/')):
        raise HTTPException(404, '资源不存在')
    return path.split('/')


def read_media(path):
    components = parts(path)
    fd = None
    try:
        fd = os.open(root(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in components[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        file_fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode): raise OSError
            return file.read()
    except OSError:
        raise HTTPException(404, '资源不存在') from None
    finally:
        if fd is not None: os.close(fd)


def write_media(path, data):
    parts(path)
    target = root() / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as file:
        file.write(data)


def remove_media(path):
    parts(path)
    (root() / path).unlink(missing_ok=True)
