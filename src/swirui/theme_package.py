"""Portable, data-only theme packages with a versioned JSON contract."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from types import MappingProxyType
from typing import cast

from .surface_style import SurfaceStyle
from .theme import Palette, Theme

_MAX_BYTES = 256 * 1024
_FORMAT = "swirui.theme-package"
_PALETTE_FIELDS = {item.name for item in fields(Palette)}
_THEME_FIELDS = {item.name for item in fields(Theme)} - {"surface_style"}
_SURFACE_FIELDS = {item.name for item in fields(SurfaceStyle)}
_PACKAGE_FIELDS = {
    "format", "format_version", "name", "version", "author", "description",
    "default_theme", "themes",
}


def _string(value: object, label: str, limit: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError(f"{label} must be a {'possibly empty ' if empty else ''}string "
                         f"of at most {limit} characters.")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{label} contains control characters.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must contain valid Unicode.") from error
    return value


def _object(value: object, label: str, expected: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{label} must be a JSON object.")
    if expected is not None and set(value) != expected:
        raise ValueError(f"{label} must contain exactly: {', '.join(sorted(expected))}.")
    return cast(dict[str, object], value)


def _theme_document(theme: Theme, *, styled: bool = True) -> dict[str, object]:
    if not isinstance(theme, Theme) or not isinstance(theme.palette, Palette):
        raise ValueError("Each package variant must be a Theme with a Palette.")
    document = {
        item.name: ({p.name: getattr(theme.palette, p.name) for p in fields(Palette)}
                    if item.name == "palette" else getattr(theme, item.name))
        for item in fields(Theme) if item.name != "surface_style"
    }
    if styled:
        document["surface_style"] = (
            asdict(theme.surface_style) if theme.surface_style is not None else None
        )
    return document


def _parse_theme(value: object, *, styled: bool = True) -> Theme:
    data = _object(value, "Theme", _THEME_FIELDS | ({"surface_style"} if styled else set()))
    surface = data.get("surface_style")
    surface_style = None
    if surface is not None:
        surface_data = _object(surface, "SurfaceStyle", _SURFACE_FIELDS)
        # Constructor checks every field's type, range and finite representation.
        surface_style = SurfaceStyle(**surface_data)  # type: ignore[arg-type]
    palette = _object(data["palette"], "Palette", _PALETTE_FIELDS)
    colors: dict[str, str] = {}
    for role, swatch in palette.items():
        if not isinstance(swatch, str) or re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?",
                                                     swatch) is None:
            raise ValueError(f"Palette {role} must be #RRGGBB or #RRGGBBAA.")
        colors[role] = swatch
    numbers: dict[str, float] = {}
    for token in ("control_radius", "motion_duration"):
        number = data[token]
        if type(number) not in (int, float):
            raise ValueError(f"Theme {token} must be a finite non-negative number.")
        try:
            numeric = float(cast(float, number))
        except OverflowError as error:
            raise ValueError(f"Theme {token} is too large.") from error
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"Theme {token} must be a finite non-negative number.")
        numbers[token] = numeric
    reduced = data["reduced_motion"]
    if not isinstance(reduced, bool):
        raise ValueError("Theme reduced_motion must be a boolean.")
    return Theme(
        palette=Palette(**colors),
        font_family=_string(data["font_family"], "font_family", 256),
        monospace_family=_string(data["monospace_family"], "monospace_family", 256),
        control_radius=numbers["control_radius"], motion_duration=numbers["motion_duration"],
        reduced_motion=reduced,
        surface_style=surface_style,
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"Non-finite JSON number: {value}.")


@dataclass(frozen=True, slots=True)
class ThemePackage:
    """A named collection of immutable themes, independent of global application state.

    Packages contain complete palettes and tokens, not code, imports, paths or
    font binaries. Apply a loaded variant through ``component.theme``. JSON
    Format 1 preserves basic themes; format 2 adds optional surface styles.
    Both versions are strict so unsupported tokens cannot be silently lost.
    """

    name: str
    themes: Mapping[str, Theme]
    default_theme: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        _string(self.name, "Package name", 120)
        _string(self.version, "Package version", 64)
        _string(self.author, "Package author", 120, empty=True)
        _string(self.description, "Package description", 2048, empty=True)
        if not isinstance(self.themes, Mapping) or not 1 <= len(self.themes) <= 32:
            raise ValueError("A package must contain between 1 and 32 theme variants.")
        copied = dict(self.themes)
        for key, theme in copied.items():
            if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", key) is None:
                raise ValueError("Theme keys must use 1–48 lowercase ASCII letters, digits, _ or - "
                                 "and begin with a letter.")
            _parse_theme(_theme_document(theme))
        if not isinstance(self.default_theme, str) or self.default_theme not in copied:
            raise ValueError("default_theme must identify a variant in the package.")
        object.__setattr__(self, "themes", MappingProxyType(copied))

    @property
    def default(self) -> Theme:
        """The default variant, ready to assign to a component."""
        return self.themes[self.default_theme]

    def dumps(self) -> str:
        """Return deterministic UTF-8-compatible JSON, including all tokens."""
        styled = any(theme.surface_style is not None for theme in self.themes.values())
        document = {
            "format": _FORMAT, "format_version": 2 if styled else 1, "name": self.name,
            "version": self.version, "author": self.author, "description": self.description,
            "default_theme": self.default_theme,
            "themes": {key: _theme_document(_parse_theme(_theme_document(theme)), styled=styled)
                       for key, theme in self.themes.items()},
        }
        result = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if len(result.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("Theme package exceeds the 256 KiB limit.")
        return result

    @classmethod
    def loads(cls, source: str) -> ThemePackage:
        """Validate and decode JSON without modifying any active theme."""
        if not isinstance(source, str):
            raise ValueError("Theme package JSON must be text.")
        try:
            if len(source) > _MAX_BYTES or len(source.encode("utf-8")) > _MAX_BYTES:
                raise ValueError("Theme package exceeds the 256 KiB limit.")
            parsed = json.loads(source, object_pairs_hook=_unique_object,
                                parse_constant=_reject_constant)
        except (UnicodeEncodeError, RecursionError) as error:
            raise ValueError(
                "Theme package contains invalid Unicode or excessive nesting."
            ) from error
        data = _object(parsed, "Theme package", _PACKAGE_FIELDS)
        if data["format"] != _FORMAT or type(data["format_version"]) is not int:
            raise ValueError("Unrecognized theme-package format.")
        if data["format_version"] not in (1, 2):
            raise ValueError("Unsupported theme-package format_version; expected 1 or 2.")
        themes = _object(data["themes"], "Theme variants")
        if not 1 <= len(themes) <= 32:
            raise ValueError("A package must contain between 1 and 32 theme variants.")
        return cls(
            name=_string(data["name"], "Package name", 120),
            themes={key: _parse_theme(value, styled=data["format_version"] == 2)
                    for key, value in themes.items()},
            default_theme=_string(data["default_theme"], "Default variant", 48),
            version=_string(data["version"], "Package version", 64),
            author=_string(data["author"], "Package author", 120, empty=True),
            description=_string(data["description"], "Package description", 2048, empty=True),
        )

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> ThemePackage:
        """Read at most 256 KiB from an explicit UTF-8 file path."""
        with Path(path).open("rb") as stream:
            content = stream.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise ValueError("Theme package exceeds the 256 KiB limit.")
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Theme package must use UTF-8 encoding.") from error
        return cls.loads(source)

    def save(self, path: str | os.PathLike[str]) -> None:
        """Atomically replace a file; failures leave an existing file intact.

        The parent directory must exist. I/O errors propagate to the caller.
        No application theme is changed and no directories are created.
        """
        content = self.dumps().encode("utf-8")
        target = Path(path)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.",
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
