"""Check native imports in a Windows PyInstaller executable before delivery."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PureWindowsPath

import pefile
from PyInstaller.archive.readers import CArchiveReader


def verify_bundle(path: Path) -> None:
    archive = CArchiveReader(path)
    binaries: dict[str, pefile.PE] = {}
    by_name: dict[str, list[str]] = {}
    for name in archive.toc:
        if not name.lower().endswith((".dll", ".pyd")):
            continue
        pe = pefile.PE(data=archive.extract(name), fast_load=True, max_symbol_exports=65536)
        pe.parse_data_directories([0, 1])
        binaries[name] = pe
        by_name.setdefault(PureWindowsPath(name).name.lower(), []).append(name)

    errors: list[str] = []
    for name, pe in list(binaries.items()):
        for dependency in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            dependency_name = dependency.dll.decode("ascii").lower()
            candidates = by_name.get(dependency_name, [])
            # Qt's Windows ICU imports must resolve against the Windows API,
            # including when ICU is correctly left out of the executable.
            if not candidates and dependency_name == "icuuc.dll":
                system_icu = Path(os.environ["SystemRoot"]) / "System32" / dependency_name
                candidates = [str(system_icu)]
                if candidates[0] not in binaries:
                    system_pe = pefile.PE(str(system_icu), fast_load=True, max_symbol_exports=65536)
                    system_pe.parse_data_directories([0])
                    binaries[candidates[0]] = system_pe
            for candidate in candidates:
                export_table = getattr(binaries[candidate], "DIRECTORY_ENTRY_EXPORT", None)
                exports = {symbol.name for symbol in export_table.symbols} if export_table else set()
                missing = [
                    symbol.name.decode("ascii")
                    for symbol in dependency.imports
                    if symbol.name and symbol.name not in exports
                ]
                if missing:
                    errors.append(f"{name} -> {candidate}: missing {', '.join(missing[:5])}")
    if errors:
        raise RuntimeError("Incompatible bundled DLLs:\n" + "\n".join(errors))
    print(f"Native DLL imports verified: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    verify_bundle(parser.parse_args().executable)
