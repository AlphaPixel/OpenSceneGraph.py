#!/usr/bin/env python3
"""Make a delvewheel-repaired OSG wheel self-contained for osgDB plugins.

OSG loads its format plugins from ``OpenSceneGraph/osgPlugins-3.6.5``.  The
Windows loader used for that secondary load does not reliably search either
the package root or delvewheel's top-level ``openscenegraph.libs`` directory.
Copy the already-vendored DLLs and ktx.dll beside the plugins, then rebuild
RECORD so pip can install the modified wheel normally.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
from pathlib import Path
import tempfile
import zipfile


PACKAGE_DIR = "OpenSceneGraph"
PLUGIN_DIR = f"{PACKAGE_DIR}/osgPlugins-3.6.5"
KTX_DLL = f"{PACKAGE_DIR}/ktx.dll"


def record_row(name: str, data: bytes) -> list[str]:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return [name, f"sha256={digest.decode('ascii')}", str(len(data))]


def repair_wheel(wheel_path: Path) -> None:
    with zipfile.ZipFile(wheel_path, "r") as source:
        files = {
            info.filename: (info, source.read(info.filename))
            for info in source.infolist()
            if not info.is_dir()
        }

    record_names = [name for name in files if name.endswith(".dist-info/RECORD")]
    if len(record_names) != 1:
        raise RuntimeError(f"Expected one wheel RECORD in {wheel_path}, found {record_names!r}")
    record_name = record_names[0]

    libs_dir = next(
        (name.rsplit("/", 1)[0] for name in files if name.endswith(".libs/.keep")),
        None,
    )
    if libs_dir is None:
        libs_dir = next(
            (name.rsplit("/", 1)[0] for name in files if ".libs/" in name),
            None,
        )
    if libs_dir is None:
        raise RuntimeError(f"No delvewheel .libs directory found in {wheel_path}")

    plugin_prefix = f"{PLUGIN_DIR}/"
    if not any(name.startswith(plugin_prefix) for name in files):
        raise RuntimeError(f"No packaged osgDB plugin directory found in {wheel_path}")
    if KTX_DLL not in files:
        raise RuntimeError(f"Missing packaged {KTX_DLL} in {wheel_path}")

    additions: dict[str, bytes] = {}
    for name, (_, data) in files.items():
        if name.startswith(f"{libs_dir}/") and name.lower().endswith(".dll"):
            additions[f"{PLUGIN_DIR}/{Path(name).name}"] = data
    additions[f"{PLUGIN_DIR}/ktx.dll"] = files[KTX_DLL][1]

    files.update((name, (None, data)) for name, data in additions.items())
    files.pop(record_name)

    with tempfile.NamedTemporaryFile(
        dir=wheel_path.parent, prefix=f".{wheel_path.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name in sorted(files):
                info, data = files[name]
                if info is None:
                    output.writestr(name, data)
                else:
                    output.writestr(info, data)

            rows = [record_row(name, data) for name, (_, data) in sorted(files.items())]
            rows.append([record_name, "", ""])
            record = "".join(",".join(row) + "\n" for row in rows).encode("utf-8")
            output.writestr(record_name, record)
        os.replace(temporary_path, wheel_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Copied {len(additions)} runtime DLLs beside osgDB plugins in {wheel_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_dir", type=Path, help="Directory containing exactly one repaired wheel")
    arguments = parser.parse_args()

    wheels = sorted(arguments.wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected exactly one wheel in {arguments.wheel_dir}, found: {wheels!r}")
    repair_wheel(wheels[0])


if __name__ == "__main__":
    main()
