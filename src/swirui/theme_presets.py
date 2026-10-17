"""Built-in opaque appearance families, ready for runtime use or export."""

from collections.abc import Mapping
from types import MappingProxyType

from .theme import FUTURE_DARK, FUTURE_LIGHT, Palette, Theme

NEON_BLUE = Theme(palette=Palette(
    canvas="#050D19", surface="#0B1728", raised="#102139", hover="#163350",
    pressed="#1C4266", border="#304F71", focus="#9AEAFF", accent="#62DEFF",
    accent_hover="#9AEAFF", accent_pressed="#3DBCD9", on_accent="#051923",
    text="#ECF7FF", muted="#9EB5CD", disabled="#142538", disabled_text="#7188A2",
    selection="#154968", success="#7FE0BF", warning="#F3D083", error="#FF9DAF",
))

NEON_GREEN = Theme(palette=Palette(
    canvas="#06130D", surface="#0D2118", raised="#163126", hover="#214635",
    pressed="#2D5742", border="#3C6652", focus="#ACFFD0", accent="#6EF2A4",
    accent_hover="#ACFFD0", accent_pressed="#47CD81", on_accent="#062615",
    text="#ECFFF3", muted="#A0C7AF", disabled="#193326", disabled_text="#749B84",
    selection="#24583D", success="#9BF5B7", warning="#F5D68B", error="#FFA8AD",
))

MATRIX = Theme(palette=Palette(
    canvas="#020603", surface="#061009", raised="#0C1D10", hover="#15351D",
    pressed="#21462A", border="#355D3E", focus="#A6FFBA", accent="#4FF77B",
    accent_hover="#8AFFA9", accent_pressed="#35CF60", on_accent="#032309",
    text="#ADFFBA", muted="#77BA84", disabled="#102417", disabled_text="#63836A",
    selection="#21462A", success="#79F79B", warning="#E6E887", error="#FF9A9A",
), font_family="Cascadia Mono", control_radius=2, motion_duration=0.12)

CYBERPUNK = Theme(palette=Palette(
    canvas="#110923", surface="#1C1030", raised="#291940", hover="#3B2456",
    pressed="#50326D", border="#654179", focus="#7FEAFF", accent="#FF7ADE",
    accent_hover="#FFACEA", accent_pressed="#D957BE", on_accent="#2B0921",
    text="#FAEDFF", muted="#C2A7D0", disabled="#2E203D", disabled_text="#917BA1",
    selection="#58336F", success="#88F0D1", warning="#FFE18A", error="#FF9DBA",
), control_radius=4, motion_duration=0.2)

OLED = Theme(palette=Palette(
    canvas="#000000", surface="#000000", raised="#101010", hover="#202020",
    pressed="#303030", border="#3C3C3C", focus="#FFFFFF", accent="#DCDCDC",
    accent_hover="#FFFFFF", accent_pressed="#B8B8B8", on_accent="#080808",
    text="#FFFFFF", muted="#B8B8B8", disabled="#141414", disabled_text="#777777",
    selection="#303030", success="#8BE0B4", warning="#F0D38A", error="#FF9DAF",
), control_radius=8)

MINIMAL = Theme(palette=Palette(
    canvas="#FAFAFA", surface="#FFFFFF", raised="#F2F2F2", hover="#E8E8E8",
    pressed="#DADADA", border="#C4C4C4", focus="#505050", accent="#252525",
    accent_hover="#404040", accent_pressed="#000000", on_accent="#FFFFFF",
    text="#151515", muted="#5C5C5C", disabled="#E8E8E8", disabled_text="#7B7B7B",
    selection="#D5D5D5", success="#176545", warning="#7A5000", error="#AD2945",
), control_radius=6, motion_duration=0.12)

PROFESSIONAL = Theme(palette=Palette(
    canvas="#EEF2F7", surface="#FFFFFF", raised="#E5ECF5", hover="#D8E4F2",
    pressed="#C6D7EC", border="#A8B9CE", focus="#124FA0", accent="#1756A3",
    accent_hover="#1C67BD", accent_pressed="#0E4386", on_accent="#FFFFFF",
    text="#18283A", muted="#4A6077", disabled="#DDE5EF", disabled_text="#74869A",
    selection="#C5D9F0", success="#146F52", warning="#805400", error="#AD2945",
), control_radius=6, motion_duration=0.12)

THEME_PRESETS: Mapping[str, Theme] = MappingProxyType({
    "future_dark": FUTURE_DARK,
    "future_light": FUTURE_LIGHT,
    "neon_blue": NEON_BLUE,
    "neon_green": NEON_GREEN,
    "matrix": MATRIX,
    "cyberpunk": CYBERPUNK,
    "oled": OLED,
    "minimal": MINIMAL,
    "professional": PROFESSIONAL,
})
