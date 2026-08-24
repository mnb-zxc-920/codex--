#!/usr/bin/env python3
"""Deterministically build the three original V0.7 interaction sounds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path
from typing import Callable


SAMPLE_RATE = 44_100
TARGET_PEAK = 0.82


def _envelope(index: int, count: int, attack: float, release: float) -> float:
    elapsed = index / SAMPLE_RATE
    duration = count / SAMPLE_RATE
    attack_gain = min(1.0, elapsed / max(attack, 1 / SAMPLE_RATE))
    release_gain = min(1.0, max(0.0, duration - elapsed) / max(release, 1 / SAMPLE_RATE))
    return attack_gain * release_gain


def _soft_pop(t: float) -> float:
    duration = 0.29
    progress = min(1.0, t / duration)
    frequency = 430.0 * ((175.0 / 430.0) ** progress)
    phase = 2.0 * math.pi * frequency * t
    body = math.sin(phase) + 0.28 * math.sin(phase * 2.02)
    return body * math.exp(-7.8 * t)


def _crystal_chime(t: float) -> float:
    first = math.sin(2.0 * math.pi * 1046.5 * t) * math.exp(-5.1 * t)
    second = math.sin(2.0 * math.pi * 1567.98 * t + 0.15) * math.exp(-7.2 * t)
    shimmer = math.sin(2.0 * math.pi * 2093.0 * t + 0.3) * math.exp(-10.5 * t)
    return first + 0.52 * second + 0.22 * shimmer


def _wood_tap(t: float) -> float:
    # The inharmonic sine cluster gives a dry wooden transient without sampled audio.
    transient = (
        math.sin(2.0 * math.pi * 184.0 * t)
        + 0.58 * math.sin(2.0 * math.pi * 317.0 * t + 0.4)
        + 0.31 * math.sin(2.0 * math.pi * 511.0 * t + 1.1)
    ) * math.exp(-24.0 * t)
    click = math.sin(2.0 * math.pi * 1733.0 * t) * math.exp(-82.0 * t)
    return transient + 0.19 * click


SOUNDS: tuple[tuple[str, float, float, float, Callable[[float], float]], ...] = (
    ("soft-pop.wav", 0.29, 0.006, 0.045, _soft_pop),
    ("crystal-chime.wav", 0.72, 0.004, 0.090, _crystal_chime),
    ("wood-tap.wav", 0.24, 0.002, 0.035, _wood_tap),
)


def _render_sound(
    path: Path,
    duration: float,
    attack: float,
    release: float,
    generator: Callable[[float], float],
) -> dict[str, object]:
    count = round(duration * SAMPLE_RATE)
    samples = [
        generator(index / SAMPLE_RATE) * _envelope(index, count, attack, release)
        for index in range(count)
    ]
    source_peak = max(abs(sample) for sample in samples) or 1.0
    gain = TARGET_PEAK / source_peak
    pcm = b"".join(
        struct.pack("<h", round(max(-1.0, min(sample * gain, 1.0)) * 32767))
        for sample in samples
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(pcm)
    payload = path.read_bytes()
    return {
        "name": path.name,
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "sampleWidthBytes": 2,
        "frames": count,
        "durationSeconds": round(count / SAMPLE_RATE, 6),
        "peak": TARGET_PEAK,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    report = [
        _render_sound(output_dir / name, duration, attack, release, generator)
        for name, duration, attack, release, generator in SOUNDS
    ]
    print(json.dumps({"ok": True, "sounds": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
