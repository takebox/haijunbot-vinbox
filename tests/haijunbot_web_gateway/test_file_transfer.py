# -*- coding: utf-8 -*-
"""Unit tests for the node file direct transfer (file-transfer) endpoint.

Covers:
1. Path normalization: absolute paths re-rooted, relative paths, .. traversal rejection;
2. Upload chunks: single chunk write, multi-chunk concatenation correctness, offset out-of-bounds;
3. Download chunks: offset/length chunked reading, eof determination, directory tar packing.

Tests directly call _node_http_dispatcher registered to node_connection_manager
inside create_app(), thus exercising the real /file-transfer/* dispatch logic.
"""

import base64
import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

os.environ.setdefault("HAIJUNBOT_SKIP_INTERACTIVE_CONFIG", "1")


@pytest.fixture()
def dispatcher(monkeypatch, tmp_path):
    """Construct a dispatcher with the transfers root directory pointing to a temp directory.

    Monkeypatches get_data_dir so that ~/.haijunbot resolves to tmp_path,
    avoiding polluting the real user directory.
    """
    import haijunbot.haijunbot_utils.config as config_mod

    monkeypatch.setattr(config_mod, "get_data_dir", lambda: str(tmp_path))

    from haijunbot.haijunbot_web_gateway.app import create_app

    app = create_app()
    # create_app injects the dispatcher into app.state.node_connection_manager
    manager = app.state.node_connection_manager
    disp = manager._node_http_dispatcher
    assert disp is not None
    return disp, tmp_path


def _call(disp, path: str, payload: dict):
    import asyncio
    import json

    async def _inner():
        return await disp(
            method="POST",
            path=path,
            query="",
            headers={"content-type": "application/json"},
            body=json.dumps(payload),
            user_info=None,
            trusted_proxy=True,
        )

    return asyncio.new_event_loop().run_until_complete(_inner())


def _body(result: dict) -> dict:
    import json

    return json.loads(result["body"])


# ----------------------------------------------------------------------
# Path normalization
# ----------------------------------------------------------------------
def test_absolute_path_is_re_rooted_under_transfers(dispatcher):
    """Absolute path /tmp/x.txt should resolve to <data_dir>/transfers/tmp/x.txt."""
    disp, tmp_path = dispatcher
    data = base64.b64encode(b"hello").decode()
    result = _call(
        disp,
        "/file-transfer/upload",
        {"path": "/tmp/x.txt", "data": data, "offset": 0, "truncate": True},
    )
    body = _body(result)
    assert body["success"] is True
    expected = tmp_path / "transfers" / "tmp" / "x.txt"
    assert expected.exists()
    assert expected.read_bytes() == b"hello"
    assert body["data"]["path"] == str(expected)


def test_relative_path_is_directly_joined(dispatcher):
    """Relative path a/b.txt should resolve to <data_dir>/transfers/a/b.txt."""
    disp, tmp_path = dispatcher
    data = base64.b64encode(b"rel").decode()
    result = _call(
        disp,
        "/file-transfer/upload",
        {"path": "a/b.txt", "data": data, "offset": 0, "truncate": True},
    )
    body = _body(result)
    assert body["success"] is True
    expected = tmp_path / "transfers" / "a" / "b.txt"
    assert expected.read_bytes() == b"rel"


@pytest.mark.parametrize(
    "evil",
    ["../../etc/passwd", "/../../etc/passwd", "a/../../../etc/passwd"],
)
def test_path_traversal_is_rejected(dispatcher, evil):
    """Any path escaping the transfers root must be rejected."""
    disp, _ = dispatcher
    data = base64.b64encode(b"x").decode()
    result = _call(
        disp,
        "/file-transfer/upload",
        {"path": evil, "data": data, "offset": 0, "truncate": True},
    )
    body = _body(result)
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_PATH"


# ----------------------------------------------------------------------
# Upload chunks
# ----------------------------------------------------------------------
def test_upload_multiple_chunks_concatenate(dispatcher):
    """Multiple chunks concatenated by offset should match the source content."""
    disp, tmp_path = dispatcher
    part1 = b"A" * 100
    part2 = b"B" * 50
    r1 = _call(
        disp,
        "/file-transfer/upload",
        {
            "path": "multi.bin",
            "data": base64.b64encode(part1).decode(),
            "offset": 0,
            "truncate": True,
        },
    )
    assert _body(r1)["success"] is True
    r2 = _call(
        disp,
        "/file-transfer/upload",
        {
            "path": "multi.bin",
            "data": base64.b64encode(part2).decode(),
            "offset": len(part1),
            "truncate": False,
        },
    )
    assert _body(r2)["success"] is True
    expected = tmp_path / "transfers" / "multi.bin"
    assert expected.read_bytes() == part1 + part2


def test_upload_chunk_sha256_returned(dispatcher):
    """The returned sha256 should match the chunk."""
    disp, _ = dispatcher
    chunk = b"hash-me"
    result = _call(
        disp,
        "/file-transfer/upload",
        {
            "path": "h.bin",
            "data": base64.b64encode(chunk).decode(),
            "offset": 0,
            "truncate": True,
        },
    )
    body = _body(result)
    assert body["data"]["sha256"] == hashlib.sha256(chunk).hexdigest()


# ----------------------------------------------------------------------
# Download chunks
# ----------------------------------------------------------------------
def test_download_chunks_and_eof(dispatcher):
    """Download should chunk by offset/length, with the last chunk having eof=True."""
    disp, tmp_path = dispatcher
    content = b"0123456789"
    target = tmp_path / "transfers" / "d.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    r1 = _call(
        disp,
        "/file-transfer/download",
        {"path": "d.bin", "offset": 0, "length": 4},
    )
    b1 = _body(r1)
    assert b1["success"] is True
    assert base64.b64decode(b1["data"]["data"]) == b"0123"
    assert b1["data"]["eof"] is False
    assert b1["data"]["size"] == 10

    r2 = _call(
        disp,
        "/file-transfer/download",
        {"path": "d.bin", "offset": 8, "length": 4},
    )
    b2 = _body(r2)
    assert base64.b64decode(b2["data"]["data"]) == b"89"
    assert b2["data"]["eof"] is True


def test_download_offset_beyond_eof_returns_empty(dispatcher):
    """When offset is out of bounds, an empty chunk should be returned with eof=True."""
    disp, tmp_path = dispatcher
    target = tmp_path / "transfers" / "e.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"abc")
    result = _call(
        disp,
        "/file-transfer/download",
        {"path": "e.bin", "offset": 100, "length": 10},
    )
    body = _body(result)
    assert body["success"] is True
    assert base64.b64decode(body["data"]["data"]) == b""
    assert body["data"]["eof"] is True


def test_download_directory_packs_tar(dispatcher):
    """When mode=dir, the directory should be packed as tar and returned."""
    import io
    import tarfile

    disp, tmp_path = dispatcher
    src = tmp_path / "transfers" / "mydir"
    src.mkdir(parents=True, exist_ok=True)
    (src / "inner.txt").write_bytes(b"inner-content")

    result = _call(
        disp,
        "/file-transfer/download",
        {"path": "mydir", "offset": 0, "length": 8 * 1024 * 1024, "mode": "dir"},
    )
    body = _body(result)
    assert body["success"] is True
    tar_bytes = base64.b64decode(body["data"]["data"])
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        names = tar.getnames()
    assert any(n.endswith("inner.txt") for n in names)


def test_upload_directory_unpacks_tar(dispatcher):
    """When mode=dir and final=True, the tar should be unpacked to the target directory."""
    import io
    import tarfile

    disp, tmp_path = dispatcher
    # Construct a tar containing a single file
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name="packed/hello.txt")
        payload = b"packed-content"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    tar_bytes = buf.getvalue()

    result = _call(
        disp,
        "/file-transfer/upload",
        {
            "path": "unpacked",
            "data": base64.b64encode(tar_bytes).decode(),
            "offset": 0,
            "mode": "dir",
            "truncate": True,
            "final": True,
        },
    )
    body = _body(result)
    assert body["success"] is True
    assert (
        tmp_path / "transfers" / "unpacked" / "packed" / "hello.txt"
    ).read_bytes() == b"packed-content"


def test_unknown_transfer_path_returns_404(dispatcher):
    """An unknown file-transfer sub-path should return 404."""
    disp, _ = dispatcher
    result = _call(disp, "/file-transfer/unknown", {})
    assert result["status_code"] == 404


def test_upload_truncate_with_nonzero_offset_writes_at_offset(dispatcher):
    """When truncate=True and offset>0, data should be written at the offset, not at the beginning of the file."""
    disp, tmp_path = dispatcher
    result = _call(
        disp,
        "/file-transfer/upload",
        {
            "path": "trunc.bin",
            "data": base64.b64encode(b"XYZ").decode(),
            "offset": 4,
            "truncate": True,
        },
    )
    assert _body(result)["success"] is True
    expected = tmp_path / "transfers" / "trunc.bin"
    # Before offset=4 is filled with null bytes (\x00)
    assert expected.read_bytes() == b"\x00\x00\x00\x00XYZ"


def test_download_directory_packs_once_and_cleans_tar(dispatcher):
    """Multi-chunk download in dir mode: tar is packed only once (cache reused), and the temporary tar is cleaned up after reading."""
    import io
    import tarfile

    disp, tmp_path = dispatcher
    src = tmp_path / "transfers" / "bigdir"
    src.mkdir(parents=True, exist_ok=True)
    (src / "a.txt").write_bytes(b"A" * 200)
    (src / "b.txt").write_bytes(b"B" * 200)

    tar_path = tmp_path / "transfers" / "bigdir.outgoing.tar"

    # First chunk: small length, definitely eof=False, tar should be retained
    r1 = _call(
        disp,
        "/file-transfer/download",
        {"path": "bigdir", "offset": 0, "length": 64, "mode": "dir"},
    )
    b1 = _body(r1)
    assert b1["success"] is True
    assert b1["data"]["eof"] is False
    assert tar_path.exists(), "Temporary tar should be retained for reuse when chunks are not fully read"
    first_mtime = tar_path.stat().st_mtime_ns
    total = b1["data"]["size"]

    # Second chunk: continue reading, cache hit (mtime unchanged, not re-packed)
    r2 = _call(
        disp,
        "/file-transfer/download",
        {"path": "bigdir", "offset": 64, "length": 64, "mode": "dir"},
    )
    b2 = _body(r2)
    assert b2["success"] is True
    assert tar_path.stat().st_mtime_ns == first_mtime, "Should not re-pack on cache hit"
    assert b2["data"]["size"] == total

    # Read to the last chunk: eof=True, temporary tar should be cleaned up
    r3 = _call(
        disp,
        "/file-transfer/download",
        {"path": "bigdir", "offset": total - 1, "length": 64, "mode": "dir"},
    )
    b3 = _body(r3)
    assert b3["success"] is True
    assert b3["data"]["eof"] is True
    assert not tar_path.exists(), "Temporary tar should be deleted after reading"

    # After cleanup, requesting again should re-pack and succeed (cache invalidated, no residue)
    r4 = _call(
        disp,
        "/file-transfer/download",
        {"path": "bigdir", "offset": 0, "length": 8 * 1024 * 1024, "mode": "dir"},
    )
    b4 = _body(r4)
    assert b4["success"] is True
    tar_bytes = base64.b64decode(b4["data"]["data"])
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        names = tar.getnames()
    assert any(n.endswith("a.txt") for n in names)
    assert any(n.endswith("b.txt") for n in names)
