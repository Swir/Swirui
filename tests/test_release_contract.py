import io
import runpy
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = runpy.run_path(str(ROOT / "tools/release_contract.py"))


def test_release_tag_must_match_all_three_version_sources(tmp_path):
    for name in ("pyproject.toml", "native/Cargo.toml", "src/swirui/__init__.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    version = CONTRACT["metadata"](tmp_path)
    assert CONTRACT["metadata"](tmp_path, release_tag=f"v{version}") == version
    with pytest.raises(AssertionError, match="tag"):
        CONTRACT["metadata"](tmp_path, release_tag="v9.9.9")
    init = tmp_path / "src/swirui/__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace(
        f'__version__ = "{version}"', '__version__ = "9.9.9"'), encoding="utf-8")
    with pytest.raises(AssertionError, match="Public API"):
        CONTRACT["metadata"](tmp_path)


def payload(directory, *, native_source=b"same", extension=True):
    for suffix, source in (("py3-none-any", b"same"), ("cp311-abi3-win_amd64", native_source)):
        with zipfile.ZipFile(directory / f"swirui-1.2.3-{suffix}.whl", "w") as archive:
            archive.writestr("swirui/__init__.py", source)
            if suffix != "py3-none-any" and extension:
                archive.writestr("swirui/_swirui_native.pyd", b"test payload")
    with tarfile.open(directory / "swirui-1.2.3.tar.gz", "w:gz") as archive:
        for name in ("src/swirui/__init__.py", "native/Cargo.lock",
                     "native/src/lib.rs", "README.md"):
            member = tarfile.TarInfo(f"swirui-1.2.3/{name}")
            member.size = 4
            archive.addfile(member, io.BytesIO(b"same"))


def test_release_contract_rejects_mismatched_wheel_sources(tmp_path):
    payload(tmp_path, native_source=b"different")
    with pytest.raises(AssertionError, match="source differs"):
        CONTRACT["artifacts"](tmp_path, "1.2.3")


def test_release_contract_rejects_missing_native_extension(tmp_path):
    payload(tmp_path, extension=False)
    with pytest.raises(AssertionError, match="extension missing"):
        CONTRACT["artifacts"](tmp_path, "1.2.3")


def test_release_contract_hashes_exact_payload_and_rejects_extra_files(tmp_path):
    payload(tmp_path)
    assert len(CONTRACT["artifacts"](tmp_path, "1.2.3")) == 3
    (tmp_path / "unexpected.whl").write_bytes(b"extra")
    with pytest.raises(AssertionError, match="Unexpected"):
        CONTRACT["artifacts"](tmp_path, "1.2.3")
