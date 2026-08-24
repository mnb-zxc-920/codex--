#!/usr/bin/env python3
"""Build fixed-size, binary-alpha Tk fallback assets for V0.7 skins."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


DISPLAY_SIZE = (152, 152)
ALPHA_THRESHOLD = 104
SKINS: dict[str, dict[str, object]] = {
    "deepseek-whale": {
        "normal": "DSniang1.png",
        "stunned": "DSniang1-stunned.png",
        "idleRoot": "idle-variants",
        "idleFiles": (
            "whale-idle-phone-transparent-candidate-v1.png",
            "whale-idle-sleeping-transparent-candidate-v1.png",
            "whale-idle-snack-chips-transparent-candidate-v1.png",
            "whale-idle-snack-cola-transparent-candidate-v1.png",
            "whale-idle-snack-rice-transparent-candidate-v1.png",
            "whale-idle-snack-spicy-strip-transparent-candidate-v1.png",
            "whale-idle-snack-token-transparent-candidate-v1.png",
        ),
    },
    "endfield-yu": {
        "normal": "skins/endfield-yu/mint-horned-default-chibi-transparent-candidate-v2.png",
        "stunned": "skins/endfield-yu/mint-horned-bump-x-eyes-transparent-candidate-v1.png",
        "idleRoot": "skins/endfield-yu",
        "idleFiles": (
            "mint-horned-idle-phone-transparent-candidate-v1.png",
            "mint-horned-idle-sleeping-transparent-candidate-v1.png",
            "mint-horned-idle-snack-chips-transparent-candidate-v1.png",
            "mint-horned-idle-snack-cola-transparent-candidate-v1.png",
            "mint-horned-idle-snack-rice-transparent-candidate-v1.png",
            "mint-horned-idle-snack-spicy-strip-transparent-candidate-v1.png",
            "mint-horned-idle-snack-token-transparent-candidate-v1.png",
        ),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _prepare(source: Path, target: Path, assets_root: Path) -> dict[str, object]:
    with Image.open(source) as opened:
        rgba = opened.convert("RGBA").resize(DISPLAY_SIZE, Image.Resampling.LANCZOS)
    red, green, blue, alpha = rgba.split()
    binary_alpha = alpha.point(lambda value: 255 if value >= ALPHA_THRESHOLD else 0)
    opaque = Image.merge("RGBA", (red, green, blue, binary_alpha))
    transparent = Image.new("RGBA", DISPLAY_SIZE, (0, 0, 0, 0))
    safe = Image.composite(opaque, transparent, binary_alpha)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe.save(target, format="PNG", optimize=False, compress_level=9)
    return {
        "source": source.relative_to(assets_root).as_posix(),
        "sourceSha256": _sha256(source),
        "target": target.relative_to(assets_root).as_posix(),
        "targetSha256": _sha256(target),
        "size": list(safe.size),
        "alphaBBox": list(safe.getchannel("A").getbbox() or ()),
        "alphaExtrema": list(safe.getchannel("A").getextrema()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-root", type=Path, required=True)
    args = parser.parse_args()
    assets_root = args.assets_root.resolve()
    all_manifests: dict[str, object] = {}
    for skin_id, definition in SKINS.items():
        output_root = assets_root / "render-cache" / skin_id
        records: dict[str, object] = {}
        records["normal"] = _prepare(
            assets_root / str(definition["normal"]), output_root / "normal.png", assets_root
        )
        records["stunned"] = _prepare(
            assets_root / str(definition["stunned"]), output_root / "stunned.png", assets_root
        )
        idle_root = assets_root / str(definition["idleRoot"])
        for name in tuple(definition["idleFiles"]):
            records[f"idle:{name}"] = _prepare(
                idle_root / name, output_root / "idle" / name, assets_root
            )
        manifest = {
            "schemaVersion": "CodexWhaleDisplayAssetsV1",
            "skin": skin_id,
            "displaySize": list(DISPLAY_SIZE),
            "alphaThreshold": ALPHA_THRESHOLD,
            "records": records,
        }
        manifest_path = output_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        all_manifests[skin_id] = {
            "path": str(manifest_path),
            "sha256": _sha256(manifest_path),
            "records": len(records),
        }
    print(json.dumps({"ok": True, "skins": all_manifests}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
