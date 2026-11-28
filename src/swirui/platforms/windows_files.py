"""Owned Unicode Save As dialog using the Windows common-dialog library."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any


class _OpenFileName(ctypes.Structure):
    # OPENFILENAMEW, commdlg.h. Pointer-sized fields retain native alignment.
    _fields_ = [
        ("lStructSize", ctypes.c_uint32), ("hwndOwner", ctypes.c_void_p),
        ("hInstance", ctypes.c_void_p), ("lpstrFilter", ctypes.c_wchar_p),
        ("lpstrCustomFilter", ctypes.c_void_p), ("nMaxCustFilter", ctypes.c_uint32),
        ("nFilterIndex", ctypes.c_uint32), ("lpstrFile", ctypes.POINTER(ctypes.c_wchar)),
        ("nMaxFile", ctypes.c_uint32), ("lpstrFileTitle", ctypes.c_void_p),
        ("nMaxFileTitle", ctypes.c_uint32), ("lpstrInitialDir", ctypes.c_wchar_p),
        ("lpstrTitle", ctypes.c_wchar_p), ("Flags", ctypes.c_uint32),
        ("nFileOffset", ctypes.c_uint16), ("nFileExtension", ctypes.c_uint16),
        ("lpstrDefExt", ctypes.c_wchar_p), ("lCustData", ctypes.c_ssize_t),
        ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", ctypes.c_wchar_p),
        ("pvReserved", ctypes.c_void_p), ("dwReserved", ctypes.c_uint32),
        ("FlagsEx", ctypes.c_uint32),
    ]


def choose_save_file(hwnd: int, suggested_name: str, title: str) -> Path | None:
    win_dll: Any = ctypes.__dict__["WinDLL"]
    library = win_dll("comdlg32")
    choose = library.GetSaveFileNameW
    choose.argtypes, choose.restype = [ctypes.POINTER(_OpenFileName)], ctypes.c_int
    error = library.CommDlgExtendedError
    error.argtypes, error.restype = [], ctypes.c_uint32
    suggested = Path(suggested_name)
    if not suggested.name:
        raise ValueError("Supply a filename for the Save As dialog.")
    filename = ctypes.create_unicode_buffer(suggested.name, 32768)
    suffix = suggested.suffix.removeprefix(".")
    filters = "All files (*.*)\0*.*\0"
    if suffix and not any(c in suffix for c in ";*?"):
        filters = f"{suffix.upper()} files (*.{suffix})\0*.{suffix}\0" + filters
    filter_buffer = ctypes.create_unicode_buffer(filters)
    dialog = _OpenFileName()
    dialog.lStructSize = ctypes.sizeof(dialog)
    dialog.hwndOwner = hwnd
    dialog.lpstrFilter = ctypes.cast(filter_buffer, ctypes.c_wchar_p)
    dialog.nFilterIndex = 1
    dialog.lpstrFile, dialog.nMaxFile = filename, len(filename)
    if suggested.parent != Path("."):
        dialog.lpstrInitialDir = str(suggested.parent.absolute())
    dialog.lpstrTitle, dialog.lpstrDefExt = title, suffix or None
    # OFN_EXPLORER | PATHMUSTEXIST | NOCHANGEDIR | HIDEREADONLY | OVERWRITEPROMPT
    dialog.Flags = 0x80000 | 0x800 | 0x8 | 0x4 | 0x2
    if choose(ctypes.byref(dialog)):
        return Path(filename.value)
    code = error()
    if code:
        raise OSError(f"Windows Save As dialog failed (0x{code:04X}).")
    return None
