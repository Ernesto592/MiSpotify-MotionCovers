#!/usr/bin/env python3
"""Validate MiSpotify's public Motion Covers catalog using only stdlib + ffprobe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

MAX_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 720
MAX_FPS = 24.0
MAX_DURATION_SECONDS = 20.0
DURATION_TOLERANCE_MS = 250
FPS_TOLERANCE = 0.05
SUPPORTED_TYPES = {
    "mp4": ".mp4",
    "webm": ".webm",
    "animated_webp": ".webp",
    "lottie": ".json",
}

ProbeRunner = Callable[[Path], dict[str, Any]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fraction(value: Any) -> float:
    if value in (None, "", "0/0", "N/A"):
        return 0.0
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def run_ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        os.fspath(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is required but was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "unknown ffprobe error").strip()
        raise RuntimeError(f"ffprobe failed for {path}: {details}") from exc
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON for {path}") from exc


def _safe_repo_path(root: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if not raw_path or candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_root = root.resolve()
    resolved_candidate = (root / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved_candidate


def _validate_lottie(asset_id: str, asset: dict[str, Any], path: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"asset {asset_id}: invalid Lottie JSON: {exc}"], {}

    width = _int(payload.get("w"))
    height = _int(payload.get("h"))
    fps = _float(payload.get("fr"))
    ip = _float(payload.get("ip"))
    op = _float(payload.get("op"))
    duration = ((op - ip) / fps) if fps > 0 and op >= ip else 0.0
    meta = {"width": width, "height": height, "fps": fps, "duration": duration, "audio_streams": 0}
    errors.extend(_validate_common_media_limits(asset_id, width, height, fps, duration, 0))
    return errors, meta


def _validate_common_media_limits(
    asset_id: str,
    width: int,
    height: int,
    fps: float,
    duration_seconds: float,
    audio_streams: int,
) -> list[str]:
    errors: list[str] = []
    if width <= 0 or height <= 0:
        errors.append(f"asset {asset_id}: media dimensions are missing or invalid")
    elif width != height:
        errors.append(f"asset {asset_id}: media must be square, got {width}x{height}")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        errors.append(
            f"asset {asset_id}: media dimensions {width}x{height} exceed official 720x720 limit"
        )
    if fps <= 0:
        errors.append(f"asset {asset_id}: FPS is missing or invalid")
    elif fps > MAX_FPS + FPS_TOLERANCE:
        errors.append(f"asset {asset_id}: media is {fps:.3f} FPS; official limit is 24 FPS")
    if duration_seconds <= 0:
        errors.append(f"asset {asset_id}: duration is missing or invalid")
    elif duration_seconds > MAX_DURATION_SECONDS + 0.05:
        errors.append(
            f"asset {asset_id}: media duration is {duration_seconds:.3f}s; official limit is 20 seconds"
        )
    if audio_streams:
        errors.append(f"asset {asset_id}: media must not contain audio streams (found {audio_streams})")
    return errors


def _validate_probed_media(
    asset_id: str,
    asset: dict[str, Any],
    probe: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    video_streams = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        errors.append(f"asset {asset_id}: expected exactly one video stream, found {len(video_streams)}")
        return errors, {}

    video = video_streams[0]
    width = _int(video.get("width"))
    height = _int(video.get("height"))
    fps = _fraction(video.get("avg_frame_rate")) or _fraction(video.get("r_frame_rate"))
    format_data = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = _float(video.get("duration")) or _float(format_data.get("duration"))

    errors.extend(_validate_common_media_limits(asset_id, width, height, fps, duration, len(audio_streams)))

    if asset.get("type") == "mp4":
        codec = str(video.get("codec_name") or "").lower()
        pix_fmt = str(video.get("pix_fmt") or "").lower()
        if codec != "h264":
            errors.append(f"asset {asset_id}: MP4 codec must be h264, got {codec or 'unknown'}")
        if pix_fmt != "yuv420p":
            errors.append(f"asset {asset_id}: MP4 pixel format must be yuv420p, got {pix_fmt or 'unknown'}")

    return errors, {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "audio_streams": len(audio_streams),
        "codec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
    }


def validate_catalog(
    repo_root: Path | str,
    manifest_path: Path | str,
    *,
    probe_runner: ProbeRunner = run_ffprobe,
) -> list[str]:
    root = Path(repo_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file

    errors: list[str] = []
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"manifest not found: {manifest_file}"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"manifest could not be parsed: {exc}"]

    if not isinstance(manifest, dict):
        return ["manifest root must be a JSON object"]
    if manifest.get("schema") != 1:
        errors.append(f"manifest schema must be 1, got {manifest.get('schema')!r}")
    revision = manifest.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("manifest revision must be a positive integer")
    cdn = manifest.get("cdnBaseUrl")
    if not isinstance(cdn, str) or not cdn.startswith("https://"):
        errors.append("manifest cdnBaseUrl must use https://")

    assets = manifest.get("assets")
    entries = manifest.get("entries")
    if not isinstance(assets, dict) or not assets:
        errors.append("manifest assets must be a non-empty object")
        assets = {}
    if not isinstance(entries, list) or not entries:
        errors.append("manifest entries must be a non-empty array")
        entries = []

    seen_entry_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry #{index}: must be an object")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append(f"entry #{index}: id must be a non-empty string")
        elif entry_id in seen_entry_ids:
            errors.append(f"entry {entry_id}: duplicate entry id")
        else:
            seen_entry_ids.add(entry_id)
        asset_id = entry.get("assetId")
        if asset_id not in assets:
            errors.append(f"entry {entry_id or index}: references missing asset {asset_id!r}")
        scope = entry.get("scope")
        identity = entry.get("identity")
        if scope not in {"track", "album"}:
            errors.append(f"entry {entry_id or index}: scope must be track or album")
        if not isinstance(identity, dict):
            errors.append(f"entry {entry_id or index}: identity must be an object")
        elif not str(identity.get("artist") or "").strip():
            errors.append(f"entry {entry_id or index}: identity.artist is required")
        elif scope == "track" and not str(identity.get("title") or "").strip():
            errors.append(f"entry {entry_id or index}: track identity.title is required")
        elif scope == "album" and not str(identity.get("album") or "").strip():
            errors.append(f"entry {entry_id or index}: album identity.album is required")

    for asset_id, asset in assets.items():
        prefix = f"asset {asset_id}:"
        if not isinstance(asset_id, str) or not asset_id:
            errors.append("asset ids must be non-empty strings")
            continue
        if not isinstance(asset, dict):
            errors.append(f"{prefix} metadata must be an object")
            continue

        asset_type = asset.get("type")
        expected_ext = SUPPORTED_TYPES.get(asset_type)
        if expected_ext is None:
            errors.append(f"{prefix} unsupported type {asset_type!r}")
            continue

        raw_path = asset.get("path")
        if not isinstance(raw_path, str) or _safe_repo_path(root, raw_path) is None:
            errors.append(f"{prefix} unsafe path {raw_path!r}")
            continue
        path = _safe_repo_path(root, raw_path)
        assert path is not None
        if path.suffix.lower() != expected_ext:
            errors.append(f"{prefix} type {asset_type} requires {expected_ext} extension")
        if not path.is_file():
            errors.append(f"{prefix} file does not exist: {raw_path}")
            continue

        actual_size = path.stat().st_size
        declared_size = asset.get("sizeBytes")
        if declared_size != actual_size:
            errors.append(f"{prefix} sizeBytes={declared_size!r} does not match file size {actual_size}")
        if actual_size > MAX_BYTES:
            errors.append(f"{prefix} file size {actual_size} exceeds official 5 MiB limit")

        declared_sha = str(asset.get("sha256") or "").lower()
        actual_sha = _sha256(path)
        if len(declared_sha) != 64 or any(c not in "0123456789abcdef" for c in declared_sha):
            errors.append(f"{prefix} sha256 must be 64 lowercase hexadecimal characters")
        if declared_sha != actual_sha:
            errors.append(f"{prefix} SHA-256 mismatch: manifest={declared_sha or 'missing'} actual={actual_sha}")
        hash_for_name = declared_sha if len(declared_sha) >= 8 else actual_sha
        expected_hash_suffix = f"-{hash_for_name[:8]}"
        if not path.stem.endswith(expected_hash_suffix):
            errors.append(
                f"{prefix} filename must end with {expected_hash_suffix}{path.suffix} for SHA/name consistency"
            )

        if asset_type == "lottie":
            media_errors, media = _validate_lottie(asset_id, asset, path)
        else:
            try:
                probe = probe_runner(path)
            except Exception as exc:  # validation boundary: report, don't hide details
                errors.append(f"{prefix} could not inspect media: {exc}")
                continue
            media_errors, media = _validate_probed_media(asset_id, asset, probe)
        errors.extend(media_errors)
        if not media:
            continue

        declared_width = _int(asset.get("width"))
        declared_height = _int(asset.get("height"))
        declared_fps = _float(asset.get("fps"))
        declared_duration = _int(asset.get("durationMs"))
        actual_duration_ms = int(round(media["duration"] * 1000))

        if declared_width != media["width"]:
            errors.append(f"{prefix} width={declared_width} does not match media width {media['width']}")
        if declared_height != media["height"]:
            errors.append(f"{prefix} height={declared_height} does not match media height {media['height']}")
        if not math.isclose(declared_fps, media["fps"], abs_tol=FPS_TOLERANCE):
            errors.append(f"{prefix} fps={declared_fps:g} does not match media FPS {media['fps']:.3f}")
        if abs(declared_duration - actual_duration_ms) > DURATION_TOLERANCE_MS:
            errors.append(
                f"{prefix} durationMs={declared_duration} does not match media duration {actual_duration_ms}ms"
            )

    return errors


def _print_asset_summary(repo_root: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(
        f"Catalog OK: schema={manifest.get('schema')} revision={manifest.get('revision')} "
        f"assets={len(manifest.get('assets', {}))} entries={len(manifest.get('entries', []))}"
    )
    for asset_id, asset in manifest.get("assets", {}).items():
        path = repo_root / asset["path"]
        print(
            f"  ✓ {asset_id}: {asset['type']} {asset.get('width')}x{asset.get('height')} "
            f"{asset.get('fps')}fps {asset.get('durationMs')}ms {path.stat().st_size} bytes "
            f"sha256={_sha256(path)}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MiSpotify Motion Covers catalog and media")
    parser.add_argument(
        "manifest",
        nargs="?",
        default="catalog/v1/manifest.json",
        help="Manifest path relative to repository root (default: catalog/v1/manifest.json)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory)",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = root / manifest

    errors = validate_catalog(root, manifest)
    if errors:
        print(f"Motion Cover validation FAILED with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1

    _print_asset_summary(root, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
