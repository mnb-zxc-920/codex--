#!/usr/bin/env python3
"""Run reproducible V0.7 validation and build a two-skin contact sheet."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "codex_whale_v0.py"
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "validation" / "v0.7"
PYTHONS = {
    "python314": ["py", "-3.14"],
    "python312": ["py", "-3.12"],
}
STATE_LABELS = (
    ("normal", "normal"),
    ("stunned", "stunned"),
    ("phone", "phone"),
    ("sleeping", "sleep"),
    ("chips", "chips"),
    ("cola", "cola"),
    ("rice", "rice"),
    ("spicy-strip", "spicy"),
    ("token", "token"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_json(label: str, command: list[str], timeout: float) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    parsed: dict[str, Any]
    try:
        parsed = json.loads(stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        parsed = {"ok": False, "parseError": True, "stdout": stdout}
    record = {
        "label": label,
        "command": command,
        "exitCode": completed.returncode,
        "wallMs": round(elapsed_ms, 3),
        "stderr": stderr,
        "result": parsed,
    }
    write_json(OUTPUT / f"{label}.json", record)
    return record


def font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


def checkerboard(size: tuple[int, int], tile: int = 12) -> Image.Image:
    canvas = Image.new("RGBA", size, (248, 250, 253, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle(
                    (x, y, min(x + tile - 1, size[0] - 1), min(y + tile - 1, size[1] - 1)),
                    fill=(226, 231, 239, 255),
                )
    return canvas


def match_record(records: dict[str, Any], token: str) -> dict[str, Any]:
    if token in ("normal", "stunned"):
        return records[token]
    matches = [value for key, value in records.items() if key.startswith("idle:") and token in key]
    if len(matches) != 1:
        raise ValueError(f"state token {token!r} matched {len(matches)} records")
    return matches[0]


def audit_assets() -> dict[str, Any]:
    sheet_cell = (170, 190)
    sheet = Image.new(
        "RGBA",
        (28 + len(STATE_LABELS) * sheet_cell[0], 72 + 2 * sheet_cell[1]),
        (244, 247, 252, 255),
    )
    draw = ImageDraw.Draw(sheet)
    title_font = font(22)
    label_font = font(13)
    draw.text((18, 14), "Codex Whale V0.7 - two-skin render audit", fill="#17274f", font=title_font)
    skin_audits: dict[str, Any] = {}
    for row, skin_id in enumerate(("deepseek-whale", "endfield-yu")):
        manifest_path = ASSETS / "render-cache" / skin_id / "manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        records = manifest["records"]
        state_audits: dict[str, Any] = {}
        for column, (token, label) in enumerate(STATE_LABELS):
            record = match_record(records, token)
            target = ASSETS / record["target"]
            with Image.open(target) as opened:
                rgba = opened.convert("RGBA")
            alpha_channel = rgba.getchannel("A")
            alpha_values = set(alpha_channel.get_flattened_data())
            state_audits[label] = {
                "path": record["target"],
                "sha256": sha256(target),
                "size": list(rgba.size),
                "binaryAlpha": alpha_values <= {0, 255},
                "alphaBBox": list(rgba.getchannel("A").getbbox() or ()),
            }
            x = 18 + column * sheet_cell[0]
            y = 62 + row * sheet_cell[1]
            background = checkerboard((152, 152))
            background.alpha_composite(rgba, (0, 0))
            sheet.alpha_composite(background, (x, y))
            draw.text((x + 2, y + 157), label, fill="#24345e", font=label_font)
        skin_audits[skin_id] = {
            "manifest": manifest_path.relative_to(ROOT).as_posix(),
            "manifestSha256": sha256(manifest_path),
            "containsAbsoluteUserPath": "C:\\Users\\" in manifest_text,
            "states": state_audits,
        }
    sheet_path = OUTPUT / "skins-contact-sheet.png"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(sheet_path, format="PNG", optimize=False, compress_level=9)

    audio_paths = (
        ASSETS / "Ya1.mp3",
        ASSETS / "Ya2.mp3",
        ASSETS / "sounds" / "soft-pop.wav",
        ASSETS / "sounds" / "crystal-chime.wav",
        ASSETS / "sounds" / "wood-tap.wav",
    )
    audio: dict[str, Any] = {}
    for path in audio_paths:
        record: dict[str, Any] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as stream:
                record.update(
                    {
                        "channels": stream.getnchannels(),
                        "sampleWidth": stream.getsampwidth(),
                        "sampleRate": stream.getframerate(),
                        "frames": stream.getnframes(),
                        "durationSeconds": round(
                            stream.getnframes() / stream.getframerate(), 6
                        ),
                    }
                )
        audio[path.relative_to(ASSETS).as_posix()] = record

    audit = {
        "ok": all(
            not skin["containsAbsoluteUserPath"]
            and len(skin["states"]) == 9
            and all(
                state["size"] == [152, 152]
                and state["binaryAlpha"]
                and bool(state["alphaBBox"])
                for state in skin["states"].values()
            )
            for skin in skin_audits.values()
        ),
        "skins": skin_audits,
        "audio": audio,
        "contactSheet": {
            "path": sheet_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(sheet_path),
        },
    }
    write_json(OUTPUT / "asset-audit.json", audit)
    return audit


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command_records: dict[str, Any] = {}
    for python_label, prefix in PYTHONS.items():
        command_records[f"{python_label}-self-test"] = run_json(
            f"{python_label}-self-test",
            [*prefix, str(SOURCE), "--self-test"],
            timeout=30,
        )
        command_records[f"{python_label}-qa"] = run_json(
            f"{python_label}-qa",
            [*prefix, str(SOURCE), "--qa-report"],
            timeout=75,
        )
    asset_audit = audit_assets()
    qa_results = [
        command_records[f"{label}-qa"]["result"] for label in PYTHONS
    ]
    summary = {
        "schemaVersion": "CodexWhaleValidationV0_7",
        "ok": (
            asset_audit["ok"]
            and all(
                record["exitCode"] == 0 and bool(record["result"].get("ok"))
                for record in command_records.values()
            )
            and all(
                result["sounds"]["submissionNonblocking"]
                and result["sounds"]["queueDrops"] == 0
                and result["edgeBounce"]["collisionFrameMs"] < 16.0
                and result["idleVariants"]["switchNonblocking"]
                for result in qa_results
            )
        ),
        "commands": {
            label: {
                "exitCode": record["exitCode"],
                "wallMs": record["wallMs"],
                "ok": bool(record["result"].get("ok")),
                "receipt": f"validation/v0.7/{label}.json",
            }
            for label, record in command_records.items()
        },
        "performance": {
            label: {
                "collisionFrameMs": result["edgeBounce"]["collisionFrameMs"],
                "collisionSubmissionMs": result["sounds"]["collisionSubmissionMs"],
                "clickSubmissionMs": result["sounds"]["clickSubmissionMs"],
                "maxIdleSwitchMs": max(
                    item["activationMs"]
                    for item in result["idleVariants"]["records"].values()
                ),
                "queueDrops": result["sounds"]["queueDrops"],
            }
            for label, result in zip(PYTHONS, qa_results)
        },
        "assetAudit": "validation/v0.7/asset-audit.json",
        "contactSheet": asset_audit["contactSheet"],
    }
    write_json(OUTPUT / "validation-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
