"""Validate release identity and the exact portable/native/sdist payload."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tarfile
import tomllib
import zipfile
from pathlib import Path

from packaging.version import Version


def metadata(root: Path, *, release_tag: str | None = None) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    native = tomllib.loads((root / "native/Cargo.toml").read_text(encoding="utf-8"))
    assert project["project"]["name"] == "swirui", "Unexpected package name"
    version = project["project"]["version"]
    parsed = Version(version)
    assert str(parsed) == version and parsed.local is None, "Use a canonical public version"
    assert Version(native["package"]["version"]) == parsed, "Python/Rust versions differ"
    module = ast.parse((root / "src/swirui/__init__.py").read_text(encoding="utf-8"))
    versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    ]
    assert versions == [version], "Public API version differs from package metadata"
    assert project["project"]["requires-python"] == ">=3.11"
    maturin = project["tool"]["maturin"]
    assert maturin["module-name"] == "swirui._swirui_native"
    assert maturin["manifest-path"] == "native/Cargo.toml"
    assert maturin["python-source"] == "src" and maturin["bindings"] == "pyo3"
    if release_tag is not None:
        assert release_tag == f"v{version}", "Release tag must match the checked-out version"
    return version


def artifacts(directory: Path, version: str) -> dict[str, str]:
    expected = {
        f"swirui-{version}-py3-none-any.whl",
        f"swirui-{version}-cp311-abi3-win_amd64.whl",
        f"swirui-{version}.tar.gz",
    }
    assert {p.name for p in directory.iterdir()} == expected, "Unexpected/missing release files"
    with (
        zipfile.ZipFile(directory / f"swirui-{version}-py3-none-any.whl") as portable,
        zipfile.ZipFile(directory / f"swirui-{version}-cp311-abi3-win_amd64.whl") as native,
    ):
        python_files = {
            n for n in portable.namelist() if n.startswith("swirui/") and n.endswith(".py")
        }
        assert python_files and python_files == {
            n for n in native.namelist() if n.startswith("swirui/") and n.endswith(".py")
        }, "Portable/native Python module sets differ"
        for name in python_files:
            assert portable.read(name) == native.read(name), f"Wheel source differs: {name}"
        assert any(
            n.startswith("swirui/_swirui_native") and n.endswith(".pyd") for n in native.namelist()
        ), "Native extension missing from wheel"
        assert not any(n.endswith(".pyd") for n in portable.namelist())
        with tarfile.open(directory / f"swirui-{version}.tar.gz") as source:
            for name in python_files:
                member = source.extractfile(f"swirui-{version}/src/{name}")
                assert member is not None and member.read() == portable.read(name), name
            for name in ("native/Cargo.lock", "native/src/lib.rs", "README.md"):
                assert source.getmember(f"swirui-{version}/{name}").isfile()
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in sorted(expected)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    version = metadata(args.root, release_tag=args.release_tag)
    report: dict[str, object] = {"version": version}
    if args.artifacts is not None:
        report["sha256"] = artifacts(args.artifacts, version)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"version={version}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
