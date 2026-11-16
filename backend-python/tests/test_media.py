import pytest
from cuoti_backend.media import MediaStore, range_values
from cuoti_backend.protocol import ApiError


def test_store_rejects_symlinks_and_overwrites(tmp_path):
    store = MediaStore(tmp_path, "test-secret-" * 4)
    store.write("uploads/one/file.txt", b"original")
    with pytest.raises(ApiError):
        store.write("uploads/one/file.txt", b"overwrite")
    assert store.read("uploads/one/file.txt") == b"original"
    for path in [
        "/etc/passwd",
        "uploads/../file",
        "uploads//file",
        "uploads/a\\b",
        "uploads/./file",
    ]:
        with pytest.raises(ApiError):
            store.read(path)
    (tmp_path / "uploads/link").symlink_to(
        tmp_path / "uploads/one", target_is_directory=True
    )
    with pytest.raises(ApiError):
        store.read("uploads/link/file.txt")
    (tmp_path / "uploads/one/symlink").symlink_to(tmp_path / "uploads/one/file.txt")
    with pytest.raises(ApiError):
        store.read("uploads/one/symlink")


def test_range_cases():
    assert range_values("bytes=-3", 10) == (7, 3)
    assert range_values("bytes=2-", 10) == (2, 8)
    assert range_values("bytes=2-99", 10) == (2, 8)
    for header in ["bytes=-0", "bytes=20-30", "bytes=4-2", "invalid"]:
        with pytest.raises(ApiError):
            range_values(header, 10)
