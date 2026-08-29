#!/usr/bin/env python3
"""Remove wheel duplicates created when ZIP flattens shared-library symlinks."""

from __future__ import annotations

import base64
import csv
import hashlib
import sys
import tempfile
import zipfile

from io import StringIO
from pathlib import Path, PurePosixPath


# CMake installs these usual ELF link chains for auditwheel. A wheel archive
# cannot preserve those symlinks, so pip would expand each alias into a full
# copy. Keep the ABI SONAME after auditwheel has completed its analysis.
LIBRARY_ALIASES = {
    "libOpenThreads.so.21": ("libOpenThreads.so", "libOpenThreads.so.3.3.1"),
    "libosg.so.161": ("libosg.so", "libosg.so.3.6.5"),
    "libosgAnimation.so.161": ("libosgAnimation.so", "libosgAnimation.so.3.6.5"),
    "libosgDB.so.161": ("libosgDB.so", "libosgDB.so.3.6.5"),
    "libosgFX.so.161": ("libosgFX.so", "libosgFX.so.3.6.5"),
    "libosgGA.so.161": ("libosgGA.so", "libosgGA.so.3.6.5"),
    "libosgText.so.161": ("libosgText.so", "libosgText.so.3.6.5"),
    "libosgUtil.so.161": ("libosgUtil.so", "libosgUtil.so.3.6.5"),
    "libosgViewer.so.161": ("libosgViewer.so", "libosgViewer.so.3.6.5"),
    "libosgWidget.so.161": ("libosgWidget.so", "libosgWidget.so.3.6.5"),
    # KTX 4.x/early 5.x releases used the 0 ABI SONAME; current KTX 5 uses 5.
    # Keep either layout compact so pin updates do not reintroduce bloat.
    "libktx.so.0": ("libktx.so", "libktx.so.0.0.0"),
    "libktx.so.5": ("libktx.so", "libktx.so.5.0.0"),
}


def record_content(entries: list[tuple[zipfile.ZipInfo, bytes]], record_name: str) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for info, data in entries:
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow((info.filename, f"sha256={digest}", str(len(data))))
    writer.writerow((record_name, "", ""))
    return output.getvalue().encode()


def compact(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as source:
        # Wheel ZIPs need only file entries. Keeping an explicit directory
        # entry confuses auditwheel's wheel scanner, which then tries to open
        # it as an ELF file after extraction.
        entries = [
            (info, source.read(info))
            for info in source.infolist()
            if not info.is_dir()
        ]

    by_basename = {PurePosixPath(info.filename).name: (info, data) for info, data in entries}
    discarded: set[str] = set()
    for soname, aliases in LIBRARY_ALIASES.items():
        if soname not in by_basename:
            continue
        _, soname_data = by_basename[soname]
        for alias in aliases:
            if alias in by_basename:
                alias_info, alias_data = by_basename[alias]
                if alias_data != soname_data:
                    raise RuntimeError(f"{wheel}: {alias} differs from {soname}")
                discarded.add(alias_info.filename)

    record_names = [info.filename for info, _ in entries if info.filename.endswith('.dist-info/RECORD')]
    if len(record_names) != 1:
        raise RuntimeError(f"{wheel}: expected one .dist-info/RECORD, found {record_names}")
    record_name = record_names[0]
    retained = [(info, data) for info, data in entries if info.filename not in discarded and info.filename != record_name]

    with tempfile.NamedTemporaryFile(dir=wheel.parent, suffix=".whl", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as destination:
            for info, data in retained:
                destination.writestr(info, data)
            destination.writestr(record_name, record_content(retained, record_name))
        temporary_path.replace(wheel)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"{wheel.name}: removed {len(discarded)} flattened shared-library aliases")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} WHEEL_DIRECTORY")
    wheels = sorted(Path(sys.argv[1]).glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in {sys.argv[1]}, found {len(wheels)}")
    compact(wheels[0])


if __name__ == "__main__":
    main()
