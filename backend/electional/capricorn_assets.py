"""Local CapricornPROMETHEUS asset discovery and safe import planning."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import zlib
from typing import Iterable, Mapping

from .aspects import Aspect, AspectProfile, aspect_profile_by_id, load_aspect_profiles, sanitize_aspect_id, save_aspect_profiles


DEFAULT_CAPRICORN_FOLDER = "CapricornPROMETHEUS1.5"
IMPORTABLE_CONFIG_EXTENSIONS = {
    ".alm_conf",
    ".arp_conf",
    ".asp_conf",
    ".asteroid_conf",
    ".astrology_settings",
    ".disp_scheme",
    ".heliacal_conf",
    ".mpt_conf",
    ".pl_orb",
    ".point_color_scheme",
    ".pt_conf",
    ".rl_conf",
    ".sign_color_scheme",
    ".star_conf",
    ".st_conf",
    ".wheel_design",
    ".zodiac13_conf",
}
REFERENCE_ONLY_EXTENSIONS = {".bmp", ".zip", ".primary_direction", ".chart_database"}
ASPECT_CONFIG_FOLDER = "Aspect Configurations"
CAPRICORN_ASPECT_GLYPHS = {
    "conjunction": "\u260c",
    "opposition": "\u260d",
    "trine": "\u25b3",
    "square": "\u25a1",
    "sextile": "\u2736",
    "semisquare": "\u2220",
    "sesquisquare": "\u26b9",
    "semisextile": "\u26ba",
    "quincunx": "Qx",
    "decile": "D",
    "quintile": "Q",
    "tridecile": "3D",
    "biquintile": "BQ",
    "septile": "7",
    "biseptile": "B7",
    "triseptile": "T7",
    "novile": "N",
    "binovile": "B9",
    "quadrinovile": "Q9",
    "undecile": "11",
    "biundecile": "B11",
    "triundecile": "T11",
    "quadriundecile": "Q11",
    "quinqueundecile": "5U",
    "parallel": "||",
    "contraparallel": "C||",
}
CAPRICORN_ASPECT_COLORS = {
    "support": "#286fc2",
    "stress": "#c23f4e",
    "mixed": "#536d8d",
}
CAPRICORN_BUILT_IN_ASPECT_IDS = {"conjunction", "trine", "square", "opposition", "sextile"}
CAPRICORN_KNOWN_ASPECT_NAMES = {
    "Conjunction",
    "Opposition",
    "Trine",
    "Square",
    "Sextile",
    "Semisquare",
    "Sesquisquare",
    "Semisextile",
    "Quincunx",
    "Decile",
    "Quintile",
    "TriDecile",
    "BiQuintile",
    "Septile",
    "BiSeptile",
    "TriSeptile",
    "Novile",
    "BiNovile",
    "QuadriNovile",
    "Undecile",
    "BiUndecile",
    "TriUndecile",
    "QuadriUndecile",
    "QuinqueUndecile",
    "Parallel",
    "ContraParallel",
}


@dataclass(frozen=True)
class CapricornAssetInventory:
    root: Path | None
    exists: bool
    total_files: int
    extension_counts: Mapping[str, int]
    importable_config_count: int
    reference_only_count: int
    unknown_count: int
    sample_files: tuple[str, ...]


@dataclass(frozen=True)
class CapricornAspectImportResult:
    root: Path | None
    scanned_files: int
    imported_profiles: int
    skipped_files: tuple[str, ...]
    saved_path: Path


def candidate_capricorn_roots(home: Path | None = None) -> tuple[Path, ...]:
    base = home or Path.home()
    return (
        base / "OneDrive" / "Documents" / DEFAULT_CAPRICORN_FOLDER,
        base / "Documents" / DEFAULT_CAPRICORN_FOLDER,
        base / "Downloads" / DEFAULT_CAPRICORN_FOLDER,
    )


def discover_capricorn_root(candidates: Iterable[Path] | None = None) -> Path | None:
    for candidate in candidates or candidate_capricorn_roots():
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def classify_capricorn_asset(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMPORTABLE_CONFIG_EXTENSIONS:
        return "importable-config"
    if suffix in REFERENCE_ONLY_EXTENSIONS or path.name.lower() == "manifest":
        return "reference-only"
    return "unknown"


def inventory_capricorn_assets(root: Path | str | None = None) -> CapricornAssetInventory:
    resolved = Path(root) if root else discover_capricorn_root()
    if not resolved or not resolved.exists():
        return CapricornAssetInventory(None, False, 0, {}, 0, 0, 0, ())

    files = [path for path in resolved.rglob("*") if path.is_file()]
    extension_counts = Counter(path.suffix.lower() or "[none]" for path in files)
    classes = Counter(classify_capricorn_asset(path) for path in files)
    samples = tuple(str(path.relative_to(resolved)) for path in files[:18])
    return CapricornAssetInventory(
        root=resolved,
        exists=True,
        total_files=len(files),
        extension_counts=dict(sorted(extension_counts.items(), key=lambda item: (-item[1], item[0]))),
        importable_config_count=int(classes.get("importable-config", 0)),
        reference_only_count=int(classes.get("reference-only", 0)),
        unknown_count=int(classes.get("unknown", 0)),
        sample_files=samples,
    )


def format_capricorn_asset_audit(inventory: CapricornAssetInventory) -> str:
    if not inventory.exists or not inventory.root:
        searched = "\n".join(f"- {path}" for path in candidate_capricorn_roots())
        return (
            "CapricornPROMETHEUS Asset Audit\n\n"
            "Folder not found in the usual locations.\n\n"
            "Searched:\n"
            f"{searched}\n\n"
            "Safe path: point the importer to the folder before extracting configuration ideas."
        )

    extension_lines = [
        f"- {extension}: {count}"
        for extension, count in list(inventory.extension_counts.items())[:14]
    ]
    sample_lines = [f"- {sample}" for sample in inventory.sample_files[:12]]
    return (
        "CapricornPROMETHEUS Asset Audit\n\n"
        f"Folder: {inventory.root}\n"
        f"Total files: {inventory.total_files}\n"
        f"Importable configuration candidates: {inventory.importable_config_count}\n"
        f"Reference-only/proprietary assets: {inventory.reference_only_count}\n"
        f"Unknown files: {inventory.unknown_count}\n\n"
        "Safe import policy\n"
        "- Do not copy proprietary backgrounds, binaries, databases, or raw vendor config files into this repo.\n"
        "- Use configs as local user-supplied references or convert only factual settings into our own JSON/profile format.\n"
        "- Recreate icons, buttons, and wheel art as original UI assets inside our app.\n\n"
        "Best next extraction targets\n"
        "- Aspect Configurations -> our custom aspect profiles.\n"
        "- Color Schemes -> our own named palettes after manual review.\n"
        "- Zodiac13 Configurations -> validation/reference data for our True 13-Sign mode.\n"
        "- Wheel/Page Designs -> layout inspiration only, not raw asset copying.\n\n"
        "Top file types\n"
        + "\n".join(extension_lines)
        + "\n\nSample files\n"
        + "\n".join(sample_lines)
    )


def capricorn_aspect_config_dir(root: Path | str | None = None) -> Path | None:
    resolved = Path(root) if root else discover_capricorn_root()
    if not resolved:
        return None
    directory = resolved / ASPECT_CONFIG_FOLDER
    return directory if directory.exists() and directory.is_dir() else None


def _decompressed_streams(path: Path) -> list[bytes]:
    data = path.read_bytes()
    streams: list[bytes] = []
    start = 0
    while True:
        index = data.find(b"\x78\x9c", start)
        if index < 0:
            break
        try:
            decompressor = zlib.decompressobj()
            payload = decompressor.decompress(data[index:])
        except zlib.error:
            start = index + 2
            continue
        if payload:
            streams.append(payload)
        start = index + 2
    return streams


def _read_utf16le_string(buffer: bytes, offset: int) -> str:
    end = offset
    while end + 1 < len(buffer):
        if buffer[end : end + 2] == b"\x00\x00":
            break
        end += 2
    return buffer[offset:end].decode("utf-16le", errors="ignore").strip()


def _read_int_field(buffer: bytes, record_start: int, record_end: int, field_id: int) -> int | None:
    marker = bytes((0x02, 0x00, field_id, 0x00))
    index = buffer.find(marker, record_start, record_end)
    if index < 0 or index + 12 > len(buffer):
        return None
    try:
        return int(struct.unpack_from("<i", buffer, index + 8)[0])
    except struct.error:
        return None


def _read_double_field(buffer: bytes, record_start: int, record_end: int, field_id: int) -> float | None:
    marker = bytes((0x01, 0x00, field_id, 0x00))
    index = buffer.find(marker, record_start, record_end)
    if index < 0 or index + 16 > len(buffer):
        return None
    try:
        value = float(struct.unpack_from("<d", buffer, index + 8)[0])
    except struct.error:
        return None
    return value if math.isfinite(value) else None


def _read_string_field(buffer: bytes, record_start: int, record_end: int, field_id: int) -> str:
    marker = bytes((0x04, 0x00, field_id, 0x00))
    index = buffer.find(marker, record_start, record_end)
    if index < 0 or index + 8 > len(buffer):
        return ""
    return _read_utf16le_string(buffer, index + 8)


def _aspect_record_ranges(buffer: bytes) -> list[tuple[int, int, str]]:
    names: list[tuple[int, str]] = []
    for name in CAPRICORN_KNOWN_ASPECT_NAMES:
        encoded = name.encode("utf-16le")
        start = 0
        while True:
            index = buffer.find(encoded, start)
            if index < 0:
                break
            if index >= 2400:
                if index >= 2 and buffer[index - 1] == 0 and chr(buffer[index - 2]).isalnum():
                    start = index + 2
                    continue
                parsed = _read_utf16le_string(buffer, index)
                if parsed == name:
                    names.append((index, name))
            start = index + 2
    names = sorted(set(names), key=lambda item: item[0])
    ranges: list[tuple[int, int, str]] = []
    for position, (name_offset, name) in enumerate(names):
        record_start = max(0, name_offset - 96)
        record_end = names[position + 1][0] - 96 if position + 1 < len(names) else min(len(buffer), name_offset + 900)
        ranges.append((record_start, max(record_start + 240, record_end), name))
    return ranges


def _capricorn_tone(nature_value: int | None, aspect_id: str) -> str:
    if nature_value == 1:
        return "support"
    if nature_value == 2:
        return "stress"
    if aspect_id in {"trine", "sextile", "quintile", "biquintile"}:
        return "support"
    if aspect_id in {"square", "opposition", "semisquare", "sesquisquare"}:
        return "stress"
    return "mixed"


def _angle_degrees(radians: float | None, fallback: float = 0.0) -> float:
    if radians is None:
        return fallback
    degrees = radians * 180.0 / math.pi
    return round(degrees, 6)


def _orb_degrees(radians: float | None, fallback: float = 1.0) -> float:
    if radians is None:
        return fallback
    degrees = radians * 180.0 / math.pi
    return round(max(0.0, degrees), 3)


def parse_capricorn_aspect_config(path: Path | str) -> AspectProfile:
    config_path = Path(path)
    streams = _decompressed_streams(config_path)
    if not streams:
        raise ValueError(f"No readable compressed aspect data found in {config_path.name}.")
    buffer = max(streams, key=len)
    aspects: list[Aspect] = []
    for record_start, record_end, fallback_name in _aspect_record_ranges(buffer):
        name = _read_string_field(buffer, record_start, record_end, 0x03) or fallback_name
        abbreviation = _read_string_field(buffer, record_start, record_end, 0x25) or name[:4]
        aspect_id = sanitize_aspect_id(name)
        active_value = _read_int_field(buffer, record_start, record_end, 0x23)
        nature_value = _read_int_field(buffer, record_start, record_end, 0x26)
        angle = _angle_degrees(_read_double_field(buffer, record_start, record_end, 0x27))
        orb = _orb_degrees(_read_double_field(buffer, record_start, record_end, 0x2B), fallback=1.0)
        if not 0 <= angle <= 180:
            continue
        tone = _capricorn_tone(nature_value, aspect_id)
        aspects.append(
            Aspect(
                id=aspect_id,
                name=name,
                angle=angle,
                default_orb=orb,
                tone=tone,
                meaning=f"Imported from local CapricornPROMETHEUS aspect configuration: {config_path.name}.",
                abbreviation=abbreviation,
                glyph=CAPRICORN_ASPECT_GLYPHS.get(aspect_id, abbreviation[:2] or name[:2]),
                color=CAPRICORN_ASPECT_COLORS[tone],
                enabled=bool(active_value),
                built_in=aspect_id in CAPRICORN_BUILT_IN_ASPECT_IDS,
            )
        )
    if not aspects:
        raise ValueError(f"No aspect records could be converted from {config_path.name}.")
    profile_name = f"Capricorn {config_path.stem}"
    return AspectProfile(
        sanitize_aspect_id(profile_name),
        profile_name,
        f"Converted from local CapricornPROMETHEUS aspect config {config_path.name}; raw file remains outside the repo.",
        tuple(aspects),
    )


def load_capricorn_aspect_profiles(root: Path | str | None = None) -> list[AspectProfile]:
    directory = capricorn_aspect_config_dir(root)
    if not directory:
        return []
    profiles: list[AspectProfile] = []
    for path in sorted(directory.glob("*.asp_conf")):
        try:
            profiles.append(parse_capricorn_aspect_config(path))
        except (OSError, ValueError, zlib.error, struct.error):
            continue
    return profiles


def import_capricorn_aspect_profiles(
    root: Path | str | None = None,
    *,
    profile_path: Path | None = None,
) -> CapricornAspectImportResult:
    directory = capricorn_aspect_config_dir(root)
    target_path = profile_path or Path.cwd() / ".electional-aspect-profiles.json"
    if not directory:
        return CapricornAspectImportResult(None, 0, 0, (), target_path)

    existing = load_aspect_profiles(target_path)
    by_id = {profile.id: profile for profile in existing}
    skipped: list[str] = []
    scanned = 0
    imported = 0
    for path in sorted(directory.glob("*.asp_conf")):
        scanned += 1
        try:
            profile = parse_capricorn_aspect_config(path)
        except (OSError, ValueError, zlib.error, struct.error):
            skipped.append(path.name)
            continue
        by_id[profile.id] = profile
        imported += 1

    ordered = [aspect_profile_by_id("major-five", by_id.values())]
    ordered.extend(profile for profile_id, profile in sorted(by_id.items()) if profile_id != "major-five")
    save_aspect_profiles(ordered, target_path)
    return CapricornAspectImportResult(
        root=directory.parent,
        scanned_files=scanned,
        imported_profiles=imported,
        skipped_files=tuple(skipped),
        saved_path=target_path,
    )


def format_capricorn_aspect_import_result(result: CapricornAspectImportResult) -> str:
    if not result.root:
        return (
            "Capricorn Aspect Import\n\n"
            "No CapricornPROMETHEUS aspect configuration folder was found.\n"
            "Open Assets first to verify the folder path."
        )
    skipped = "\n".join(f"- {name}" for name in result.skipped_files[:12]) or "- None"
    return (
        "Capricorn Aspect Import\n\n"
        f"Folder: {result.root}\n"
        f"Scanned .asp_conf files: {result.scanned_files}\n"
        f"Imported/updated profiles: {result.imported_profiles}\n"
        f"Saved to: {result.saved_path}\n\n"
        "Imported data\n"
        "- Aspect name and abbreviation.\n"
        "- Enabled/disabled state.\n"
        "- Exact angle converted from radians to degrees.\n"
        "- Default orb converted from radians to degrees.\n"
        "- Nature converted to support/stress/mixed.\n\n"
        "Skipped files\n"
        f"{skipped}\n\n"
        "Raw Capricorn files were not copied into the repository."
    )
