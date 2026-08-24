#!/usr/bin/env python3
"""Codex Whale desktop widget V0.7.

This is a standalone, read-only desktop widget. It does not modify Codex
threads, account settings, the native /pets feature, or any repository.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import queue
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


APP_NAME = "Codex 小鲸鱼 V0.7"
APP_VERSION = "0.7.0"
APP_RUN_VALUE = "CodexWhaleWidgetV01"
BUBBLE_MS = 5000
FOLLOW_INTERVAL_MS = 16
FOLLOW_RAMP_SECONDS = 1.6
FOLLOW_ACCELERATION_OPTIONS = (4800, 7200, 9600, 12800)
FOLLOW_ACCELERATION_DEFAULT = 9600
FOLLOW_MAX_SPEED = 1600.0
FOLLOW_BOUNCE_THRESHOLD = 620.0
PHYSICS_REBOUND_MIN = 1.05
PHYSICS_REBOUND_MAX = 1.42
PHYSICS_STUN_RESTITUTION = 0.88
PHYSICS_TANGENTIAL_RETENTION = 0.98
PHYSICS_FREE_FLIGHT_DRAG = 0.28
PHYSICS_FREE_FLIGHT_MAX_SPEED = 2600.0
PHYSICS_STUN_BOUNCE_MIN = 45.0
THROW_SAMPLE_WINDOW_SECONDS = 0.16
THROW_MIN_SPEED = 80.0
THROW_STOP_SPEED = 24.0
THROW_FREE_FLIGHT_DRAG = 1.35
STUN_DURATION_OPTIONS = (800, 1400, 2200, 3200)
STUN_DURATION_DEFAULT = 1400
COLLISION_SOUND_COOLDOWN_MS = 550
DISPLAY_ALPHA_THRESHOLD = 104
WHALE_SOURCE_SIZE = (610, 610)
WHALE_ALPHA_BOUNDS = (45, 10, 610, 610)
WHALE_STUNNED_ALPHA_BOUNDS = (46, 9, 610, 610)
PET_BASE_SIZE = (152, 152)
WORKING_SOURCE_PX = 400
ABSOLUTE_PRESET_LIMIT = 3
IDLE_VARIANT_SECONDS = 5 * 60
WHALE_IDLE_VARIANT_FILES = (
    "whale-idle-phone-transparent-candidate-v1.png",
    "whale-idle-sleeping-transparent-candidate-v1.png",
    "whale-idle-snack-chips-transparent-candidate-v1.png",
    "whale-idle-snack-cola-transparent-candidate-v1.png",
    "whale-idle-snack-rice-transparent-candidate-v1.png",
    "whale-idle-snack-spicy-strip-transparent-candidate-v1.png",
    "whale-idle-snack-token-transparent-candidate-v1.png",
)
YU_IDLE_VARIANT_FILES = (
    "mint-horned-idle-phone-transparent-candidate-v1.png",
    "mint-horned-idle-sleeping-transparent-candidate-v1.png",
    "mint-horned-idle-snack-chips-transparent-candidate-v1.png",
    "mint-horned-idle-snack-cola-transparent-candidate-v1.png",
    "mint-horned-idle-snack-rice-transparent-candidate-v1.png",
    "mint-horned-idle-snack-spicy-strip-transparent-candidate-v1.png",
    "mint-horned-idle-snack-token-transparent-candidate-v1.png",
)
DEFAULT_SKIN_ID = "deepseek-whale"
SKIN_DEFINITIONS: dict[str, dict[str, Any]] = {
    DEFAULT_SKIN_ID: {
        "label": "DeepSeek 小鲸鱼",
        "bubbleTitle": "CODEX · 小鲸鱼",
        "normal": "DSniang1.png",
        "stunned": "DSniang1-stunned.png",
        "idleRoot": "idle-variants",
        "idleFiles": WHALE_IDLE_VARIANT_FILES,
    },
    "endfield-yu": {
        "label": "终末地 · 祀（非官方同人）",
        "bubbleTitle": "CODEX · 祀",
        "normal": "skins/endfield-yu/mint-horned-default-chibi-transparent-candidate-v2.png",
        "stunned": "skins/endfield-yu/mint-horned-bump-x-eyes-transparent-candidate-v1.png",
        "idleRoot": "skins/endfield-yu",
        "idleFiles": YU_IDLE_VARIANT_FILES,
    },
}
SKIN_IDS = tuple(SKIN_DEFINITIONS)
DEFAULT_SOUND_PROFILE = "duck"
SOUND_PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    DEFAULT_SOUND_PROFILE: {
        "label": "塑料鸭（默认）",
        "files": ("Ya1.mp3", "Ya2.mp3"),
        "sequenceDelayMs": 115,
    },
    "soft-pop": {
        "label": "软萌啵",
        "files": ("sounds/soft-pop.wav",),
        "sequenceDelayMs": 0,
    },
    "crystal-chime": {
        "label": "水晶叮",
        "files": ("sounds/crystal-chime.wav",),
        "sequenceDelayMs": 0,
    },
    "wood-tap": {
        "label": "木质嗒",
        "files": ("sounds/wood-tap.wav",),
        "sequenceDelayMs": 0,
    },
}
SOUND_PROFILE_IDS = tuple(SOUND_PROFILE_DEFINITIONS)
SOUND_VOLUME_OPTIONS = (0, 25, 50, 75, 100)
CLICK_DEFORMATION_FRAMES = (
    (0, 1.10, 0.88),
    (70, 0.97, 1.04),
    (140, 1.03, 0.98),
    (215, 1.00, 1.00),
)
SCALE_MIN = 0.5
SCALE_MAX = 2.2
SCALE_PERCENT_OPTIONS = (50, 75, 100, 125, 150, 175, 200, 220)
POLL_SECONDS = 5
RATE_LIMIT_REFRESH_SECONDS = 60
RECENT_THREAD_LIMIT = 12
LONG_RUNNING_SECONDS = 30 * 60
LIFECYCLE_EVENTS = {"task_started", "task_complete", "turn_aborted"}
STATUS_DOT_COLORS = {
    "working": "#f4b942",
    "idle": "#42b983",
    "attention": "#ef6c5b",
    "unknown": "#9aa4b5",
}
MENU_LABELS = (
    "拖拽甩出",
    "跟随鼠标",
    "固定位置",
    "固定屏幕绝对位置",
    "绝对位置预设",
    "窗口置顶",
    "调整大小",
    "更换皮肤",
    "声音设置",
    "开机自启动",
    "检查更新",
    "关于作者",
    "退出程序",
)
FOLLOW_SUBMENU_LABELS = (
    "启用跟随鼠标",
    "跟随加速度上限",
    "启用物理碰撞引擎",
    "撞晕时长",
)
DEFAULT_SETTINGS: dict[str, Any] = {
    "throwMode": False,
    "followMouse": False,
    "fixedPosition": True,
    "absolutePosition": False,
    "absolutePresets": [None] * ABSOLUTE_PRESET_LIMIT,
    "activeAbsolutePreset": None,
    "followAccelerationLimit": FOLLOW_ACCELERATION_DEFAULT,
    "physicsEnabled": True,
    "stunDurationMs": STUN_DURATION_DEFAULT,
    "topmost": True,
    "scale": 1.0,
    "skin": DEFAULT_SKIN_ID,
    "soundProfile": DEFAULT_SOUND_PROFILE,
    "soundVolume": 100,
    "position": None,
}


def _clamp_scale(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        return 1.0
    return round(max(SCALE_MIN, min(numeric, SCALE_MAX)), 2)


def _scale_from_percent(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    return _clamp_scale(float(value) / 100.0)


def _normalize_skin(value: Any) -> str:
    return value if isinstance(value, str) and value in SKIN_DEFINITIONS else DEFAULT_SKIN_ID


def _normalize_sound_profile(value: Any) -> str:
    return (
        value
        if isinstance(value, str) and value in SOUND_PROFILE_DEFINITIONS
        else DEFAULT_SOUND_PROFILE
    )


def _normalize_sound_volume(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 100
    numeric = float(value)
    if not math.isfinite(numeric):
        return 100
    clamped = max(0.0, min(numeric, 100.0))
    return min(SOUND_VOLUME_OPTIONS, key=lambda candidate: abs(candidate - clamped))


def _normalize_acceleration_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return FOLLOW_ACCELERATION_DEFAULT
    numeric = float(value)
    if not math.isfinite(numeric):
        return FOLLOW_ACCELERATION_DEFAULT
    return min(FOLLOW_ACCELERATION_OPTIONS, key=lambda candidate: abs(candidate - numeric))


def _normalize_stun_duration(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return STUN_DURATION_DEFAULT
    numeric = float(value)
    if not math.isfinite(numeric):
        return STUN_DURATION_DEFAULT
    return min(STUN_DURATION_OPTIONS, key=lambda candidate: abs(candidate - numeric))


def _impact_rebound_multiplier(normal_speed: float) -> float:
    speed = max(0.0, float(normal_speed))
    span = max(1.0, FOLLOW_MAX_SPEED - FOLLOW_BOUNCE_THRESHOLD)
    ratio = max(0.0, min((speed - FOLLOW_BOUNCE_THRESHOLD) / span, 1.0))
    shaped = ratio ** 0.72
    return PHYSICS_REBOUND_MIN + (PHYSICS_REBOUND_MAX - PHYSICS_REBOUND_MIN) * shaped


def _throw_velocity_from_samples(
    samples: Iterable[tuple[float, float, float]],
) -> tuple[float, float]:
    points = list(samples)
    if len(points) < 2:
        return 0.0, 0.0
    newest_at = float(points[-1][0])
    recent = [
        (float(at), float(x), float(y))
        for at, x, y in points
        if newest_at - float(at) <= THROW_SAMPLE_WINDOW_SECONDS
    ]
    if len(recent) < 2:
        recent = [
            (float(points[-2][0]), float(points[-2][1]), float(points[-2][2])),
            (float(points[-1][0]), float(points[-1][1]), float(points[-1][2])),
        ]
    elapsed = recent[-1][0] - recent[0][0]
    if elapsed <= 0.001:
        return 0.0, 0.0
    vx = (recent[-1][1] - recent[0][1]) / elapsed
    vy = (recent[-1][2] - recent[0][2]) / elapsed
    speed = math.hypot(vx, vy)
    if speed > PHYSICS_FREE_FLIGHT_MAX_SPEED:
        factor = PHYSICS_FREE_FLIGHT_MAX_SPEED / speed
        vx, vy = vx * factor, vy * factor
    return vx, vy


def _normalize_absolute_preset(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    position = value.get("position")
    scale = value.get("scale")
    if (
        not isinstance(position, list)
        or len(position) != 2
        or not all(isinstance(coordinate, int) and not isinstance(coordinate, bool) for coordinate in position)
        or not isinstance(scale, (int, float))
        or isinstance(scale, bool)
    ):
        return None
    return {"position": [position[0], position[1]], "scale": _clamp_scale(float(scale))}


def _widget_root() -> Path:
    return Path(__file__).resolve().parent


def _settings_path() -> Path:
    return _widget_root() / "settings-v0.1.json"


def _normalize_settings(raw: Any) -> dict[str, Any]:
    settings = {
        **DEFAULT_SETTINGS,
        "absolutePresets": [None] * ABSOLUTE_PRESET_LIMIT,
    }
    if not isinstance(raw, dict):
        return settings
    settings["throwMode"] = bool(raw.get("throwMode", False))
    settings["followMouse"] = bool(raw.get("followMouse", False))
    settings["fixedPosition"] = bool(raw.get("fixedPosition", True))
    settings["absolutePosition"] = bool(raw.get("absolutePosition", False))
    if settings["throwMode"]:
        settings["followMouse"] = False
        settings["fixedPosition"] = False
        settings["absolutePosition"] = False
    elif settings["followMouse"]:
        settings["fixedPosition"] = False
        settings["absolutePosition"] = False
    elif settings["absolutePosition"]:
        settings["fixedPosition"] = False
    settings["followAccelerationLimit"] = _normalize_acceleration_limit(
        raw.get("followAccelerationLimit")
    )
    settings["physicsEnabled"] = bool(raw.get("physicsEnabled", True))
    settings["stunDurationMs"] = _normalize_stun_duration(raw.get("stunDurationMs"))
    presets = raw.get("absolutePresets")
    if isinstance(presets, list):
        normalized_presets = [
            _normalize_absolute_preset(value)
            for value in presets[:ABSOLUTE_PRESET_LIMIT]
        ]
        normalized_presets.extend([None] * (ABSOLUTE_PRESET_LIMIT - len(normalized_presets)))
        settings["absolutePresets"] = normalized_presets
    active_preset = raw.get("activeAbsolutePreset")
    if (
        isinstance(active_preset, int)
        and not isinstance(active_preset, bool)
        and 0 <= active_preset < ABSOLUTE_PRESET_LIMIT
        and settings["absolutePosition"]
        and settings["absolutePresets"][active_preset] is not None
    ):
        settings["activeAbsolutePreset"] = active_preset
    settings["topmost"] = bool(raw.get("topmost", True))
    scale = raw.get("scale")
    settings["scale"] = (
        _clamp_scale(float(scale))
        if isinstance(scale, (int, float)) and not isinstance(scale, bool)
        else 1.0
    )
    settings["skin"] = _normalize_skin(raw.get("skin"))
    settings["soundProfile"] = _normalize_sound_profile(raw.get("soundProfile"))
    settings["soundVolume"] = _normalize_sound_volume(raw.get("soundVolume"))
    position = raw.get("position")
    if (
        isinstance(position, list)
        and len(position) == 2
        and all(isinstance(value, int) for value in position)
    ):
        settings["position"] = position
    return settings


def _load_settings(path: Path | None = None) -> dict[str, Any]:
    target = path or _settings_path()
    try:
        return _normalize_settings(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict[str, Any], path: Path | None = None) -> None:
    target = path or _settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_normalize_settings(settings), ensure_ascii=False, indent=2) + "\n"
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)


def _autostart_command() -> str:
    launcher = (_widget_root() / "Start-CodexWhale.ps1").resolve()
    return (
        'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass '
        f'-File "{launcher}"'
    )


def _autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            value, _ = winreg.QueryValueEx(key, APP_RUN_VALUE)
        return value == _autostart_command()
    except (FileNotFoundError, OSError):
        return False


def _set_autostart(enabled: bool) -> None:
    if os.name != "nt":
        raise RuntimeError("开机自启动仅支持 Windows")
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        key_path,
        0,
        winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(key, APP_RUN_VALUE, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_RUN_VALUE)
            except FileNotFoundError:
                pass


class AppServerError(RuntimeError):
    pass


def _compact_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".replace("\r", " ").replace("\n", " ")
    return text[:180]


def _find_codex() -> str:
    candidate = shutil.which("codex.exe") or shutil.which("codex")
    if not candidate:
        raise AppServerError("找不到 codex.exe，请先启动或安装 Codex")
    return candidate


class AppServerClient:
    """Minimal JSON-RPC client for the official local Codex App Server."""

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        self._next_id = 1
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._stderr_tail: list[str] = []
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [_find_codex(), "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-whale-v0",
                    "title": APP_NAME,
                    "version": APP_VERSION,
                },
                "capabilities": {},
            },
        )
        self.notify("initialized")

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = message.get("id")
            if isinstance(request_id, int):
                with self._lock:
                    waiter = self._pending.get(request_id)
                if waiter is not None:
                    waiter.put(message)

    def _read_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr_tail.append(line.strip())
            del self._stderr_tail[:-12]

    def _send(self, message: dict[str, Any]) -> None:
        if self.proc.poll() is not None:
            raise AppServerError(f"Codex App Server 已退出：{self.proc.returncode}")
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AppServerError("无法向 Codex App Server 发送只读请求") from exc

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            waiter: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = waiter
        try:
            message: dict[str, Any] = {"id": request_id, "method": method}
            if params is not None:
                message["params"] = params
            self._send(message)
            try:
                response = waiter.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise AppServerError(f"只读请求超时：{method}") from exc
            if "error" in response:
                err = response["error"]
                raise AppServerError(f"{method} 失败：{err}")
            return response.get("result")
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def close(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError):
            try:
                self.proc.kill()
            except OSError:
                pass

    def __enter__(self) -> "AppServerClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass(frozen=True)
class Lifecycle:
    event: str
    timestamp: str | None
    turn_id: str | None


@dataclass
class LifecycleCacheEntry:
    size: int
    lifecycle: Lifecycle | None


def _reverse_lines(path: Path, block_size: int = 64 * 1024) -> Iterable[bytes]:
    """Yield a file's lines from newest to oldest without loading it all."""
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        position = stream.tell()
        carry = b""
        while position > 0:
            read_size = min(block_size, position)
            position -= read_size
            stream.seek(position)
            carry = stream.read(read_size) + carry
            parts = carry.split(b"\n")
            carry = parts[0]
            for line in reversed(parts[1:]):
                if line:
                    yield line.rstrip(b"\r")
        if carry:
            yield carry.rstrip(b"\r")


def _parse_lifecycle_line(raw: bytes | str) -> Lifecycle | None:
    if isinstance(raw, bytes):
        if not any(marker.encode("ascii") in raw for marker in LIFECYCLE_EVENTS):
            return None
        text = raw.decode("utf-8", errors="replace")
    else:
        if not any(marker in raw for marker in LIFECYCLE_EVENTS):
            return None
        text = raw
    try:
        record = json.loads(text)
    except json.JSONDecodeError:
        return None
    if record.get("type") != "event_msg":
        return None
    payload = record.get("payload") or {}
    event = payload.get("type")
    if event not in LIFECYCLE_EVENTS:
        return None
    return Lifecycle(
        event=event,
        timestamp=record.get("timestamp"),
        turn_id=payload.get("turn_id"),
    )


class LifecycleCache:
    """Read only the bound rollout files returned by App Server."""

    def __init__(self) -> None:
        self._entries: dict[Path, LifecycleCacheEntry] = {}

    def observe(self, raw_path: str | None) -> tuple[Lifecycle | None, float | None]:
        if not raw_path:
            return None, None
        path = Path(raw_path)
        try:
            stat = path.stat()
        except OSError:
            return None, None
        cached = self._entries.get(path)
        if cached and stat.st_size == cached.size:
            return cached.lifecycle, stat.st_mtime

        lifecycle = cached.lifecycle if cached and stat.st_size >= cached.size else None
        if cached and stat.st_size >= cached.size:
            try:
                with path.open("rb") as stream:
                    stream.seek(cached.size)
                    appended = stream.read()
                for raw in appended.splitlines():
                    parsed = _parse_lifecycle_line(raw)
                    if parsed is not None:
                        lifecycle = parsed
            except OSError:
                pass
        else:
            try:
                lifecycle = next(
                    parsed
                    for raw in _reverse_lines(path)
                    if (parsed := _parse_lifecycle_line(raw)) is not None
                )
            except (StopIteration, OSError):
                lifecycle = None

        self._entries[path] = LifecycleCacheEntry(size=stat.st_size, lifecycle=lifecycle)
        return lifecycle, stat.st_mtime


def load_recent_threads(limit: int = RECENT_THREAD_LIMIT) -> list[dict[str, Any]]:
    """Read recent thread paths from Codex state SQLite in query-only mode."""
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    state_db = codex_home / "state_5.sqlite"
    if not state_db.is_file():
        raise RuntimeError(f"找不到 Codex 状态库：{state_db}")
    uri = state_db.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=1.5) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute(
            """
            SELECT id,
                   rollout_path AS path,
                   name,
                   title,
                   agent_nickname AS agentNickname,
                   created_at AS createdAt,
                   updated_at AS updatedAt,
                   recency_at AS recencyAt
              FROM threads
             WHERE archived = 0
             ORDER BY updated_at_ms DESC
             LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [dict(row) for row in rows]


def _safe_number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def normalize_rate_limits(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"available": False}
    reset_credit_count: int | None = None
    reset_credits = result.get("rateLimitResetCredits")
    if isinstance(reset_credits, dict):
        raw_count = reset_credits.get("availableCount")
        if (
            isinstance(raw_count, (int, float))
            and not isinstance(raw_count, bool)
            and math.isfinite(float(raw_count))
            and float(raw_count) >= 0
        ):
            reset_credit_count = int(raw_count)
    rate = result.get("rateLimits")
    if not isinstance(rate, dict):
        candidates = result.get("rateLimitsByLimitId")
        rate = candidates.get("codex") if isinstance(candidates, dict) else None
    if not isinstance(rate, dict):
        return {"available": False, "resetCreditCount": reset_credit_count}
    primary = rate.get("primary")
    if not isinstance(primary, dict):
        return {"available": False, "resetCreditCount": reset_credit_count}
    used = _safe_number(primary.get("usedPercent"))
    if used is None:
        return {"available": False, "resetCreditCount": reset_credit_count}
    used = min(100.0, max(0.0, used))
    reset = primary.get("resetsAt")
    return {
        "available": True,
        "remainingPercent": round(100.0 - used, 1),
        "usedPercent": round(used, 1),
        "windowMinutes": primary.get("windowDurationMins"),
        "resetsAt": reset if isinstance(reset, (int, float)) else None,
        "resetCreditCount": reset_credit_count,
        "planType": rate.get("planType"),
    }


def _thread_display_name(thread: dict[str, Any]) -> str | None:
    for key in ("name", "agentNickname"):
        value = thread.get(key)
        if isinstance(value, str) and value.strip():
            compact = " ".join(value.split())
            return compact if len(compact) <= 20 else compact[:19] + "…"
    title = thread.get("title")
    if isinstance(title, str) and title.strip() and not title.lstrip().startswith("<codex_delegation>"):
        compact = " ".join(title.split())
        return compact if len(compact) <= 20 else compact[:19] + "…"
    return None


def derive_task_status(
    threads: list[dict[str, Any]],
    cache: LifecycleCache,
    now: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    candidates = sorted(
        (t for t in threads if isinstance(t, dict)),
        key=lambda t: max(
            _safe_number(t.get("updatedAt")) or 0,
            _safe_number(t.get("recencyAt")) or 0,
            _safe_number(t.get("createdAt")) or 0,
        ),
        reverse=True,
    )[:RECENT_THREAD_LIMIT]

    active: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    inspected = 0
    for thread in candidates:
        lifecycle, modified_at = cache.observe(thread.get("path"))
        if lifecycle is None:
            continue
        inspected += 1
        item = {
            "threadId": thread.get("id"),
            "name": _thread_display_name(thread),
            "event": lifecycle.event,
            "turnId": lifecycle.turn_id,
            "eventAt": lifecycle.timestamp,
            "fileModifiedAt": modified_at,
        }
        if lifecycle.event == "task_started":
            age = now - modified_at if modified_at is not None else float("inf")
            item["longRunning"] = age > LONG_RUNNING_SECONDS
            active.append(item)
        elif lifecycle.event in {"task_complete", "turn_aborted"}:
            completed.append(item)

    if active:
        names = [item["name"] for item in active if item.get("name")]
        if len(names) == 1:
            detail = names[0]
        elif names:
            detail = " · ".join(names[:2])
        else:
            detail = "本机任务正在持续运行"
        return {
            "state": "working",
            "label": f"{len(active)} 个任务进行中",
            "detail": detail,
            "activeCount": len(active),
            "longRunningCount": sum(bool(item.get("longRunning")) for item in active),
            "inspectedCount": inspected,
        }
    if completed:
        return {
            "state": "idle",
            "label": "Codex 暂时空闲",
            "detail": "最近任务已结束",
            "activeCount": 0,
            "longRunningCount": 0,
            "inspectedCount": inspected,
        }
    return {
        "state": "unknown",
        "label": "任务状态不可用",
        "detail": "没有读到可验证的任务生命周期",
        "activeCount": 0,
        "longRunningCount": 0,
        "inspectedCount": inspected,
    }


class SnapshotReader:
    def __init__(self) -> None:
        self.cache = LifecycleCache()

    def read_once(self, client: AppServerClient | None = None) -> dict[str, Any]:
        owns_client = client is None
        if client is None:
            client = AppServerClient()
        try:
            threads = load_recent_threads()
            try:
                quota = normalize_rate_limits(client.request("account/rateLimits/read", {}))
            except Exception as exc:
                quota = {"available": False, "error": _compact_error(exc)}
            return {
                "ok": True,
                "capturedAt": int(time.time()),
                "quota": quota,
                "task": derive_task_status(threads, self.cache),
                "source": {
                    "quota": "account/rateLimits/read",
                    "threads": "state_5.sqlite(mode=ro) + bound rollout lifecycle",
                    "threadCount": len(threads),
                },
            }
        finally:
            if owns_client:
                client.close()


class SnapshotWorker(threading.Thread):
    def __init__(self, output: queue.Queue[dict[str, Any]], stop: threading.Event) -> None:
        super().__init__(daemon=True)
        self.output = output
        self.stop = stop
        self.reader = SnapshotReader()

    def run(self) -> None:
        client: AppServerClient | None = None
        last_quota: dict[str, Any] = {"available": False}
        next_quota_at = 0.0
        while not self.stop.is_set():
            try:
                now = time.time()
                if now >= next_quota_at:
                    try:
                        if client is None:
                            client = AppServerClient()
                        last_quota = normalize_rate_limits(
                            client.request("account/rateLimits/read", {})
                        )
                    except Exception as exc:
                        last_quota = {"available": False, "error": _compact_error(exc)}
                        if client is not None:
                            client.close()
                            client = None
                    next_quota_at = now + RATE_LIMIT_REFRESH_SECONDS
                threads = load_recent_threads()
                self.output.put(
                    {
                        "ok": True,
                        "capturedAt": int(now),
                        "quota": last_quota,
                        "task": derive_task_status(threads, self.reader.cache, now),
                        "source": {
                            "quota": "account/rateLimits/read",
                            "threads": "state_5.sqlite(mode=ro) + bound rollout lifecycle",
                            "threadCount": len(threads),
                        },
                    }
                )
            except Exception as exc:
                self.output.put(
                    {
                        "ok": False,
                        "capturedAt": int(time.time()),
                        "error": _compact_error(exc),
                        "quota": {"available": False},
                        "task": {
                            "state": "unknown",
                            "label": "Codex 状态不可用",
                            "detail": "只读入口暂时无法连接",
                        },
                    }
                )
            self.stop.wait(POLL_SECONDS)
        if client is not None:
            client.close()


def _format_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "--"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _format_reset(timestamp: Any) -> str:
    if not isinstance(timestamp, (int, float)):
        return "重置时间未知"


def _format_reset_credit_count(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= 0:
        return f"重置卡 {int(value)} 张"
    return "重置卡数量不可用"
    try:
        return datetime.fromtimestamp(timestamp).strftime("%m-%d %H:%M 重置")
    except (OSError, OverflowError, ValueError):
        return "重置时间未知"


def _single_instance() -> object | None:
    if os.name != "nt":
        return object()
    try:
        import ctypes

        handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\CodexWhaleDesktopWidgetV0")
        if not handle or ctypes.windll.kernel32.GetLastError() == 183:
            return None
        return handle
    except Exception:
        return object()


class WhaleWidget:
    TRANSPARENT = "#ff00fe"
    BASE_WIDTH = 430
    BASE_HEIGHT = 300

    def __init__(self, smoke_seconds: float | None = None, qa_mode: bool = False) -> None:
        import tkinter as tk

        self.tk = tk
        self.qa_mode = qa_mode
        self.settings = _load_settings()
        self.scale = float(self.settings["scale"])
        self._active_skin_id = _normalize_skin(self.settings.get("skin"))
        self._latest_snapshot: dict[str, Any] | None = None
        self._bubble_visible = False
        self._bubble_scale = 1.0
        self._bubble_after_ids: list[str] = []
        self._bubble_stage_history: list[float] = []
        self._click_generation = 0
        self._click_count = 0
        self._click_deformation_history: list[tuple[float, float]] = []
        self._whale_stretch = (1.0, 1.0)
        self._press_active = False
        self._drag_moved = False
        self._drag_origin = (0, 0)
        self._window_origin = (0, 0)
        self._throw_dragging = False
        self._throw_active = False
        self._throw_position = [0.0, 0.0]
        self._throw_velocity = [0.0, 0.0]
        self._throw_last_tick: float | None = None
        self._throw_samples: list[tuple[float, float, float]] = []
        self._throw_history: list[dict[str, Any]] = []
        self._follow_paused = False
        self._follow_position = [0.0, 0.0]
        self._follow_velocity = [0.0, 0.0]
        self._follow_last_tick: float | None = None
        self._follow_target: tuple[float, float] | None = None
        self._follow_cycle_started = 0.0
        self._follow_cycle_active = False
        self._follow_last_speed = 0.0
        self._follow_last_ramp = 0.0
        self._follow_last_acceleration = 0.0
        self._collision_count = 0
        self._collision_sound_count = 0
        self._collision_last_sound_at: float | None = None
        self._collision_history: list[dict[str, Any]] = []
        self._stunned = False
        self._stun_started_at: float | None = None
        self._stun_until = 0.0
        self._stun_history: list[dict[str, Any]] = []
        self._last_rebound_multiplier = 0.0
        self._scale_save_timer: str | None = None
        self._window_handle: int | None = None
        self._audio_aliases: set[str] = set()
        self._collision_audio_alias: str | None = None
        self._click_audio_aliases: tuple[str, ...] = ()
        self._collision_audio_path: Path | None = None
        self._collision_audio_ready = False
        self._collision_audio_prepare_ms = 0.0
        self._audio_profile_generation = 0
        self._audio_profile_ready = threading.Event()
        self._audio_queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=64)
        self._audio_state_lock = threading.Lock()
        self._audio_worker_results: list[dict[str, Any]] = []
        self._audio_submit_dropped = 0
        self._audio_accepting = True
        self._audio_thread = threading.Thread(
            target=self._audio_worker,
            name="codex-whale-audio",
            daemon=True,
        )
        self._audio_thread.start()
        self._last_dialog: tuple[str, str] | None = None
        self._last_whale_translucent_pixels = 0
        self._last_whale_magenta_pixels = 0
        self._last_whale_alpha_bbox: tuple[int, int, int, int] | None = None
        self._last_whale_render_size: tuple[int, int] | None = None
        self._rendered_whale_state = "normal"
        self._whale_image_cache: dict[tuple[str, float, float, float], dict[str, Any]] = {}
        self._last_whale_cache_hit = False
        self._collision_visual_prewarmed = False
        self._collision_visual_prewarm_ms = 0.0
        self._last_stun_visual_switch_ms = 0.0
        self._active_idle_variant: str | None = None
        self._last_idle_variant: str | None = None
        self._idle_variant_history: list[dict[str, Any]] = []
        self._last_interaction_at = time.monotonic()
        self._next_idle_variant_at = self._last_interaction_at + IDLE_VARIANT_SECONDS

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", bool(self.settings["topmost"]))
        self.root.configure(bg=self.TRANSPARENT)
        try:
            self.root.wm_attributes("-transparentcolor", self.TRANSPARENT)
        except tk.TclError:
            pass
        self.root.geometry(self._initial_geometry())
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self._raw_whale_image: Any | None = None
        self._raw_stunned_image: Any | None = None
        self._raw_idle_images: dict[str, Any] = {}
        self._pil_image_module: Any | None = None
        self._pil_imagetk_module: Any | None = None
        self._pil_whale_source: Any | None = None
        self._pil_stunned_source: Any | None = None
        self._pil_idle_sources: dict[str, Any] = {}
        self._idle_asset_paths: dict[str, Path] = {}
        self._raw_alpha_bounds: dict[str, tuple[int, int, int, int]] = {}
        self._load_skin_assets(self._active_skin_id)
        self._draw_static()
        self._prepare_collision_audio()
        self.root.update_idletasks()
        saved_position = self.settings.get("position")
        if isinstance(saved_position, list) and len(saved_position) == 2:
            restored_x, restored_y = self._clamp_position(*saved_position)
            self._place_window(restored_x, restored_y, include_size=True)
            self.root.update_idletasks()
        self._bind_actions()
        self._reset_follow_state()
        self._reset_throw_state()

        self.output: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stop = threading.Event()
        self.worker: SnapshotWorker | None = None
        if qa_mode:
            self._render(
                {
                    "task": {
                        "state": "idle",
                        "label": "Codex 暂时空闲",
                        "detail": "V0.7 本机交互验收",
                    },
                    "quota": {
                        "available": True,
                        "remainingPercent": 66.0,
                        "resetCreditCount": 1,
                    },
                }
            )
        else:
            self.worker = SnapshotWorker(self.output, self.stop)
            self.worker.start()
            self.root.after(150, self._drain_updates)
        self.root.after(FOLLOW_INTERVAL_MS, self._follow_tick)
        self.root.after(1000, self._idle_variant_tick)
        if smoke_seconds is not None:
            self.root.after(max(1, int(smoke_seconds * 1000)), self.close)

    @property
    def width(self) -> int:
        return max(1, int(round(self.BASE_WIDTH * self.scale)))

    @property
    def height(self) -> int:
        return max(1, int(round(self.BASE_HEIGHT * self.scale)))

    def _s(self, value: float) -> int:
        return int(round(value * self.scale))

    def _font(self, size: int, weight: str | None = None) -> tuple[str, int] | tuple[str, int, str]:
        scaled = max(6, self._s(size))
        return ("Microsoft YaHei UI", scaled, weight) if weight else ("Microsoft YaHei UI", scaled)

    def _screen_bounds(self) -> tuple[int, int, int, int]:
        if os.name == "nt":
            try:
                user32 = ctypes.windll.user32
                left = int(user32.GetSystemMetrics(76))
                top = int(user32.GetSystemMetrics(77))
                width = int(user32.GetSystemMetrics(78))
                height = int(user32.GetSystemMetrics(79))
                if width > 0 and height > 0:
                    return left, top, left + width, top + height
            except Exception:
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _position_bounds(self) -> tuple[int, int, int, int]:
        left, top, right, bottom = self._screen_bounds()
        visible = self._visible_whale_bounds()
        if visible is None:
            return left, top, max(left, right - self.width), max(top, bottom - self.height)
        visible_left, visible_top, visible_right, visible_bottom = visible
        min_x = left - visible_left
        min_y = top - visible_top
        max_x = right - visible_right
        max_y = bottom - visible_bottom
        return (
            min_x,
            min_y,
            max(min_x, max_x),
            max(min_y, max_y),
        )

    def _visible_whale_bounds(self) -> tuple[int, int, int, int] | None:
        if not hasattr(self, "canvas"):
            return None
        full_bounds = self.canvas.bbox("whale")
        alpha_bounds = self._last_whale_alpha_bbox
        render_size = self._last_whale_render_size
        if not full_bounds:
            return None
        if not alpha_bounds or not render_size:
            return tuple(int(value) for value in full_bounds)
        full_width = full_bounds[2] - full_bounds[0]
        full_height = full_bounds[3] - full_bounds[1]
        if (full_width, full_height) != render_size:
            return tuple(int(value) for value in full_bounds)
        return (
            int(full_bounds[0] + alpha_bounds[0]),
            int(full_bounds[1] + alpha_bounds[1]),
            int(full_bounds[0] + alpha_bounds[2]),
            int(full_bounds[1] + alpha_bounds[3]),
        )

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        min_x, min_y, max_x, max_y = self._position_bounds()
        return max(min_x, min(int(x), max_x)), max(min_y, min(int(y), max_y))

    def _position_geometry(self, x: int | float, y: int | float, include_size: bool = False) -> str:
        position = f"{round(x):+d}{round(y):+d}"
        return f"{self.width}x{self.height}{position}" if include_size else position

    def _resolve_window_handle(self) -> int | None:
        if self._window_handle is not None:
            return self._window_handle
        if os.name != "nt":
            return None
        try:
            self.root.update_idletasks()
            frame_id = self.root.frame()
            self._window_handle = (
                int(frame_id, 0) if isinstance(frame_id, str) else int(frame_id)
            )
        except Exception:
            self._window_handle = None
        return self._window_handle

    def _place_window(
        self,
        x: int | float,
        y: int | float,
        include_size: bool = False,
    ) -> None:
        target_x, target_y = round(x), round(y)
        if os.name == "nt":
            try:
                flags = 0x0010 | 0x0004  # SWP_NOACTIVATE | SWP_NOZORDER
                if not include_size:
                    flags |= 0x0001  # SWP_NOSIZE
                window_handle = self._resolve_window_handle()
                if window_handle is not None:
                    moved = ctypes.windll.user32.SetWindowPos(
                        window_handle,
                        0,
                        target_x,
                        target_y,
                        self.width,
                        self.height,
                        flags,
                    )
                    if moved:
                        return
                    self._window_handle = None
            except Exception:
                self._window_handle = None
                pass
        self.root.geometry(
            self._position_geometry(target_x, target_y, include_size=include_size)
        )

    def _initial_geometry(self) -> str:
        self.root.update_idletasks()
        saved = self.settings.get("position")
        if isinstance(saved, list) and len(saved) == 2:
            x, y = self._clamp_position(saved[0], saved[1])
        else:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = max(0, screen_w - self.width - 22)
            y = min(max(36, int(screen_h * 0.08)), max(0, screen_h - self.height))
        return self._position_geometry(x, y, include_size=True)

    def _skin_definition(self, skin_id: str | None = None) -> dict[str, Any]:
        return SKIN_DEFINITIONS[_normalize_skin(skin_id or self._active_skin_id)]

    def _active_idle_files(self) -> tuple[str, ...]:
        return tuple(self._skin_definition().get("idleFiles") or ())

    def _load_skin_assets(self, skin_id: str) -> None:
        selected = _normalize_skin(skin_id)
        definition = SKIN_DEFINITIONS[selected]
        asset_root = _widget_root() / "assets"
        normal_asset = asset_root / str(definition["normal"])
        stunned_asset = asset_root / str(definition["stunned"])
        idle_asset_root = asset_root / str(definition["idleRoot"])
        idle_asset_paths = {
            name: idle_asset_root / name
            for name in tuple(definition.get("idleFiles") or ())
        }
        display_root = asset_root / "render-cache" / selected
        display_manifest_path = display_root / "manifest.json"
        display_normal = display_root / "normal.png"
        display_stunned = display_root / "stunned.png"
        display_idle_paths = {
            name: display_root / "idle" / name
            for name in tuple(definition.get("idleFiles") or ())
        }
        required = [
            normal_asset,
            stunned_asset,
            *idle_asset_paths.values(),
            display_manifest_path,
            display_normal,
            display_stunned,
            *display_idle_paths.values(),
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f"缺少皮肤 {definition['label']} 的素材：" + " | ".join(missing)
            )

        try:
            display_manifest = json.loads(display_manifest_path.read_text(encoding="utf-8"))
            if (
                display_manifest.get("skin") != selected
                or display_manifest.get("displaySize") != list(PET_BASE_SIZE)
                or display_manifest.get("alphaThreshold") != DISPLAY_ALPHA_THRESHOLD
            ):
                raise ValueError("显示副本清单与当前皮肤契约不一致")
            display_records = display_manifest["records"]
            raw_alpha_bounds = {
                visual_key: tuple(int(value) for value in record["alphaBBox"])
                for visual_key, record in display_records.items()
            }
            if set(raw_alpha_bounds) != {
                "normal",
                "stunned",
                *(f"idle:{name}" for name in idle_asset_paths),
            }:
                raise ValueError("显示副本清单缺少视觉状态")
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"皮肤 {definition['label']} 的显示副本无效：{exc}") from exc

        self._raw_whale_image = self.tk.PhotoImage(file=str(display_normal))
        self._raw_stunned_image = self.tk.PhotoImage(file=str(display_stunned))
        self._raw_idle_images = {}
        self._pil_whale_source = None
        self._pil_stunned_source = None
        self._pil_idle_sources = {}
        try:
            from PIL import Image, ImageTk

            self._pil_image_module = Image
            self._pil_imagetk_module = ImageTk

            def fit_source(path: Path) -> Any:
                image = Image.open(path).convert("RGBA")
                longest = max(image.size)
                if longest <= WORKING_SOURCE_PX:
                    return image
                ratio = WORKING_SOURCE_PX / longest
                fitted_size = (
                    max(1, round(image.width * ratio)),
                    max(1, round(image.height * ratio)),
                )
                return image.resize(fitted_size, Image.Resampling.LANCZOS)

            self._pil_whale_source = fit_source(normal_asset)
            self._pil_stunned_source = fit_source(stunned_asset)
            self._pil_idle_sources = {
                name: fit_source(path)
                for name, path in idle_asset_paths.items()
            }
        except (ImportError, OSError):
            self._pil_image_module = None
            self._pil_imagetk_module = None
            self._raw_idle_images = {
                name: self.tk.PhotoImage(file=str(display_idle_paths[name]))
                for name in idle_asset_paths
            }
        self._active_skin_id = selected
        self._idle_asset_paths = idle_asset_paths
        self._raw_alpha_bounds = raw_alpha_bounds

    def _whale_base_size(self) -> tuple[int, int]:
        return (
            max(1, int(round(PET_BASE_SIZE[0] * self.scale))),
            max(1, int(round(PET_BASE_SIZE[1] * self.scale))),
        )

    def _whale_anchor(self) -> tuple[float, float]:
        width, height = self._whale_base_size()
        return self._s(274) + width / 2, self._s(142) + height

    def _current_visual_key(self, stunned: bool | None = None) -> str:
        if self._stunned if stunned is None else bool(stunned):
            return "stunned"
        if self._active_idle_variant in self._idle_asset_paths:
            return f"idle:{self._active_idle_variant}"
        return "normal"

    def _visual_sources(self, visual_key: str) -> tuple[Any | None, Any]:
        if visual_key == "stunned":
            return self._pil_stunned_source, self._raw_stunned_image
        if visual_key.startswith("idle:"):
            name = visual_key.removeprefix("idle:")
            pil_source = self._pil_idle_sources.get(name)
            raw_source = self._raw_idle_images.get(name, self._raw_whale_image)
            return pil_source, raw_source
        return self._pil_whale_source, self._raw_whale_image

    def _whale_variant(
        self,
        stunned: bool,
        stretch_x: float = 1.0,
        stretch_y: float = 1.0,
        visual_key: str | None = None,
    ) -> dict[str, Any]:
        visual_key = visual_key or self._current_visual_key(stunned)
        key = (
            f"{self._active_skin_id}:{visual_key}",
            round(float(self.scale), 3),
            round(float(stretch_x), 3),
            round(float(stretch_y), 3),
        )
        cached = self._whale_image_cache.get(key)
        if cached is not None:
            self._last_whale_cache_hit = True
            return cached
        self._last_whale_cache_hit = False
        base_width, base_height = self._whale_base_size()
        width = max(1, int(round(base_width * stretch_x)))
        height = max(1, int(round(base_height * stretch_y)))
        pil_source, raw_source = self._visual_sources(visual_key)
        if pil_source is not None and self._pil_imagetk_module is not None:
            image = pil_source.resize(
                (width, height),
                self._pil_image_module.Resampling.LANCZOS,
            )
            image = self._make_color_key_safe(image)
            record = {
                "image": self._pil_imagetk_module.PhotoImage(image, master=self.root),
                "alphaBBox": image.getchannel("A").getbbox(),
                "renderSize": image.size,
                "translucentPixels": self._last_whale_translucent_pixels,
                "magentaPixels": self._last_whale_magenta_pixels,
            }
            self._whale_image_cache[key] = record
            return record

        ratio_x = Fraction(width, max(1, raw_source.width())).limit_denominator(20)
        ratio_y = Fraction(height, max(1, raw_source.height())).limit_denominator(20)
        image = raw_source
        if ratio_x.numerator != 1 or ratio_y.numerator != 1:
            image = image.zoom(ratio_x.numerator, ratio_y.numerator)
        if ratio_x.denominator != 1 or ratio_y.denominator != 1:
            image = image.subsample(ratio_x.denominator, ratio_y.denominator)
        rendered_width, rendered_height = image.width(), image.height()
        source_bounds = self._raw_alpha_bounds.get(
            visual_key, (0, 0, raw_source.width(), raw_source.height())
        )
        source_size = (raw_source.width(), raw_source.height())
        record = {
            "image": image,
            "alphaBBox": (
                math.floor(source_bounds[0] * rendered_width / source_size[0]),
                math.floor(source_bounds[1] * rendered_height / source_size[1]),
                math.ceil(source_bounds[2] * rendered_width / source_size[0]),
                math.ceil(source_bounds[3] * rendered_height / source_size[1]),
            ),
            "renderSize": (rendered_width, rendered_height),
            "translucentPixels": 0,
            "magentaPixels": 0,
        }
        self._whale_image_cache[key] = record
        return record

    def _scaled_whale(self, stretch_x: float = 1.0, stretch_y: float = 1.0) -> Any:
        record = self._whale_variant(self._stunned, stretch_x, stretch_y)
        self._rendered_whale_state = self._current_visual_key()
        self._last_whale_alpha_bbox = record["alphaBBox"]
        self._last_whale_render_size = record["renderSize"]
        self._last_whale_translucent_pixels = record["translucentPixels"]
        self._last_whale_magenta_pixels = record["magentaPixels"]
        return record["image"]

    def _prewarm_collision_visual(self) -> None:
        started = time.perf_counter()
        visual_keys = [
            "normal",
            "stunned",
            *(f"idle:{name}" for name in self._active_idle_files()),
        ]
        stretch_frames = {
            (float(stretch_x), float(stretch_y))
            for _, stretch_x, stretch_y in CLICK_DEFORMATION_FRAMES
        }
        for visual_key in visual_keys:
            for stretch_x, stretch_y in stretch_frames:
                self._whale_variant(
                    visual_key == "stunned",
                    stretch_x,
                    stretch_y,
                    visual_key=visual_key,
                )
        self._collision_visual_prewarm_ms = (time.perf_counter() - started) * 1000.0
        self._collision_visual_prewarmed = True

    def _make_color_key_safe(self, image: Any) -> Any:
        """Remove translucent edge pixels before Tk blends them with the magenta key."""
        rgba = image.convert("RGBA")
        red, green, blue, alpha = rgba.split()
        binary_alpha = alpha.point(lambda value: 255 if value >= DISPLAY_ALPHA_THRESHOLD else 0)
        opaque = self._pil_image_module.merge("RGBA", (red, green, blue, binary_alpha))
        transparent = self._pil_image_module.new("RGBA", rgba.size, (0, 0, 0, 0))
        safe = self._pil_image_module.composite(opaque, transparent, binary_alpha)
        self._last_whale_translucent_pixels = 0
        self._last_whale_magenta_pixels = 0
        if self.qa_mode:
            colors = safe.getcolors(maxcolors=safe.width * safe.height) or []
            self._last_whale_translucent_pixels = sum(
                count for count, (*_, value) in colors if 0 < value < 255
            )
            self._last_whale_magenta_pixels = sum(
                count
                for count, (red_value, green_value, blue_value, alpha_value) in colors
                if alpha_value > 0
                and red_value >= 220
                and blue_value >= 220
                and green_value <= 80
            )
        return safe

    def _bubble_coord(self, value: float, pivot: float, factor: float) -> int:
        return self._s(pivot + (value - pivot) * factor)

    def _draw_bubble(self, factor: float) -> None:
        c = self.canvas
        c.delete("bubble")
        factor = max(0.05, min(float(factor), 1.0))
        pivot_x, pivot_y = 305.0, 220.0
        bx = lambda value: self._bubble_coord(value, pivot_x, factor)
        by = lambda value: self._bubble_coord(value, pivot_y, factor)
        outline = "#203170"
        bubble_tags = ("bubble", "bubble-shape")
        content_tags = ("bubble", "bubble-content")
        self.bubble_main = c.create_oval(
            bx(8), by(9), bx(320), by(197),
            fill="#ffffff", outline=outline,
            width=max(1, self._s(4 * factor)), tags=bubble_tags,
        )
        c.create_oval(
            bx(257), by(191), bx(289), by(213),
            fill="#ffffff", outline=outline,
            width=max(1, self._s(4 * factor)), tags=bubble_tags,
        )
        c.create_oval(
            bx(294), by(218), bx(314), by(234),
            fill="#ffffff", outline=outline,
            width=max(1, self._s(4 * factor)), tags=bubble_tags,
        )
        self.bubble_title_text = c.create_text(
            bx(164), by(32), text=str(self._skin_definition()["bubbleTitle"]), fill="#5b6fa7",
            font=self._font(max(6, round(11 * factor)), "bold"), tags=content_tags,
        )
        self.status_dot = c.create_oval(
            bx(88), by(65), bx(100), by(77),
            fill="#9aa4b5", outline="", tags=content_tags,
        )
        self.status_text = c.create_text(
            bx(164), by(71), text="正在读取本机状态…", anchor="center",
            fill="#273970", font=self._font(max(6, round(12 * factor)), "bold"),
            tags=content_tags,
        )
        self.detail_text = c.create_text(
            bx(164), by(91), text="", anchor="n", justify="center",
            width=max(1, self._s(240 * factor)), fill="#6f7c9f",
            font=self._font(max(6, round(8 * factor))), tags=content_tags,
        )
        c.create_line(
            bx(43), by(126), bx(281), by(126),
            fill="#e4e8f3", width=max(1, self._s(factor)), tags=content_tags,
        )
        self.quota_text = c.create_text(
            bx(162), by(146), text="Codex 余量 --", fill="#536ba9",
            font=self._font(max(6, round(11 * factor)), "bold"), tags=content_tags,
        )
        self.reset_text = c.create_text(
            bx(162), by(174), text="重置时间未知 · 重置卡数量不可用", fill="#7183b2",
            font=self._font(max(6, round(8 * factor))), tags=content_tags,
        )
        self.reset_credit_text = self.reset_text
        c.itemconfigure("bubble-content", state="normal" if factor >= 0.98 else "hidden")
        if c.find_withtag("whale"):
            c.tag_lower("bubble", "whale")
        if self._latest_snapshot is not None:
            self._render(self._latest_snapshot)

    def _draw_whale(self) -> None:
        self.whale_image = self._scaled_whale(*self._whale_stretch)
        anchor_x, anchor_y = self._whale_anchor()
        self.whale_item = self.canvas.create_image(
            anchor_x, anchor_y, image=self.whale_image, anchor="s", tags=("whale",),
        )

    def _draw_static(self) -> None:
        c = self.canvas
        c.delete("all")
        c.configure(width=self.width, height=self.height)
        self._draw_bubble(self._bubble_scale if self._bubble_visible else 1.0)
        self._draw_whale()
        self._prewarm_collision_visual()
        if not self._bubble_visible:
            c.itemconfigure("bubble", state="hidden")

    def _bind_actions(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_release)
        self.canvas.bind("<Button-3>", self._show_menu)

        self.throw_var = self.tk.BooleanVar(value=bool(self.settings["throwMode"]))
        self.follow_var = self.tk.BooleanVar(value=bool(self.settings["followMouse"]))
        self.fixed_var = self.tk.BooleanVar(value=bool(self.settings["fixedPosition"]))
        self.absolute_var = self.tk.BooleanVar(value=bool(self.settings["absolutePosition"]))
        self.acceleration_var = self.tk.IntVar(
            value=int(self.settings["followAccelerationLimit"])
        )
        self.physics_var = self.tk.BooleanVar(value=bool(self.settings["physicsEnabled"]))
        self.stun_duration_var = self.tk.IntVar(value=int(self.settings["stunDurationMs"]))
        self.scale_percent_var = self.tk.IntVar(value=round(self.scale * 100))
        self.skin_var = self.tk.StringVar(value=self._active_skin_id)
        self.sound_profile_var = self.tk.StringVar(
            value=_normalize_sound_profile(self.settings.get("soundProfile"))
        )
        self.sound_volume_var = self.tk.IntVar(
            value=_normalize_sound_volume(self.settings.get("soundVolume"))
        )
        self.topmost_var = self.tk.BooleanVar(value=bool(self.settings["topmost"]))
        self.autostart_var = self.tk.BooleanVar(value=_autostart_enabled())

        menu = self.tk.Menu(self.root, tearoff=0)
        follow_menu = self.tk.Menu(menu, tearoff=0)
        follow_menu.add_checkbutton(
            label=FOLLOW_SUBMENU_LABELS[0],
            variable=self.follow_var,
            command=self._toggle_follow,
        )
        acceleration_menu = self.tk.Menu(follow_menu, tearoff=0)
        acceleration_labels = {
            4800: "柔和 · 4,800 px/s²",
            7200: "标准 · 7,200 px/s²",
            9600: "快速 · 9,600 px/s²（推荐）",
            12800: "极快 · 12,800 px/s²",
        }
        for limit in FOLLOW_ACCELERATION_OPTIONS:
            acceleration_menu.add_radiobutton(
                label=acceleration_labels[limit],
                variable=self.acceleration_var,
                value=limit,
                command=lambda selected=limit: self._set_follow_acceleration_limit(selected),
            )
        follow_menu.add_cascade(label=FOLLOW_SUBMENU_LABELS[1], menu=acceleration_menu)
        follow_menu.add_separator()
        follow_menu.add_checkbutton(
            label=FOLLOW_SUBMENU_LABELS[2],
            variable=self.physics_var,
            command=self._toggle_physics,
        )
        stun_duration_menu = self.tk.Menu(follow_menu, tearoff=0)
        stun_duration_labels = {
            800: "短暂 · 0.8 秒",
            1400: "标准 · 1.4 秒（推荐）",
            2200: "明显 · 2.2 秒",
            3200: "很久 · 3.2 秒",
        }
        for duration in STUN_DURATION_OPTIONS:
            stun_duration_menu.add_radiobutton(
                label=stun_duration_labels[duration],
                variable=self.stun_duration_var,
                value=duration,
                command=lambda selected=duration: self._set_stun_duration(selected),
            )
        follow_menu.add_cascade(
            label=FOLLOW_SUBMENU_LABELS[3], menu=stun_duration_menu,
        )
        menu.add_checkbutton(
            label=MENU_LABELS[0], variable=self.throw_var, command=self._toggle_throw,
        )
        menu.add_cascade(label=MENU_LABELS[1], menu=follow_menu)
        menu.add_checkbutton(label=MENU_LABELS[2], variable=self.fixed_var, command=self._toggle_fixed)
        menu.add_checkbutton(
            label=MENU_LABELS[3], variable=self.absolute_var, command=self._toggle_absolute,
        )
        absolute_presets_menu = self.tk.Menu(menu, tearoff=0)
        self.absolute_preset_menus: list[Any] = []
        for index in range(ABSOLUTE_PRESET_LIMIT):
            preset_menu = self.tk.Menu(absolute_presets_menu, tearoff=0)
            preset_menu.add_command(
                label="保存/覆盖当前位置与大小",
                command=lambda slot=index: self._save_absolute_preset(slot),
            )
            preset_menu.add_command(
                label="应用并锁定",
                command=lambda slot=index: self._apply_absolute_preset(slot),
            )
            preset_menu.add_command(
                label="清除",
                command=lambda slot=index: self._clear_absolute_preset(slot),
            )
            absolute_presets_menu.add_cascade(label=f"预设 {index + 1}：空", menu=preset_menu)
            self.absolute_preset_menus.append(preset_menu)
        menu.add_cascade(label=MENU_LABELS[4], menu=absolute_presets_menu)
        menu.add_checkbutton(label=MENU_LABELS[5], variable=self.topmost_var, command=self._toggle_topmost)
        size_menu = self.tk.Menu(menu, tearoff=0)
        size_menu.add_command(label=self._size_status_label(), state="disabled")
        size_menu.add_separator()
        for percent in SCALE_PERCENT_OPTIONS:
            size_menu.add_radiobutton(
                label=f"{percent}%",
                variable=self.scale_percent_var,
                value=percent,
                command=lambda selected=percent: self._apply_scale(
                    _scale_from_percent(selected)
                ),
            )
        menu.add_cascade(label=MENU_LABELS[6], menu=size_menu)
        skin_menu = self.tk.Menu(menu, tearoff=0)
        for skin_id in SKIN_IDS:
            skin_menu.add_radiobutton(
                label=str(SKIN_DEFINITIONS[skin_id]["label"]),
                variable=self.skin_var,
                value=skin_id,
                command=lambda selected=skin_id: self._set_skin(selected),
            )
        menu.add_cascade(label=MENU_LABELS[7], menu=skin_menu)
        sound_menu = self.tk.Menu(menu, tearoff=0)
        for profile_id in SOUND_PROFILE_IDS:
            sound_menu.add_radiobutton(
                label=str(SOUND_PROFILE_DEFINITIONS[profile_id]["label"]),
                variable=self.sound_profile_var,
                value=profile_id,
                command=lambda selected=profile_id: self._set_sound_profile(selected),
            )
        sound_menu.add_separator()
        volume_menu = self.tk.Menu(sound_menu, tearoff=0)
        for volume in SOUND_VOLUME_OPTIONS:
            volume_menu.add_radiobutton(
                label="静音" if volume == 0 else f"{volume}%",
                variable=self.sound_volume_var,
                value=volume,
                command=lambda selected=volume: self._set_sound_volume(selected),
            )
        sound_menu.add_cascade(label="音量", menu=volume_menu)
        sound_menu.add_command(label="试听当前音效", command=self._preview_sound)
        menu.add_cascade(label=MENU_LABELS[8], menu=sound_menu)
        menu.add_checkbutton(
            label=MENU_LABELS[9], variable=self.autostart_var, command=self._toggle_autostart,
        )
        menu.add_command(label=MENU_LABELS[10], command=self._check_updates)
        menu.add_command(label=MENU_LABELS[11], command=self._about)
        menu.add_command(label=MENU_LABELS[12], command=self.close)
        self.menu = menu
        self.follow_menu = follow_menu
        self.acceleration_menu = acceleration_menu
        self.stun_duration_menu = stun_duration_menu
        self.absolute_presets_menu = absolute_presets_menu
        self.size_menu = size_menu
        self.skin_menu = skin_menu
        self.sound_menu = sound_menu
        self.volume_menu = volume_menu
        self._refresh_absolute_preset_menu()
        self._refresh_size_menu()

    def _size_status_label(self) -> str:
        mode = " · 绝对坐标模式" if hasattr(self, "absolute_var") and self.absolute_var.get() else ""
        return f"当前比例 {round(self.scale * 100):d}%（范围 50%–220%）{mode}"

    def _refresh_size_menu(self) -> None:
        if hasattr(self, "size_menu"):
            self.size_menu.entryconfigure(0, label=self._size_status_label())
        if hasattr(self, "scale_percent_var"):
            self.scale_percent_var.set(round(self.scale * 100))

    def _set_skin(self, selected: str) -> None:
        selected = _normalize_skin(selected)
        if selected == self._active_skin_id:
            self.skin_var.set(selected)
            return
        previous = self._active_skin_id
        self._record_interaction()
        self._set_stunned(False)
        self._active_idle_variant = None
        self._last_idle_variant = None
        try:
            self._load_skin_assets(selected)
        except Exception as exc:
            self.skin_var.set(previous)
            self._dialog("更换皮肤", f"切换失败：{_compact_error(exc)}", error=True)
            return
        self.skin_var.set(selected)
        self.settings["skin"] = selected
        self._whale_image_cache.clear()
        self._draw_static()
        self.root.update_idletasks()
        x, y = self._clamp_position(self.root.winfo_x(), self.root.winfo_y())
        self._place_window(x, y, include_size=True)
        self._save_preferences(position=True)

    def _selected_sound_profile(self) -> str:
        value = (
            self.sound_profile_var.get()
            if hasattr(self, "sound_profile_var")
            else self.settings.get("soundProfile")
        )
        return _normalize_sound_profile(value)

    def _selected_sound_volume(self) -> int:
        value = (
            self.sound_volume_var.get()
            if hasattr(self, "sound_volume_var")
            else self.settings.get("soundVolume")
        )
        return _normalize_sound_volume(value)

    def _selected_sound_paths(self) -> tuple[Path, ...]:
        definition = SOUND_PROFILE_DEFINITIONS[self._selected_sound_profile()]
        asset_root = _widget_root() / "assets"
        return tuple(asset_root / str(name) for name in definition["files"])

    def _set_sound_profile(self, selected: str, wait: bool = False) -> None:
        normalized = _normalize_sound_profile(selected)
        self.sound_profile_var.set(normalized)
        self.settings["soundProfile"] = normalized
        self._reload_collision_audio(wait=wait)
        self._save_preferences()

    def _set_sound_volume(self, selected: int, wait: bool = False) -> None:
        normalized = _normalize_sound_volume(selected)
        self.sound_volume_var.set(normalized)
        self.settings["soundVolume"] = normalized
        aliases = tuple(self._audio_aliases)
        if aliases:
            value = normalized * 10
            self._submit_audio(
                *(f"setaudio {alias} volume to {value}" for alias in aliases),
                label="set-profile-volume",
                wait=wait,
            )
        self._save_preferences()

    def _preview_sound(self) -> None:
        self._play_selected_click()

    def _preset_label(self, index: int) -> str:
        preset = self.settings["absolutePresets"][index]
        if preset is None:
            return f"预设 {index + 1}：空"
        position = preset["position"]
        scale = round(float(preset["scale"]) * 100)
        active = " · 当前" if self.settings.get("activeAbsolutePreset") == index else ""
        return f"预设 {index + 1}：({position[0]}, {position[1]}) · {scale}%{active}"

    def _refresh_absolute_preset_menu(self) -> None:
        if not hasattr(self, "absolute_presets_menu"):
            return
        for index, preset_menu in enumerate(self.absolute_preset_menus):
            preset = self.settings["absolutePresets"][index]
            self.absolute_presets_menu.entryconfigure(index, label=self._preset_label(index))
            state = "normal" if preset is not None else "disabled"
            preset_menu.entryconfigure(1, state=state)
            preset_menu.entryconfigure(2, state=state)

    def menu_labels(self) -> list[str]:
        return [self.menu.entrycget(index, "label") for index in range(self.menu.index("end") + 1)]

    def follow_menu_labels(self) -> list[str]:
        return [
            self.follow_menu.entrycget(index, "label")
            for index in range(self.follow_menu.index("end") + 1)
            if self.follow_menu.type(index) != "separator"
        ]

    def skin_menu_labels(self) -> list[str]:
        return [
            self.skin_menu.entrycget(index, "label")
            for index in range(self.skin_menu.index("end") + 1)
        ]

    def sound_menu_labels(self) -> list[str]:
        return [
            self.sound_menu.entrycget(index, "label")
            for index in range(self.sound_menu.index("end") + 1)
            if self.sound_menu.type(index) != "separator"
        ]

    def bubble_visible(self) -> bool:
        return (
            self._bubble_visible
            and bool(self.canvas.find_withtag("bubble-shape"))
            and self.canvas.itemcget(self.bubble_main, "state") != "hidden"
        )

    def _event_hits_whale(self, event: Any) -> bool:
        bounds = self.canvas.bbox("whale")
        if not bounds:
            return False
        x = event.x_root - self.root.winfo_rootx()
        y = event.y_root - self.root.winfo_rooty()
        return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]

    def _drag_start(self, event: Any) -> None:
        self._press_active = self._event_hits_whale(event)
        if not self._press_active:
            return
        self._record_interaction()
        self._drag_moved = False
        self._drag_origin = (event.x_root, event.y_root)
        self._window_origin = (self.root.winfo_x(), self.root.winfo_y())
        if self.throw_var.get():
            now = time.monotonic()
            self._set_stunned(False, now)
            self._throw_active = False
            self._throw_dragging = True
            self._throw_position = [float(self._window_origin[0]), float(self._window_origin[1])]
            self._throw_velocity = [0.0, 0.0]
            self._throw_last_tick = now
            self._throw_samples = [(now, *self._throw_position)]
            return
        if self.follow_var.get():
            self._follow_paused = True

    def _drag_move(self, event: Any) -> None:
        if not self._press_active:
            return
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._drag_moved = True
        if self.throw_var.get() and self._throw_dragging and self._drag_moved:
            x, y = self._clamp_position(self._window_origin[0] + dx, self._window_origin[1] + dy)
            self._throw_position = [float(x), float(y)]
            self._place_window(x, y)
            self._record_throw_sample(float(x), float(y))
            return
        if (
            not self._drag_moved
            or self.fixed_var.get()
            or self.follow_var.get()
            or self.absolute_var.get()
        ):
            return
        x, y = self._clamp_position(self._window_origin[0] + dx, self._window_origin[1] + dy)
        self._place_window(x, y)

    def _drag_release(self, _event: Any) -> None:
        if not self._press_active:
            return
        self._press_active = False
        if self.throw_var.get() and self._throw_dragging:
            now = time.monotonic()
            self._throw_dragging = False
            self._record_throw_sample(
                float(self.root.winfo_x()), float(self.root.winfo_y()), now,
            )
            if self._drag_moved:
                vx, vy = _throw_velocity_from_samples(self._throw_samples)
                speed = math.hypot(vx, vy)
                self._throw_velocity = [vx, vy]
                self._throw_position = [float(self.root.winfo_x()), float(self.root.winfo_y())]
                self._throw_last_tick = now
                self._throw_active = speed >= THROW_MIN_SPEED
                self._throw_history.append(
                    {
                        "event": "release",
                        "at": round(now, 3),
                        "speed": round(speed, 3),
                        "velocity": [round(vx, 3), round(vy, 3)],
                        "active": self._throw_active,
                    }
                )
                self._throw_history = self._throw_history[-12:]
                if not self._throw_active:
                    self._stop_throw(persist=True)
                elif not self.qa_mode:
                    self._save_preferences(position=True)
                return
            self._activate_click(play_sound=not self.qa_mode)
            return
        if self._drag_moved:
            if not self.fixed_var.get() and not self.follow_var.get() and not self.absolute_var.get():
                self._save_preferences(position=True)
            if self.follow_var.get():
                self._follow_paused = False
                self._reset_follow_state()
            return
        if self.follow_var.get():
            self.follow_var.set(False)
            self.fixed_var.set(True)
            self.absolute_var.set(False)
            self.settings["activeAbsolutePreset"] = None
            self._follow_paused = False
            self._reset_follow_state()
            self._save_preferences(position=True)
        self._activate_click(play_sound=not self.qa_mode)

    def _show_menu(self, event: Any) -> None:
        if not self._event_hits_whale(event):
            return
        self._record_interaction()
        resume_follow = bool(self.follow_var.get())
        if resume_follow:
            self._follow_paused = True
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
            if resume_follow and self.follow_var.get():
                self._follow_paused = False
                self._reset_follow_state()

    def _cancel_bubble_timers(self) -> None:
        for after_id in self._bubble_after_ids:
            try:
                self.root.after_cancel(after_id)
            except self.tk.TclError:
                pass
        self._bubble_after_ids.clear()

    def _set_bubble_stage(self, factor: float, expected: int, opening: bool) -> None:
        if expected != self._click_generation or self.stop.is_set():
            return
        self._bubble_scale = factor
        if opening:
            self._bubble_stage_history.append(round(factor, 2))
        self._draw_bubble(factor)

    def _show_bubble(self, generation: int) -> None:
        self._cancel_bubble_timers()
        self._bubble_visible = True
        self._bubble_stage_history = []
        self._set_bubble_stage(0.30, generation, opening=True)
        for delay, factor in ((70, 0.64), (150, 1.0)):
            after_id = self.root.after(
                delay,
                lambda value=factor, expected=generation: self._set_bubble_stage(
                    value, expected, opening=True,
                ),
            )
            self._bubble_after_ids.append(after_id)
        self._bubble_after_ids.append(
            self.root.after(BUBBLE_MS, lambda expected=generation: self._begin_bubble_hide(expected))
        )

    def _begin_bubble_hide(self, expected: int) -> None:
        if expected != self._click_generation or self.stop.is_set():
            return
        for delay, factor in ((0, 1.0), (65, 0.64), (130, 0.30)):
            after_id = self.root.after(
                delay,
                lambda value=factor, generation=expected: self._set_bubble_stage(
                    value, generation, opening=False,
                ),
            )
            self._bubble_after_ids.append(after_id)
        self._bubble_after_ids.append(
            self.root.after(195, lambda generation=expected: self._finish_bubble_hide(generation))
        )

    def _finish_bubble_hide(self, expected: int) -> None:
        if expected != self._click_generation:
            return
        self._bubble_visible = False
        self.canvas.itemconfigure("bubble", state="hidden")

    def _set_whale_deformation(
        self,
        stretch_x: float,
        stretch_y: float,
        expected: int,
    ) -> None:
        if expected != self._click_generation or self.stop.is_set():
            return
        self._whale_stretch = (stretch_x, stretch_y)
        self._click_deformation_history.append((round(stretch_x, 2), round(stretch_y, 2)))
        self._refresh_whale_visual()

    def _refresh_whale_visual(self) -> None:
        if not hasattr(self, "whale_item"):
            return
        self.whale_image = self._scaled_whale(*self._whale_stretch)
        self.canvas.itemconfigure(self.whale_item, image=self.whale_image)
        self.canvas.coords(self.whale_item, *self._whale_anchor())

    def _record_interaction(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else float(now)
        self._last_interaction_at = current
        self._next_idle_variant_at = current + IDLE_VARIANT_SECONDS
        if self._active_idle_variant is not None:
            previous = self._active_idle_variant
            self._active_idle_variant = None
            self._idle_variant_history.append(
                {"event": "restore", "variant": previous, "at": round(current, 3)}
            )
            self._idle_variant_history = self._idle_variant_history[-12:]
            self._refresh_whale_visual()

    def _activate_idle_variant(
        self,
        name: str | None = None,
        now: float | None = None,
    ) -> bool:
        if self._stunned or self._throw_dragging or self._throw_active or self._press_active:
            return False
        choices = list(self._active_idle_files())
        if name is None:
            if self._last_idle_variant in choices and len(choices) > 1:
                choices.remove(self._last_idle_variant)
            name = random.choice(choices)
        if name not in self._idle_asset_paths:
            return False
        current = time.monotonic() if now is None else float(now)
        self._active_idle_variant = name
        self._last_idle_variant = name
        self._idle_variant_history.append(
            {"event": "activate", "variant": name, "at": round(current, 3)}
        )
        self._idle_variant_history = self._idle_variant_history[-12:]
        self._refresh_whale_visual()
        return True

    def _idle_variant_tick(self) -> None:
        if self.stop.is_set():
            return
        self._maybe_activate_idle_variant()
        self.root.after(1000, self._idle_variant_tick)

    def _maybe_activate_idle_variant(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        if self._active_idle_variant is None and current >= self._next_idle_variant_at:
            return self._activate_idle_variant(now=current)
        return False

    def _set_stunned(
        self,
        active: bool,
        now: float | None = None,
        impact_speed: float = 0.0,
        sides: list[str] | None = None,
    ) -> bool:
        active = bool(active)
        current = time.monotonic() if now is None else float(now)
        if active:
            if self._stunned:
                return False
            duration_ms = _normalize_stun_duration(
                self.stun_duration_var.get()
                if hasattr(self, "stun_duration_var")
                else self.settings.get("stunDurationMs")
            )
            self._stunned = True
            self._stun_started_at = current
            self._stun_until = current + duration_ms / 1000.0
            self._stun_history.append(
                {
                    "event": "start",
                    "at": round(current, 3),
                    "durationMs": duration_ms,
                    "impactSpeed": round(float(impact_speed), 3),
                    "sides": list(sides or []),
                }
            )
        else:
            if not self._stunned:
                return False
            self._stunned = False
            self._stun_started_at = None
            self._stun_until = 0.0
            self._stun_history.append({"event": "end", "at": round(current, 3)})
            self._follow_cycle_started = current
            self._follow_cycle_active = False
        self._stun_history = self._stun_history[-12:]
        switch_started = time.perf_counter()
        self._refresh_whale_visual()
        self._last_stun_visual_switch_ms = (time.perf_counter() - switch_started) * 1000.0
        return True

    def _activate_click(self, play_sound: bool = True) -> None:
        self._record_interaction()
        self._click_count += 1
        self._click_generation += 1
        generation = self._click_generation
        self._show_bubble(generation)
        if play_sound:
            self._play_selected_click()
        self._click_deformation_history = []
        for delay, stretch_x, stretch_y in CLICK_DEFORMATION_FRAMES:
            self.root.after(
                delay,
                lambda x=stretch_x, y=stretch_y, expected=generation: (
                    self._set_whale_deformation(x, y, expected)
                ),
            )

    def _audio_worker(self) -> None:
        while True:
            job = self._audio_queue.get()
            if job is None:
                self._audio_queue.task_done()
                return
            started = time.perf_counter()
            codes: list[int] = []
            commands = tuple(job.get("commands") or ())
            for command in commands:
                try:
                    code = int(
                        ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
                    )
                except Exception:
                    code = -1
                codes.append(code)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            ok = all(code == 0 for code in codes)
            generation = job.get("profileGeneration")
            if generation is not None and generation == self._audio_profile_generation:
                self._collision_audio_prepare_ms = elapsed_ms
                self._collision_audio_ready = ok
                self._audio_profile_ready.set()
            record = {
                "label": str(job.get("label") or "audio"),
                "commandCount": len(commands),
                "codes": codes,
                "ok": ok,
                "elapsedMs": round(elapsed_ms, 3),
            }
            with self._audio_state_lock:
                self._audio_worker_results.append(record)
                self._audio_worker_results = self._audio_worker_results[-64:]
            result = job.get("result")
            if isinstance(result, dict):
                result.update(record)
            event = job.get("event")
            if isinstance(event, threading.Event):
                event.set()
            self._audio_queue.task_done()

    def _submit_audio(
        self,
        *commands: str,
        label: str = "audio",
        wait: bool = False,
        profile_generation: int | None = None,
    ) -> bool:
        if os.name != "nt" or not self._audio_accepting:
            return False
        event = threading.Event() if wait else None
        result: dict[str, Any] = {}
        job: dict[str, Any] = {
            "commands": tuple(commands),
            "event": event,
            "result": result,
            "label": label,
            "profileGeneration": profile_generation,
        }
        try:
            self._audio_queue.put_nowait(job)
        except queue.Full:
            self._audio_submit_dropped += 1
            if profile_generation == self._audio_profile_generation:
                self._collision_audio_ready = False
                self._audio_profile_ready.set()
            return False
        if not wait:
            return True
        if event is None or not event.wait(timeout=5.0):
            return False
        return bool(result.get("ok"))

    def _wait_for_audio_profile(self, timeout: float = 5.0) -> bool:
        if self._collision_audio_ready:
            return True
        self._audio_profile_ready.wait(timeout=max(0.0, float(timeout)))
        return self._collision_audio_ready

    @staticmethod
    def _audio_play_commands(alias: str) -> tuple[str, str, str]:
        return (
            f"stop {alias}",
            f"seek {alias} to start",
            f"play {alias} from 0",
        )

    def _play_audio_alias(self, alias: str, label: str) -> bool:
        if alias not in self._audio_aliases:
            return False
        return self._submit_audio(
            *self._audio_play_commands(alias),
            label=label,
        )

    def _play_selected_click(self) -> bool:
        if self._selected_sound_volume() == 0:
            return True
        aliases = self._click_audio_aliases
        if not self._collision_audio_ready or not aliases:
            try:
                self.root.bell()
            except self.tk.TclError:
                pass
            return False
        delay = int(
            SOUND_PROFILE_DEFINITIONS[self._selected_sound_profile()]["sequenceDelayMs"]
        )
        submitted = self._play_audio_alias(aliases[0], "click-1")
        for index, alias in enumerate(aliases[1:], start=1):
            self.root.after(
                max(0, delay * index),
                lambda selected=alias, number=index + 1: self._play_audio_alias(
                    selected, f"click-{number}"
                ),
            )
        return submitted

    @staticmethod
    def _mci_device_type(path: Path) -> str:
        # mpegvideo accepts both MP3 and PCM WAV and, unlike waveaudio on this
        # Windows path, supports per-alias setaudio volume control.
        return "mpegvideo"

    def _set_audio_alias_volume(self, alias: str, wait: bool = False) -> bool:
        if alias not in self._audio_aliases:
            return False
        value = self._selected_sound_volume() * 10
        return self._submit_audio(
            f"setaudio {alias} volume to {value}",
            label="set-volume",
            wait=wait,
        )

    def _reload_collision_audio(self, wait: bool = False) -> bool:
        old_aliases = tuple(self._audio_aliases)
        self._audio_aliases.clear()
        self._collision_audio_alias = None
        self._click_audio_aliases = ()
        self._collision_audio_path = None
        self._collision_audio_ready = False
        return self._prepare_collision_audio(wait=wait, aliases_to_close=old_aliases)

    def _prepare_collision_audio(
        self,
        wait: bool = False,
        aliases_to_close: tuple[str, ...] = (),
    ) -> bool:
        if self._collision_audio_alias:
            return self._wait_for_audio_profile() if wait else True
        if os.name != "nt":
            return False
        paths = self._selected_sound_paths()
        if not paths or not all(path.is_file() for path in paths):
            return False
        if aliases_to_close:
            self._submit_audio(
                *(f"close {alias}" for alias in aliases_to_close),
                label="close-old-profile",
            )
        self._audio_profile_generation += 1
        generation = self._audio_profile_generation
        self._audio_profile_ready.clear()
        self._collision_audio_prepare_ms = 0.0
        collision_alias = f"codexwhale_collision_{os.getpid()}_{generation}"
        click_aliases = tuple(
            f"codexwhale_click_{os.getpid()}_{generation}_{index}"
            for index in range(len(paths))
        )
        aliases_and_paths = (
            (collision_alias, paths[0]),
            *tuple(zip(click_aliases, paths)),
        )
        volume = self._selected_sound_volume() * 10
        commands: list[str] = []
        for alias, path in aliases_and_paths:
            commands.extend(
                (
                    f'open "{path.resolve()}" type {self._mci_device_type(path)} alias {alias}',
                    f"setaudio {alias} volume to {volume}",
                )
            )
        self._collision_audio_alias = collision_alias
        self._click_audio_aliases = click_aliases
        self._collision_audio_path = paths[0].resolve()
        self._audio_aliases = {alias for alias, _ in aliases_and_paths}
        submitted = self._submit_audio(
            *commands,
            label="prepare-profile",
            wait=False,
            profile_generation=generation,
        )
        if not submitted:
            self._audio_aliases.clear()
            self._collision_audio_alias = None
            self._click_audio_aliases = ()
            self._collision_audio_path = None
            return False
        return self._wait_for_audio_profile() if wait else True

    def _play_preloaded_collision_audio(self) -> bool:
        if self._selected_sound_volume() == 0:
            return True
        alias = self._collision_audio_alias
        if not self._collision_audio_ready or not alias:
            return False
        return self._play_audio_alias(alias, "collision")

    def _close_audio(self, alias: str) -> None:
        if alias not in self._audio_aliases:
            return
        self._audio_aliases.discard(alias)
        self._submit_audio(f"close {alias}", label="close-alias")
        if alias == self._collision_audio_alias:
            self._collision_audio_alias = None
            self._collision_audio_path = None
            self._collision_audio_ready = False

    def _wait_for_audio_idle(self, timeout: float = 5.0) -> bool:
        return self._submit_audio(label="audio-barrier", wait=True)

    def _shutdown_audio(self) -> None:
        if not self._audio_thread.is_alive():
            return
        aliases = tuple(self._audio_aliases)
        if aliases:
            self._submit_audio(
                *(f"close {alias}" for alias in aliases),
                label="shutdown-close",
                wait=True,
            )
        self._audio_aliases.clear()
        self._collision_audio_alias = None
        self._click_audio_aliases = ()
        self._collision_audio_path = None
        self._collision_audio_ready = False
        self._audio_accepting = False
        try:
            self._audio_queue.put(None, timeout=1.0)
        except queue.Full:
            return
        self._audio_thread.join(timeout=3.0)

    def _save_preferences(self, position: bool = False) -> None:
        self.settings.update(
            {
                "followMouse": bool(self.follow_var.get()),
                "throwMode": bool(self.throw_var.get()),
                "fixedPosition": bool(self.fixed_var.get()),
                "absolutePosition": bool(self.absolute_var.get()),
                "followAccelerationLimit": int(self.acceleration_var.get()),
                "physicsEnabled": bool(self.physics_var.get()),
                "stunDurationMs": int(self.stun_duration_var.get()),
                "topmost": bool(self.topmost_var.get()),
                "scale": float(self.scale),
                "skin": self._active_skin_id,
                "soundProfile": self._selected_sound_profile(),
                "soundVolume": self._selected_sound_volume(),
            }
        )
        if position:
            self.settings["position"] = [self.root.winfo_x(), self.root.winfo_y()]
        if not self.qa_mode:
            _save_settings(self.settings)

    def _toggle_throw(self) -> None:
        self._record_interaction()
        self._set_stunned(False)
        self._stop_throw(persist=False)
        if self.throw_var.get():
            self.follow_var.set(False)
            self.fixed_var.set(False)
            self.absolute_var.set(False)
            self.settings["activeAbsolutePreset"] = None
        else:
            self.fixed_var.set(True)
        self._follow_paused = False
        self._reset_follow_state()
        self._reset_throw_state()
        self._save_preferences(position=True)
        self._refresh_absolute_preset_menu()
        self._refresh_size_menu()

    def _toggle_follow(self) -> None:
        self._record_interaction()
        self._set_stunned(False)
        if self.follow_var.get():
            self.throw_var.set(False)
            self._stop_throw(persist=False)
            self.fixed_var.set(False)
            self.absolute_var.set(False)
            self.settings["activeAbsolutePreset"] = None
            self._follow_paused = False
            self._reset_follow_state()
        else:
            self._follow_paused = False
            self._follow_velocity = [0.0, 0.0]
            self.settings["position"] = [self.root.winfo_x(), self.root.winfo_y()]
        self._save_preferences(position=not self.follow_var.get())
        self._refresh_size_menu()

    def _toggle_fixed(self) -> None:
        self._record_interaction()
        self._set_stunned(False)
        if self.fixed_var.get():
            self.throw_var.set(False)
            self._stop_throw(persist=False)
            self.follow_var.set(False)
            self.absolute_var.set(False)
            self.settings["activeAbsolutePreset"] = None
        self._follow_paused = False
        self._reset_follow_state()
        self._save_preferences(position=True)
        self._refresh_size_menu()

    def _toggle_absolute(self) -> None:
        self._record_interaction()
        self._set_stunned(False)
        if self.absolute_var.get():
            self.throw_var.set(False)
            self._stop_throw(persist=False)
            self.follow_var.set(False)
            self.fixed_var.set(False)
            self.settings["activeAbsolutePreset"] = None
        self._follow_paused = False
        self._reset_follow_state()
        self._save_preferences(position=True)
        self._refresh_absolute_preset_menu()
        self._refresh_size_menu()

    def _set_follow_acceleration_limit(self, selected: int) -> None:
        normalized = _normalize_acceleration_limit(selected)
        self.acceleration_var.set(normalized)
        self.settings["followAccelerationLimit"] = normalized
        self._save_preferences()

    def _toggle_physics(self) -> None:
        if not self.physics_var.get():
            self._set_stunned(False)
            self._follow_velocity = [0.0, 0.0]
        self._reset_follow_state()
        self._save_preferences()

    def _set_stun_duration(self, selected: int) -> None:
        normalized = _normalize_stun_duration(selected)
        self.stun_duration_var.set(normalized)
        self.settings["stunDurationMs"] = normalized
        self._save_preferences()

    def _save_absolute_preset(self, index: int) -> None:
        if not 0 <= index < ABSOLUTE_PRESET_LIMIT:
            return
        self.root.update_idletasks()
        self.settings["absolutePresets"][index] = {
            "position": [self.root.winfo_x(), self.root.winfo_y()],
            "scale": float(self.scale),
        }
        self._save_preferences(position=True)
        self._refresh_absolute_preset_menu()
        self._refresh_size_menu()

    def _apply_absolute_preset(self, index: int) -> None:
        if not 0 <= index < ABSOLUTE_PRESET_LIMIT:
            return
        preset = _normalize_absolute_preset(self.settings["absolutePresets"][index])
        if preset is None:
            return
        self.throw_var.set(False)
        self._stop_throw(persist=False)
        self.follow_var.set(False)
        self.fixed_var.set(False)
        self.absolute_var.set(True)
        self.settings["activeAbsolutePreset"] = index
        self._apply_scale(float(preset["scale"]), persist=False)
        x, y = self._clamp_position(*preset["position"])
        self._place_window(x, y, include_size=True)
        self.root.update_idletasks()
        self._reset_follow_state()
        self._save_preferences(position=True)
        self._refresh_absolute_preset_menu()

    def _clear_absolute_preset(self, index: int) -> None:
        if not 0 <= index < ABSOLUTE_PRESET_LIMIT:
            return
        self.settings["absolutePresets"][index] = None
        if self.settings.get("activeAbsolutePreset") == index:
            self.settings["activeAbsolutePreset"] = None
        self._save_preferences()
        self._refresh_absolute_preset_menu()

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", bool(self.topmost_var.get()))
        self._save_preferences()

    def _apply_scale(self, selected: float, persist: bool = True) -> None:
        try:
            selected = _clamp_scale(float(selected))
        except (TypeError, ValueError):
            return
        self.root.update_idletasks()
        old_x, old_y = self.root.winfo_x(), self.root.winfo_y()
        old_bounds = self.canvas.bbox("whale")
        if old_bounds:
            anchor_screen_x = old_x + (old_bounds[0] + old_bounds[2]) / 2
            anchor_screen_y = old_y + old_bounds[3]
        else:
            anchor_screen_x = old_x + self.width / 2
            anchor_screen_y = old_y + self.height
        self.scale = selected
        self._whale_image_cache.clear()
        self._place_window(old_x, old_y, include_size=True)
        self._draw_static()
        self.root.update_idletasks()
        new_bounds = self.canvas.bbox("whale")
        if new_bounds:
            target_x = round(anchor_screen_x - (new_bounds[0] + new_bounds[2]) / 2)
            target_y = round(anchor_screen_y - new_bounds[3])
        else:
            target_x, target_y = old_x, old_y
        target_x, target_y = self._clamp_position(target_x, target_y)
        self._place_window(target_x, target_y, include_size=True)
        self.root.update_idletasks()
        self._refresh_size_menu()
        self._reset_follow_state()
        if persist:
            if hasattr(self, "absolute_var") and self.absolute_var.get():
                self.settings["activeAbsolutePreset"] = None
                self._refresh_absolute_preset_menu()
            self._schedule_scale_save()

    def _schedule_scale_save(self) -> None:
        if self.qa_mode:
            return
        if self._scale_save_timer is not None:
            try:
                self.root.after_cancel(self._scale_save_timer)
            except self.tk.TclError:
                pass
        self._scale_save_timer = self.root.after(350, self._save_scale_preferences)

    def _save_scale_preferences(self) -> None:
        self._scale_save_timer = None
        self._save_preferences(position=True)

    def _toggle_autostart(self) -> None:
        desired = bool(self.autostart_var.get())
        try:
            _set_autostart(desired)
        except Exception as exc:
            self.autostart_var.set(not desired)
            self._dialog("开机自启动", f"设置失败：{_compact_error(exc)}", error=True)
            return
        state = "已开启" if desired else "已关闭"
        self._dialog("开机自启动", f"{state}。该设置仅作用于当前 Windows 用户。")

    def _check_updates(self) -> None:
        self._dialog(
            "检查更新",
            f"当前版本：V0.7 ({APP_VERSION})\n"
            "本按钮不联网，也不会自动下载或安装。\n"
            "请手动查看：https://github.com/mnb-zxc-920/codex--",
        )

    def _about(self) -> None:
        self._dialog(
            "关于作者",
            "Codex 小鲸鱼桌面挂件 V0.7\n"
            "Codex 适配与本地状态入口：OpenAI Codex\n"
            "常态立绘及鸭叫素材：MeteorNOX\n"
            "两套皮肤差分图：用户提供的非官方同人立绘\n"
            "软萌啵、水晶叮、木质嗒：本项目本地合成原创音效\n"
            "上游项目：DeepSeek-Balance-Whale-Widget（MIT）",
        )

    def _dialog(self, title: str, message: str, error: bool = False) -> None:
        self._last_dialog = (title, message)
        if self.qa_mode:
            return
        from tkinter import messagebox

        if error:
            messagebox.showerror(title, message, parent=self.root)
        else:
            messagebox.showinfo(title, message, parent=self.root)

    def _reset_follow_state(self, now: float | None = None) -> None:
        self.root.update_idletasks()
        self._follow_position = [float(self.root.winfo_x()), float(self.root.winfo_y())]
        self._follow_velocity = [0.0, 0.0]
        self._follow_last_tick = time.monotonic() if now is None else float(now)
        self._follow_target = None
        self._follow_cycle_started = self._follow_last_tick
        self._follow_cycle_active = False
        self._follow_last_speed = 0.0
        self._follow_last_ramp = 0.0
        self._follow_last_acceleration = 0.0

    def _reset_throw_state(self, now: float | None = None) -> None:
        self.root.update_idletasks()
        current = time.monotonic() if now is None else float(now)
        self._throw_dragging = False
        self._throw_active = False
        self._throw_position = [float(self.root.winfo_x()), float(self.root.winfo_y())]
        self._throw_velocity = [0.0, 0.0]
        self._throw_last_tick = current
        self._throw_samples = []

    def _record_throw_sample(
        self,
        x: float,
        y: float,
        now: float | None = None,
    ) -> None:
        current = time.monotonic() if now is None else float(now)
        self._throw_samples.append((current, float(x), float(y)))
        cutoff = current - THROW_SAMPLE_WINDOW_SECONDS
        while len(self._throw_samples) > 2 and self._throw_samples[1][0] < cutoff:
            self._throw_samples.pop(0)
        self._throw_samples = self._throw_samples[-12:]

    def _stop_throw(self, persist: bool = True) -> None:
        self._throw_dragging = False
        self._throw_active = False
        self._throw_velocity = [0.0, 0.0]
        self._throw_position = [float(self.root.winfo_x()), float(self.root.winfo_y())]
        self._throw_last_tick = time.monotonic()
        self._throw_samples = []
        if persist:
            self._save_preferences(position=True)

    def _advance_throw(self, now: float) -> dict[str, Any]:
        current = float(now)
        if self._throw_last_tick is None:
            self._throw_last_tick = current
        if self._stunned and current >= self._stun_until:
            self._set_stunned(False, current)
        dt = max(0.001, min(current - float(self._throw_last_tick), 0.032))
        x, y = self._throw_position
        vx, vy = self._throw_velocity
        speed_before = math.hypot(vx, vy)
        drag = math.exp(-THROW_FREE_FLIGHT_DRAG * dt)
        vx, vy = vx * drag, vy * drag
        x += vx * dt
        y += vy * dt
        (
            x,
            y,
            vx,
            vy,
            collision_sides,
            impact_speed,
            rebound_multiplier,
        ) = self._resolve_boundary_collisions(x, y, vx, vy, current)
        speed = math.hypot(vx, vy)
        self._throw_position = [x, y]
        self._throw_velocity = [vx, vy]
        self._throw_last_tick = current
        self._place_window(x, y)
        stopped = speed < THROW_STOP_SPEED
        if stopped:
            self._throw_position = [float(round(x)), float(round(y))]
            self._place_window(*self._throw_position)
            self._stop_throw(persist=not self.qa_mode)
        return {
            "mode": "throw",
            "dt": dt,
            "speedBefore": speed_before,
            "speed": 0.0 if stopped else speed,
            "collision": bool(collision_sides),
            "collisionSides": collision_sides,
            "impactSpeed": impact_speed,
            "reboundMultiplier": rebound_multiplier,
            "stopped": stopped,
            "position": [round(x, 3), round(y, 3)],
        }

    def _physics_enabled(self) -> bool:
        if hasattr(self, "physics_var"):
            return bool(self.physics_var.get())
        return bool(self.settings.get("physicsEnabled", True))

    @staticmethod
    def _cap_velocity(vx: float, vy: float, maximum: float) -> tuple[float, float]:
        speed = math.hypot(vx, vy)
        if speed <= maximum or speed <= 0:
            return vx, vy
        factor = maximum / speed
        return vx * factor, vy * factor

    def _resolve_boundary_collisions(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        now: float,
    ) -> tuple[float, float, float, float, list[str], float, float]:
        min_x, min_y, max_x, max_y = (float(value) for value in self._position_bounds())
        collision_sides: list[str] = []
        impact_speed = 0.0
        rebound_multipliers: list[float] = []
        stunned_before = self._stunned
        bounce_threshold = PHYSICS_STUN_BOUNCE_MIN if stunned_before else FOLLOW_BOUNCE_THRESHOLD
        physics_enabled = self._physics_enabled()

        if x < min_x or x > max_x:
            side = "left" if x < min_x else "right"
            x = min_x if x < min_x else max_x
            normal_speed = abs(vx)
            if physics_enabled and normal_speed >= bounce_threshold:
                multiplier = (
                    PHYSICS_STUN_RESTITUTION
                    if stunned_before
                    else _impact_rebound_multiplier(normal_speed)
                )
                vx = -vx * multiplier
                vy *= PHYSICS_TANGENTIAL_RETENTION
                collision_sides.append(side)
                impact_speed = max(impact_speed, normal_speed)
                rebound_multipliers.append(multiplier)
            else:
                vx = 0.0

        if y < min_y or y > max_y:
            side = "top" if y < min_y else "bottom"
            y = min_y if y < min_y else max_y
            normal_speed = abs(vy)
            if physics_enabled and normal_speed >= bounce_threshold:
                multiplier = (
                    PHYSICS_STUN_RESTITUTION
                    if stunned_before
                    else _impact_rebound_multiplier(normal_speed)
                )
                vy = -vy * multiplier
                vx *= PHYSICS_TANGENTIAL_RETENTION
                collision_sides.append(side)
                impact_speed = max(impact_speed, normal_speed)
                rebound_multipliers.append(multiplier)
            else:
                vy = 0.0

        rebound_multiplier = max(rebound_multipliers, default=0.0)
        if collision_sides:
            vx, vy = self._cap_velocity(vx, vy, PHYSICS_FREE_FLIGHT_MAX_SPEED)
            self._last_rebound_multiplier = rebound_multiplier
            if not stunned_before:
                self._set_stunned(True, now, impact_speed, collision_sides)
            self._on_edge_collision(now, collision_sides, impact_speed)
        return x, y, vx, vy, collision_sides, impact_speed, rebound_multiplier

    def _advance_stunned(
        self,
        target: tuple[float, float],
        now: float,
    ) -> dict[str, Any]:
        dt = max(0.001, min(float(now) - float(self._follow_last_tick), 0.032))
        x, y = self._follow_position
        vx, vy = self._follow_velocity
        speed_before = math.hypot(vx, vy)
        drag = math.exp(-PHYSICS_FREE_FLIGHT_DRAG * dt)
        vx, vy = vx * drag, vy * drag
        x += vx * dt
        y += vy * dt
        (
            x,
            y,
            vx,
            vy,
            collision_sides,
            impact_speed,
            rebound_multiplier,
        ) = self._resolve_boundary_collisions(x, y, vx, vy, float(now))
        speed = math.hypot(vx, vy)
        remaining = math.hypot(target[0] - x, target[1] - y)
        self._follow_position = [x, y]
        self._follow_velocity = [vx, vy]
        self._follow_target = target
        self._follow_last_tick = float(now)
        self._follow_last_speed = speed
        self._follow_last_ramp = 0.0
        self._follow_last_acceleration = 0.0
        self._place_window(x, y)
        return {
            "mode": "stunned",
            "dt": dt,
            "speedBefore": speed_before,
            "speed": speed,
            "ramp": 0.0,
            "acceleration": 0.0,
            "maxAcceleration": 0.0,
            "distance": remaining,
            "collision": bool(collision_sides),
            "collisionSides": collision_sides,
            "impactSpeed": impact_speed,
            "reboundMultiplier": rebound_multiplier,
            "stunRemainingMs": max(0, round((self._stun_until - now) * 1000)),
        }

    def _advance_follow(self, target_x: float, target_y: float, now: float) -> dict[str, Any]:
        if self._follow_last_tick is None:
            self._reset_follow_state(now)
        target = (float(target_x), float(target_y))
        if self._stunned and self._physics_enabled() and float(now) < self._stun_until:
            return self._advance_stunned(target, float(now))
        if self._stunned:
            self._set_stunned(False, float(now))
            self._follow_velocity = [value * 0.25 for value in self._follow_velocity]

        dt = max(0.001, min(float(now) - float(self._follow_last_tick), 0.032))
        x, y = self._follow_position
        vx, vy = self._follow_velocity
        target_motion = (
            math.hypot(target[0] - self._follow_target[0], target[1] - self._follow_target[1])
            if self._follow_target is not None
            else math.inf
        )
        distance = math.hypot(target[0] - x, target[1] - y)
        speed_before = math.hypot(vx, vy)
        if not self._follow_cycle_active and (distance > 10 or target_motion > 4):
            self._follow_cycle_active = True
            self._follow_cycle_started = float(now)
        elapsed = max(0.0, float(now) - self._follow_cycle_started)
        phase = min(elapsed / FOLLOW_RAMP_SECONDS, 1.0) if self._follow_cycle_active else 0.0
        ramp = phase * phase * (3.0 - 2.0 * phase)
        late_ramp = ramp * ramp
        stiffness = 1.8 + 6.2 * ramp + 10.0 * late_ramp
        damping = 2.3 + 1.1 * ramp
        ax = (target[0] - x) * stiffness - vx * damping
        ay = (target[1] - y) * stiffness - vy * damping
        acceleration = math.hypot(ax, ay)
        configured_acceleration = float(
            _normalize_acceleration_limit(
                self.acceleration_var.get()
                if hasattr(self, "acceleration_var")
                else self.settings["followAccelerationLimit"]
            )
        )
        max_acceleration = 2600.0 + (configured_acceleration - 2600.0) * late_ramp
        if acceleration > max_acceleration:
            factor = max_acceleration / acceleration
            ax, ay = ax * factor, ay * factor
            acceleration = max_acceleration
        vx += ax * dt
        vy += ay * dt
        speed = math.hypot(vx, vy)
        max_speed = 180.0 + (FOLLOW_MAX_SPEED - 180.0) * (ramp ** 1.45)
        if speed > max_speed:
            factor = max_speed / speed
            vx, vy = vx * factor, vy * factor
        x += vx * dt
        y += vy * dt
        (
            x,
            y,
            vx,
            vy,
            collision_sides,
            impact_speed,
            rebound_multiplier,
        ) = self._resolve_boundary_collisions(x, y, vx, vy, float(now))
        speed = math.hypot(vx, vy)
        remaining = math.hypot(target[0] - x, target[1] - y)
        if not self._stunned and remaining < 2.5 and speed < 8.0 and target_motion < 1.5:
            x, y = target
            vx, vy = 0.0, 0.0
            speed = 0.0
            self._follow_cycle_active = False
        self._follow_position = [x, y]
        self._follow_velocity = [vx, vy]
        self._follow_target = target
        self._follow_last_tick = float(now)
        self._follow_last_speed = speed
        self._follow_last_ramp = ramp
        self._follow_last_acceleration = acceleration
        self._place_window(x, y)
        return {
            "mode": "stunned-start" if self._stunned else "follow",
            "dt": dt,
            "speedBefore": speed_before,
            "speed": speed,
            "ramp": ramp,
            "acceleration": acceleration,
            "maxAcceleration": max_acceleration,
            "distance": remaining,
            "collision": bool(collision_sides),
            "collisionSides": collision_sides,
            "impactSpeed": impact_speed,
            "reboundMultiplier": rebound_multiplier,
            "stunRemainingMs": max(0, round((self._stun_until - now) * 1000)),
        }

    def _on_edge_collision(self, now: float, sides: list[str], impact_speed: float) -> bool:
        self._collision_count += 1
        played = (
            self._collision_last_sound_at is None
            or (now - self._collision_last_sound_at) * 1000 >= COLLISION_SOUND_COOLDOWN_MS
        )
        if played:
            self._collision_last_sound_at = now
            self._collision_sound_count += 1
            if not self.qa_mode:
                if not self._play_preloaded_collision_audio():
                    try:
                        self.root.bell()
                    except self.tk.TclError:
                        pass
        self._collision_history.append(
            {
                "sides": list(sides),
                "impactSpeed": round(float(impact_speed), 3),
                "reboundMultiplier": round(float(self._last_rebound_multiplier), 3),
                "stunned": bool(self._stunned),
                "sound": played,
            }
        )
        self._collision_history = self._collision_history[-12:]
        return played

    def _follow_tick(self) -> None:
        if self.stop.is_set():
            return
        now = time.monotonic()
        if not self.qa_mode and self.throw_var.get() and self._throw_active:
            self._advance_throw(now)
        elif (
            not self.qa_mode
            and self.throw_var.get()
            and self._stunned
            and now >= self._stun_until
        ):
            self._set_stunned(False, now)
        moving_under_physics = (
            self._stunned and self._physics_enabled() and not self.throw_var.get()
        )
        if not self.qa_mode and not self._follow_paused and not self.throw_var.get() and (
            self.follow_var.get() or moving_under_physics
        ):
            if self.follow_var.get() and not self._stunned:
                pointer_x = self.root.winfo_pointerx()
                pointer_y = self.root.winfo_pointery()
                target_x, target_y = self._clamp_position(
                    pointer_x - self._s(250),
                    pointer_y - self._s(120),
                )
            else:
                target_x, target_y = self._follow_target or tuple(self._follow_position)
            self._advance_follow(target_x, target_y, now)
        elif self._follow_last_tick is not None:
            self._follow_last_tick = now
        self.root.after(FOLLOW_INTERVAL_MS, self._follow_tick)

    def _drain_updates(self) -> None:
        latest = None
        try:
            while True:
                latest = self.output.get_nowait()
        except queue.Empty:
            pass
        if latest is not None:
            self._render(latest)
        if not self.stop.is_set():
            self.root.after(300, self._drain_updates)

    def _render(self, snapshot: dict[str, Any]) -> None:
        self._latest_snapshot = snapshot
        task = snapshot.get("task") or {}
        state = task.get("state", "unknown")
        self.canvas.itemconfigure(
            self.status_dot,
            fill=STATUS_DOT_COLORS.get(state, STATUS_DOT_COLORS["unknown"]),
        )
        self.canvas.itemconfigure(
            self.status_text, text=task.get("label", "状态不可用"), fill="#273970",
        )
        self.canvas.itemconfigure(self.detail_text, text=task.get("detail", ""))
        quota = snapshot.get("quota") or {}
        if quota.get("available"):
            remaining = _format_percent(quota.get("remainingPercent"))
            self.canvas.itemconfigure(self.quota_text, text=f"Codex 余量 {remaining}%")
            self.canvas.itemconfigure(
                self.reset_text,
                text=(
                    f"{_format_reset(quota.get('resetsAt'))} · "
                    f"{_format_reset_credit_count(quota.get('resetCreditCount'))}"
                ),
            )
        else:
            self.canvas.itemconfigure(self.quota_text, text="Codex 余量不可用")
            self.canvas.itemconfigure(
                self.reset_text,
                text=(
                    "没有用猜测值代替 · "
                    f"{_format_reset_credit_count(quota.get('resetCreditCount'))}"
                ),
            )

    def close(self) -> None:
        if self.stop.is_set():
            return
        self.stop.set()
        self._cancel_bubble_timers()
        if self._scale_save_timer is not None:
            try:
                self.root.after_cancel(self._scale_save_timer)
            except self.tk.TclError:
                pass
            self._scale_save_timer = None
            if not self.qa_mode:
                self._save_preferences(position=True)
        self._shutdown_audio()
        self.root.after(50, self.root.destroy)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()


def _run_self_test() -> int:
    failures: list[str] = []
    tests = 0

    def check(condition: bool, name: str) -> None:
        nonlocal tests
        tests += 1
        if not condition:
            failures.append(name)

    rate = normalize_rate_limits(
        {
            "rateLimitResetCredits": {"availableCount": 2, "credits": [{"id": "not-retained"}]},
            "rateLimits": {
                "primary": {
                    "usedPercent": 34,
                    "windowDurationMins": 10080,
                    "resetsAt": 123,
                }
            },
        }
    )
    check(rate.get("remainingPercent") == 66.0, "quota normalization")
    check(
        rate.get("resetCreditCount") == 2
        and "credits" not in rate
        and _format_reset_credit_count(2) == "重置卡 2 张",
        "reset credits count-only normalization",
    )

    with tempfile.TemporaryDirectory(prefix="codex-whale-v0.7-") as folder:
        path = Path(folder) / "rollout.jsonl"
        started = {
            "timestamp": "2026-08-24T00:00:00Z",
            "type": "event_msg",
            "payload": {"type": "task_started", "turn_id": "turn-1"},
        }
        path.write_text(json.dumps(started) + "\n", encoding="utf-8")
        cache = LifecycleCache()
        life, _ = cache.observe(str(path))
        check(bool(life and life.event == "task_started"), "task_started parsing")
        old_time = time.time() - LONG_RUNNING_SECONDS - 60
        os.utime(path, (old_time, old_time))
        long_running = derive_task_status(
            [
                {
                    "id": "thread-art",
                    "path": str(path),
                    "name": "小鲸鱼立绘工坊｜用户主控",
                    "updatedAt": time.time(),
                }
            ],
            cache,
            now=time.time(),
        )
        check(
            long_running.get("state") == "working"
            and long_running.get("label") == "1 个任务进行中"
            and long_running.get("detail") == "小鲸鱼立绘工坊｜用户主控"
            and long_running.get("longRunningCount") == 1,
            "long-running task remains working with display name",
        )
        completed = {
            "timestamp": "2026-08-24T00:01:00Z",
            "type": "event_msg",
            "payload": {"type": "task_complete", "turn_id": "turn-1"},
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(completed) + "\n")
        life, _ = cache.observe(str(path))
        check(bool(life and life.event == "task_complete"), "incremental task_complete parsing")
        task = derive_task_status(
            [{"id": "thread-1", "path": str(path), "updatedAt": time.time()}],
            cache,
        )
        check(task.get("state") == "idle", "idle state derivation")

        settings_path = Path(folder) / "settings.json"
        _save_settings(
            {
                "throwMode": False,
                "followMouse": True,
                "fixedPosition": True,
                "absolutePosition": True,
                "absolutePresets": [
                    {"position": [120, 80], "scale": 1.85},
                    {"position": ["bad", 80], "scale": 1.0},
                    {"position": [-500, 40], "scale": 9.0},
                    {"position": [1, 2], "scale": 1.0},
                ],
                "activeAbsolutePreset": 0,
                "followAccelerationLimit": 12700,
                "physicsEnabled": False,
                "stunDurationMs": 2050,
                "topmost": False,
                "scale": 1.85,
                "skin": "endfield-yu",
                "soundProfile": "crystal-chime",
                "soundVolume": 73,
                "position": [120, 80],
            },
            settings_path,
        )
        loaded = _load_settings(settings_path)
        check(
            loaded == {
                "throwMode": False,
                "followMouse": True,
                "fixedPosition": False,
                "absolutePosition": False,
                "absolutePresets": [
                    {"position": [120, 80], "scale": 1.85},
                    None,
                    {"position": [-500, 40], "scale": SCALE_MAX},
                ],
                "activeAbsolutePreset": None,
                "followAccelerationLimit": 12800,
                "physicsEnabled": False,
                "stunDurationMs": 2200,
                "topmost": False,
                "scale": 1.85,
                "skin": "endfield-yu",
                "soundProfile": "crystal-chime",
                "soundVolume": 75,
                "position": [120, 80],
            },
            "settings atomic roundtrip and exclusivity",
        )

        absolute = _normalize_settings(
            {
                "followMouse": False,
                "fixedPosition": True,
                "absolutePosition": True,
                "absolutePresets": [{"position": [-120, 60], "scale": 0.75}],
                "activeAbsolutePreset": 0,
            }
        )
        check(
            absolute["absolutePosition"]
            and not absolute["fixedPosition"]
            and not absolute["followMouse"]
            and absolute["activeAbsolutePreset"] == 0,
            "absolute position mode exclusivity",
        )
        check(
            len(absolute["absolutePresets"]) == ABSOLUTE_PRESET_LIMIT
            and absolute["absolutePresets"][1:] == [None, None],
            "three absolute presets only",
        )

        throw_mode = _normalize_settings(
            {
                "throwMode": True,
                "followMouse": True,
                "fixedPosition": True,
                "absolutePosition": True,
            }
        )
        check(
            throw_mode["throwMode"]
            and not throw_mode["followMouse"]
            and not throw_mode["fixedPosition"]
            and not throw_mode["absolutePosition"],
            "throw mode exclusivity",
        )

    check(MENU_LABELS == (
        "拖拽甩出",
        "跟随鼠标",
        "固定位置",
        "固定屏幕绝对位置",
        "绝对位置预设",
        "窗口置顶",
        "调整大小",
        "更换皮肤",
        "声音设置",
        "开机自启动",
        "检查更新",
        "关于作者",
        "退出程序",
    ), "menu order contract")
    check(
        FOLLOW_SUBMENU_LABELS == (
            "启用跟随鼠标",
            "跟随加速度上限",
            "启用物理碰撞引擎",
            "撞晕时长",
        ),
        "follow submenu contract",
    )
    check('Start-CodexWhale.ps1"' in _autostart_command(), "autostart command binding")
    check(
        all((_widget_root() / "assets" / name).is_file() for name in ("Ya1.mp3", "Ya2.mp3")),
        "duck audio assets",
    )
    check(
        _normalize_skin("endfield-yu") == "endfield-yu"
        and _normalize_skin("unknown") == DEFAULT_SKIN_ID
        and _normalize_sound_profile("wood-tap") == "wood-tap"
        and _normalize_sound_profile("unknown") == DEFAULT_SOUND_PROFILE
        and _normalize_sound_volume(73) == 75,
        "skin sound and volume normalization",
    )
    check(not hasattr(WhaleWidget, "_animate"), "continuous breathing removed")
    check(not hasattr(WhaleWidget, "_set_whale_offset"), "click translation removed")
    check(_clamp_scale(0.1) == SCALE_MIN, "scale minimum clamp")
    check(_clamp_scale(3.0) == SCALE_MAX, "scale maximum clamp")
    check(_scale_from_percent(125) == 1.25, "percentage scale conversion")
    check(
        SCALE_PERCENT_OPTIONS == (50, 75, 100, 125, 150, 175, 200, 220),
        "percentage scale menu contract",
    )
    check(not hasattr(WhaleWidget, "_on_mousewheel"), "mouse-wheel scaling removed")
    check(_normalize_acceleration_limit(9000) == 9600, "follow acceleration option normalization")
    check(_normalize_stun_duration(2000) == 2200, "stun duration option normalization")
    check(
        FOLLOW_INTERVAL_MS <= 20
        and FOLLOW_RAMP_SECONDS >= 1.0
        and FOLLOW_ACCELERATION_DEFAULT > 4800,
        "faster late accelerated follow constants",
    )
    check(
        FOLLOW_BOUNCE_THRESHOLD > 0
        and 0 < PHYSICS_STUN_RESTITUTION < 1
        and _impact_rebound_multiplier(1500) > _impact_rebound_multiplier(800) > 1
        and COLLISION_SOUND_COOLDOWN_MS >= 300,
        "impact-scaled edge collision constants",
    )
    check(0 < DISPLAY_ALPHA_THRESHOLD < 255, "color-key-safe alpha threshold")
    check(
        WORKING_SOURCE_PX >= math.ceil(max(PET_BASE_SIZE) * SCALE_MAX)
        and len(CLICK_DEFORMATION_FRAMES) == 4
        and CLICK_DEFORMATION_FRAMES[-1][1:] == (1.0, 1.0),
        "bounded working source and prewarm frames",
    )
    source_text = Path(__file__).read_text(encoding="utf-8")
    mci_call_token = "ctypes.windll.winmm." + "mciSendStringW("
    check(
        source_text.count(mci_call_token) == 1
        and "target=self._audio_worker" in source_text
        and "self._audio_queue.put_nowait(job)" in source_text,
        "all MCI calls isolated in bounded audio worker",
    )
    check(
        set(STATUS_DOT_COLORS) == {"working", "idle", "attention", "unknown"}
        and len(set(STATUS_DOT_COLORS.values())) == 4,
        "state dot color contract",
    )
    skin_assets_complete = True
    for definition in SKIN_DEFINITIONS.values():
        asset_root = _widget_root() / "assets"
        idle_root = asset_root / str(definition["idleRoot"])
        paths = [
            asset_root / str(definition["normal"]),
            asset_root / str(definition["stunned"]),
            *(idle_root / name for name in definition["idleFiles"]),
        ]
        render_root = asset_root / "render-cache" / _normalize_skin(
            next(
                skin_id
                for skin_id, candidate in SKIN_DEFINITIONS.items()
                if candidate is definition
            )
        )
        paths.extend(
            [
                render_root / "manifest.json",
                render_root / "normal.png",
                render_root / "stunned.png",
                *(render_root / "idle" / name for name in definition["idleFiles"]),
            ]
        )
        skin_assets_complete = skin_assets_complete and len(definition["idleFiles"]) == 7
        skin_assets_complete = skin_assets_complete and all(path.is_file() for path in paths)
    check(
        IDLE_VARIANT_SECONDS == 300
        and SKIN_IDS == ("deepseek-whale", "endfield-yu")
        and skin_assets_complete,
        "two complete skins with seven idle variants each",
    )
    original_sound_contract = True
    original_sound_paths = [
        _widget_root() / "assets" / SOUND_PROFILE_DEFINITIONS[profile]["files"][0]
        for profile in SOUND_PROFILE_IDS
        if profile != DEFAULT_SOUND_PROFILE
    ]
    try:
        for path in original_sound_paths:
            with wave.open(str(path), "rb") as stream:
                original_sound_contract = original_sound_contract and (
                    stream.getnchannels() == 1
                    and stream.getsampwidth() == 2
                    and stream.getframerate() == 44_100
                    and stream.getnframes() > 0
                )
    except (OSError, wave.Error):
        original_sound_contract = False
    check(
        len(SOUND_PROFILE_IDS) == 4
        and SOUND_VOLUME_OPTIONS == (0, 25, 50, 75, 100)
        and original_sound_contract,
        "four sound profiles and five volume levels",
    )
    throw_vx, throw_vy = _throw_velocity_from_samples(
        [(10.0, 100.0, 100.0), (10.1, 220.0, 140.0)]
    )
    check(
        throw_vx > 0
        and throw_vy > 0
        and THROW_MIN_SPEED < math.hypot(throw_vx, throw_vy) <= PHYSICS_FREE_FLIGHT_MAX_SPEED,
        "throw velocity from recent drag samples",
    )

    print(json.dumps({"ok": not failures, "tests": tests, "failures": failures}, ensure_ascii=False))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--snapshot", action="store_true", help="输出一次脱敏只读状态并退出")
    parser.add_argument("--self-test", action="store_true", help="运行本地解析自测")
    parser.add_argument("--smoke-seconds", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--qa-report", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.self_test:
        return _run_self_test()
    if args.snapshot:
        try:
            print(json.dumps(SnapshotReader().read_once(), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"ok": False, "error": _compact_error(exc)}, ensure_ascii=False, indent=2))
            return 2

    mutex = object() if args.qa_report or args.smoke_seconds is not None else _single_instance()
    if mutex is None:
        return 0
    try:
        widget = WhaleWidget(smoke_seconds=args.smoke_seconds, qa_mode=args.qa_report)
        if args.qa_report:
            from types import SimpleNamespace

            initial: dict[str, Any] = {}

            def whale_event(dx: int = 0, dy: int = 0) -> Any:
                bounds = widget.canvas.bbox("whale") or (0, 0, 0, 0)
                return SimpleNamespace(
                    x_root=widget.root.winfo_rootx() + (bounds[0] + bounds[2]) // 2 + dx,
                    y_root=widget.root.winfo_rooty() + (bounds[1] + bounds[3]) // 2 + dy,
                )

            def begin_report() -> None:
                widget.root.update_idletasks()
                initial["whaleCoords"] = list(widget.canvas.coords(widget.whale_item))
                initial["bubbleHidden"] = not widget.bubble_visible()
                widget.root.after(700, after_idle)

            def after_idle() -> None:
                widget.root.update_idletasks()
                initial["idleCoords"] = list(widget.canvas.coords(widget.whale_item))
                initial["noIdleMotion"] = initial["whaleCoords"] == initial["idleCoords"]
                event = whale_event()
                widget._drag_start(event)
                widget._drag_release(event)
                initial["bubbleShownOnClick"] = widget.bubble_visible()
                initial["clickCount"] = widget._click_count
                widget.root.after(280, capture_click_animation)

            def capture_click_animation() -> None:
                widget.root.update_idletasks()
                initial["bubbleStages"] = list(widget._bubble_stage_history)
                initial["deformationFrames"] = list(widget._click_deformation_history)
                initial["postClickCoords"] = list(widget.canvas.coords(widget.whale_item))
                initial["bubbleContentVisible"] = (
                    widget.canvas.itemcget(widget.status_text, "state") != "hidden"
                )
                detail_bounds = widget.canvas.bbox(widget.detail_text)
                status_bounds = widget.canvas.bbox(widget.status_text)
                dot_bounds = widget.canvas.bbox(widget.status_dot)
                quota_bounds = widget.canvas.bbox(widget.quota_text)
                reset_bounds = widget.canvas.bbox(widget.reset_text)
                status_center = widget._s(164)
                initial["statusTextCentered"] = bool(
                    status_bounds
                    and abs((status_bounds[0] + status_bounds[2]) / 2 - status_center)
                    <= max(2, widget._s(2))
                )
                initial["detailTextCentered"] = bool(
                    detail_bounds
                    and abs((detail_bounds[0] + detail_bounds[2]) / 2 - status_center)
                    <= max(2, widget._s(2))
                )
                initial["largeStatusPanelRemoved"] = not hasattr(widget, "status_panel")
                rendered_dot_colors: dict[str, str] = {}
                for state_name in STATUS_DOT_COLORS:
                    widget._render(
                        {
                            "task": {
                                "state": state_name,
                                "label": "状态颜色验收",
                                "detail": "V0.7 本机交互验收",
                            },
                            "quota": {
                                "available": True,
                                "remainingPercent": 66.0,
                                "resetCreditCount": 1,
                            },
                        }
                    )
                    rendered_dot_colors[state_name] = widget.canvas.itemcget(
                        widget.status_dot, "fill"
                    )
                initial["statusDotStateColors"] = rendered_dot_colors == STATUS_DOT_COLORS
                widget._render(
                    {
                        "task": {
                            "state": "idle",
                            "label": "Codex 暂时空闲",
                            "detail": "V0.7 本机交互验收",
                        },
                        "quota": {
                            "available": True,
                            "remainingPercent": 66.0,
                            "resetCreditCount": 1,
                        },
                    }
                )
                initial["bubbleLayoutReadable"] = bool(
                    status_bounds
                    and detail_bounds
                    and dot_bounds
                    and quota_bounds
                    and reset_bounds
                    and detail_bounds[3] < quota_bounds[1]
                    and quota_bounds[3] <= reset_bounds[1] + 2
                    and dot_bounds[2] < status_bounds[0]
                    and initial["statusTextCentered"]
                    and initial["detailTextCentered"]
                    and initial["largeStatusPanelRemoved"]
                    and initial["statusDotStateColors"]
                )
                widget.root.after(BUBBLE_MS + 500, finish_report)

            def finish_report() -> None:
                widget.root.update_idletasks()
                initial["bubbleHiddenAfterMs"] = not widget.bubble_visible()
                old_x, old_y = widget.root.winfo_x(), widget.root.winfo_y()
                widget.fixed_var.set(False)
                start = whale_event()
                widget._drag_start(start)
                widget._drag_move(
                    SimpleNamespace(x_root=start.x_root - 55, y_root=start.y_root + 35)
                )
                widget._drag_release(
                    SimpleNamespace(x_root=start.x_root - 55, y_root=start.y_root + 35)
                )
                widget.root.update_idletasks()
                new_x, new_y = widget.root.winfo_x(), widget.root.winfo_y()
                original_scale = widget.scale
                wheel_bindings_removed = all(
                    not widget.canvas.bind(sequence)
                    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>")
                )
                widget._apply_scale(_scale_from_percent(125), persist=False)
                widget.root.update_idletasks()
                proportion_scale = widget.scale
                proportion_size = [widget.root.winfo_width(), widget.root.winfo_height()]
                widget._apply_scale(_scale_from_percent(SCALE_PERCENT_OPTIONS[0]), persist=False)
                widget.root.update_idletasks()
                minimum_scale = widget.scale
                minimum_size = [widget.root.winfo_width(), widget.root.winfo_height()]
                widget._apply_scale(_scale_from_percent(SCALE_PERCENT_OPTIONS[-1]), persist=False)
                widget.root.update_idletasks()
                maximum_scale = widget.scale
                maximum_size = [widget.root.winfo_width(), widget.root.winfo_height()]
                widget._apply_scale(original_scale, persist=False)
                widget.root.update_idletasks()
                widget.follow_var.set(True)
                widget._toggle_follow()
                follow_disables_fixed = not widget.fixed_var.get() and not widget.absolute_var.get()
                widget.fixed_var.set(True)
                widget._toggle_fixed()
                fixed_disables_follow = not widget.follow_var.get() and not widget.absolute_var.get()

                widget.absolute_var.set(True)
                widget._toggle_absolute()
                absolute_disables_other_modes = (
                    widget.absolute_var.get()
                    and not widget.follow_var.get()
                    and not widget.fixed_var.get()
                )
                widget.absolute_var.set(False)
                widget._toggle_absolute()

                widget._apply_scale(1.15, persist=False)
                widget._place_window(260, 190, include_size=True)
                widget.root.update_idletasks()
                widget._save_absolute_preset(0)
                saved_preset = dict(widget.settings["absolutePresets"][0])
                widget._apply_scale(0.80, persist=False)
                widget._place_window(430, 280, include_size=True)
                widget.root.update_idletasks()
                widget._apply_absolute_preset(0)
                widget.root.update_idletasks()
                applied_preset = {
                    "position": [widget.root.winfo_x(), widget.root.winfo_y()],
                    "scale": widget.scale,
                }
                absolute_preset_applied = (
                    applied_preset["position"] == saved_preset["position"]
                    and applied_preset["scale"] == saved_preset["scale"]
                    and widget.settings.get("activeAbsolutePreset") == 0
                )
                absolute_before_drag = tuple(applied_preset["position"])
                absolute_before_scale = widget.scale
                absolute_event = whale_event()
                widget._drag_start(absolute_event)
                widget._drag_move(
                    SimpleNamespace(
                        x_root=absolute_event.x_root + 90,
                        y_root=absolute_event.y_root + 55,
                    )
                )
                widget._drag_release(
                    SimpleNamespace(
                        x_root=absolute_event.x_root + 90,
                        y_root=absolute_event.y_root + 55,
                    )
                )
                widget.root.update_idletasks()
                absolute_drag_locked = (
                    widget.root.winfo_x(), widget.root.winfo_y()
                ) == absolute_before_drag
                widget._apply_scale(_scale_from_percent(150))
                absolute_scale_resized = (
                    widget.scale > absolute_before_scale
                    and widget.absolute_var.get()
                    and widget.settings.get("activeAbsolutePreset") is None
                )
                widget.absolute_var.set(False)
                widget._toggle_absolute()

                widget._apply_scale(original_scale, persist=False)
                widget.root.update_idletasks()
                min_edge_x, min_edge_y, max_edge_x, max_edge_y = widget._position_bounds()
                screen_left, screen_top, screen_right, screen_bottom = widget._screen_bounds()
                widget._place_window(min_edge_x, min_edge_y, include_size=True)
                widget.root.update_idletasks()
                visible_at_min = widget._visible_whale_bounds()
                visible_edge_alignment = bool(
                    visible_at_min
                    and widget.root.winfo_x() + visible_at_min[0] == screen_left
                    and widget.root.winfo_y() + visible_at_min[1] == screen_top
                    and max_edge_x + visible_at_min[2] == screen_right
                    and max_edge_y + visible_at_min[3] == screen_bottom
                )
                visible_edge_coordinates = {
                    "window": [widget.root.winfo_x(), widget.root.winfo_y()],
                    "visibleBounds": list(visible_at_min or ()),
                    "visibleLeft": (
                        widget.root.winfo_x() + visible_at_min[0]
                        if visible_at_min else None
                    ),
                    "visibleTop": (
                        widget.root.winfo_y() + visible_at_min[1]
                        if visible_at_min else None
                    ),
                    "screen": [screen_left, screen_top, screen_right, screen_bottom],
                }
                widget._place_window(200, 180, include_size=True)
                widget.root.update_idletasks()
                widget.follow_var.set(True)
                widget.fixed_var.set(False)
                widget.absolute_var.set(False)
                widget._set_follow_acceleration_limit(FOLLOW_ACCELERATION_DEFAULT)
                widget._reset_follow_state(now=1000.0)
                follow_positions: list[tuple[float, float]] = []
                follow_speeds: list[float] = []
                follow_accelerations: list[float] = []
                follow_caps: list[float] = []
                _, _, follow_target_x, follow_target_y = widget._position_bounds()
                for index in range(1, 91):
                    telemetry = widget._advance_follow(
                        float(follow_target_x),
                        float(follow_target_y),
                        1000.0 + index * 0.016,
                    )
                    follow_positions.append(tuple(widget._follow_position))
                    follow_speeds.append(telemetry["speed"])
                    follow_accelerations.append(telemetry["acceleration"])
                    follow_caps.append(telemetry["maxAcceleration"])
                step_lengths = [
                    math.hypot(
                        follow_positions[index][0] - follow_positions[index - 1][0],
                        follow_positions[index][1] - follow_positions[index - 1][1],
                    )
                    for index in range(1, len(follow_positions))
                ]
                position_before_inertia = tuple(widget._follow_position)
                widget._advance_follow(
                    float(follow_target_x),
                    float(follow_target_y),
                    1000.0 + 91 * 0.016,
                )
                inertia_distance = math.hypot(
                    widget._follow_position[0] - position_before_inertia[0],
                    widget._follow_position[1] - position_before_inertia[1],
                )
                widget.root.update_idletasks()
                catch = whale_event()
                widget._drag_start(catch)
                widget._drag_release(catch)
                follow_click_freezes = not widget.follow_var.get() and widget.fixed_var.get()

                min_x, min_y, max_x, max_y = widget._position_bounds()
                collision_y = float(min_y + max(0, max_y - min_y) / 2)
                widget.follow_var.set(True)
                widget.fixed_var.set(False)
                widget.absolute_var.set(False)
                widget.physics_var.set(True)
                widget._follow_position = [float(max_x) - 1.0, collision_y]
                widget._follow_velocity = [900.0, 110.0]
                widget._follow_last_tick = 2000.0
                widget._follow_target = (float(max_x), collision_y)
                widget._follow_cycle_active = True
                widget._follow_cycle_started = 1998.0
                collision_frame_started = time.perf_counter()
                bounce_telemetry = widget._advance_follow(
                    float(max_x), collision_y, 2000.016,
                )
                collision_frame_ms = (time.perf_counter() - collision_frame_started) * 1000.0
                collision_visual_switch_ms = widget._last_stun_visual_switch_ms
                collision_visual_cache_hit = widget._last_whale_cache_hit
                bounce_velocity = tuple(widget._follow_velocity)
                stunned_started = (
                    widget._stunned
                    and bounce_telemetry["mode"] == "stunned-start"
                    and widget._rendered_whale_state == "stunned"
                )
                boundary_position = tuple(widget._follow_position)
                freeflight_telemetry = widget._advance_follow(
                    float(max_x), collision_y, 2000.032,
                )
                freeflight_positions = [boundary_position, tuple(widget._follow_position)]
                for frame in range(2, 13):
                    widget._advance_follow(
                        float(max_x), collision_y, 2000.016 + frame * 0.016,
                    )
                    freeflight_positions.append(tuple(widget._follow_position))
                freeflight_steps = [
                    math.hypot(
                        freeflight_positions[index][0] - freeflight_positions[index - 1][0],
                        freeflight_positions[index][1] - freeflight_positions[index - 1][1],
                    )
                    for index in range(1, len(freeflight_positions))
                ]
                freeflight_distance = math.hypot(
                    freeflight_positions[-1][0] - boundary_position[0],
                    freeflight_positions[-1][1] - boundary_position[1],
                )
                freeflight_smooth = (
                    all(
                        freeflight_positions[index][0]
                        < freeflight_positions[index - 1][0]
                        for index in range(1, len(freeflight_positions))
                    )
                    and max(freeflight_steps) - min(freeflight_steps) < 1.0
                )
                stunned_ignores_target = (
                    freeflight_telemetry["mode"] == "stunned"
                    and freeflight_telemetry["acceleration"] == 0.0
                    and freeflight_distance > 0
                    and freeflight_smooth
                )
                expiry_time = widget._stun_until + 0.016
                widget._advance_follow(float(max_x), collision_y, expiry_time)
                stun_expires_to_normal = (
                    not widget._stunned and widget._rendered_whale_state == "normal"
                )

                widget._set_stunned(False, 2100.0)
                widget._follow_position = [float(min_x) + 0.1, collision_y]
                widget._follow_velocity = [-100.0, 0.0]
                widget._follow_last_tick = 2100.0
                widget._follow_target = (float(min_x), collision_y)
                widget._follow_cycle_active = True
                widget._follow_cycle_started = 2098.0
                low_speed_telemetry = widget._advance_follow(
                    float(min_x), collision_y, 2100.016,
                )
                low_speed_stopped = (
                    not low_speed_telemetry["collision"]
                    and abs(widget._follow_velocity[0]) < 0.001
                )

                widget.physics_var.set(False)
                widget._toggle_physics()
                widget._follow_position = [float(max_x) - 1.0, collision_y]
                widget._follow_velocity = [900.0, 0.0]
                widget._follow_last_tick = 2200.0
                widget._follow_target = (float(max_x), collision_y)
                widget._follow_cycle_active = True
                widget._follow_cycle_started = 2198.0
                physics_off_telemetry = widget._advance_follow(
                    float(max_x), collision_y, 2200.016,
                )
                physics_off_stops_at_wall = (
                    not physics_off_telemetry["collision"]
                    and not widget._stunned
                    and abs(widget._follow_velocity[0]) < 0.001
                )
                widget.physics_var.set(True)
                widget._toggle_physics()
                widget._set_stun_duration(2200)
                stun_duration_setting_works = (
                    widget.stun_duration_var.get() == 2200
                    and widget.settings["stunDurationMs"] == 2200
                )
                widget._set_stun_duration(STUN_DURATION_DEFAULT)
                impact_scaled_rebound = (
                    _impact_rebound_multiplier(1500.0)
                    > _impact_rebound_multiplier(900.0)
                    > 1.0
                )

                widget._collision_count = 0
                widget._collision_sound_count = 0
                widget._collision_last_sound_at = None
                collision_sound_sequence = [
                    widget._on_edge_collision(3000.0, ["left"], 700.0),
                    widget._on_edge_collision(3000.1, ["left"], 700.0),
                    widget._on_edge_collision(3000.7, ["right"], 700.0),
                ]
                collision_cooldown_pass = (
                    collision_sound_sequence == [True, False, True]
                    and widget._collision_count == 3
                    and widget._collision_sound_count == 2
                )
                rapid_click_start = widget._click_count
                widget._activate_click(play_sound=False)
                widget._activate_click(play_sound=False)
                rapid_click_no_cooldown = widget._click_count - rapid_click_start == 2

                widget._render(
                    {
                        "task": {
                            "state": "idle",
                            "label": "Codex 暂时空闲",
                            "detail": "V0.7 本机交互验收",
                        },
                        "quota": {
                            "available": True,
                            "remainingPercent": 66.0,
                            "resetCreditCount": 3,
                        },
                    }
                )
                reset_credit_count_only = (
                    "重置卡 3 张" in widget.canvas.itemcget(widget.reset_credit_text, "text")
                    and not hasattr(widget, "reset_credit_button")
                )

                widget._set_stunned(False, 4000.0)
                widget._stop_throw(persist=False)
                widget.throw_var.set(False)
                widget._record_interaction(4000.0)
                idle_before_boundary = widget._maybe_activate_idle_variant(4299.999)
                idle_at_boundary = widget._maybe_activate_idle_variant(4300.0)
                idle_boundary_works = (
                    not idle_before_boundary
                    and idle_at_boundary
                    and widget._active_idle_variant in widget._active_idle_files()
                )
                widget._record_interaction(4300.01)
                idle_variant_records: dict[str, Any] = {}
                for index, name in enumerate(widget._active_idle_files()):
                    idle_started = time.perf_counter()
                    activated = widget._activate_idle_variant(name, 4300.0 + index)
                    idle_activation_ms = (time.perf_counter() - idle_started) * 1000.0
                    widget.root.update_idletasks()
                    idle_variant_records[name] = {
                        "activated": activated,
                        "activationMs": round(idle_activation_ms, 3),
                        "renderedState": widget._rendered_whale_state,
                        "alphaBBox": list(widget._last_whale_alpha_bbox or ()),
                        "renderSize": list(widget._last_whale_render_size or ()),
                        "translucentPixels": widget._last_whale_translucent_pixels,
                        "magentaPixels": widget._last_whale_magenta_pixels,
                    }
                    widget._record_interaction(4300.1 + index)
                idle_variants_render_safe = all(
                    record["activated"]
                    and record["renderedState"] == f"idle:{name}"
                    and bool(record["alphaBBox"])
                    and record["translucentPixels"] == 0
                    and record["magentaPixels"] == 0
                    for name, record in idle_variant_records.items()
                )
                idle_switch_nonblocking = (
                    max(record["activationMs"] for record in idle_variant_records.values())
                    < 16.0
                )
                idle_interaction_restores_normal = (
                    widget._active_idle_variant is None
                    and widget._rendered_whale_state == "normal"
                    and abs(
                        widget._next_idle_variant_at
                        - widget._last_interaction_at
                        - IDLE_VARIANT_SECONDS
                    ) < 0.001
                )

                widget._place_window(280, 220, include_size=True)
                widget.root.update_idletasks()
                widget.throw_var.set(True)
                widget._toggle_throw()
                throw_disables_other_modes = (
                    widget.throw_var.get()
                    and not widget.follow_var.get()
                    and not widget.fixed_var.get()
                    and not widget.absolute_var.get()
                )
                throw_start = whale_event()
                widget._drag_start(throw_start)
                time.sleep(0.02)
                widget._drag_move(
                    SimpleNamespace(
                        x_root=throw_start.x_root + 120,
                        y_root=throw_start.y_root + 36,
                    )
                )
                time.sleep(0.02)
                widget._drag_release(
                    SimpleNamespace(
                        x_root=throw_start.x_root + 120,
                        y_root=throw_start.y_root + 36,
                    )
                )
                drag_release_velocity = list(widget._throw_velocity)
                drag_release_activates_throw = (
                    widget._throw_active
                    and math.hypot(*drag_release_velocity) >= THROW_MIN_SPEED
                )
                widget._stop_throw(persist=False)
                widget._set_stunned(False, 5000.0)
                widget._place_window(320, 240, include_size=True)
                widget._throw_position = [320.0, 240.0]
                widget._throw_velocity = [720.0, 180.0]
                widget._throw_last_tick = 5000.0
                widget._throw_active = True
                throw_before = tuple(widget._throw_position)
                throw_freeflight = widget._advance_throw(5000.016)
                throw_inertia_continues = (
                    widget._throw_active
                    and math.hypot(
                        widget._throw_position[0] - throw_before[0],
                        widget._throw_position[1] - throw_before[1],
                    ) > 0
                    and throw_freeflight["speed"] > 0
                )

                widget._set_stunned(False, 6000.0)
                throw_min_x, throw_min_y, throw_max_x, throw_max_y = widget._position_bounds()
                throw_collision_y = float(throw_min_y + max(0, throw_max_y - throw_min_y) / 2)
                widget._place_window(float(throw_max_x) - 1.0, throw_collision_y)
                widget._throw_position = [float(throw_max_x) - 1.0, throw_collision_y]
                widget._throw_velocity = [1000.0, 140.0]
                widget._throw_last_tick = 6000.0
                widget._throw_active = True
                throw_collision = widget._advance_throw(6000.016)
                throw_bounces_at_edge = (
                    throw_collision["collision"]
                    and "right" in throw_collision["collisionSides"]
                    and widget._throw_velocity[0] < 0
                    and throw_collision["reboundMultiplier"] > 1.0
                )
                throw_now = 6000.016
                throw_frames = 0
                while widget._throw_active and throw_frames < 700:
                    throw_frames += 1
                    throw_now += 0.016
                    widget._advance_throw(throw_now)
                widget.root.update_idletasks()
                settled_position = [widget.root.winfo_x(), widget.root.winfo_y()]
                throw_settles_where_released = (
                    not widget._throw_active
                    and widget._throw_velocity == [0.0, 0.0]
                    and settled_position
                    == [round(widget._throw_position[0]), round(widget._throw_position[1])]
                )

                widget._set_stunned(False, 8000.0)
                widget.physics_var.set(False)
                widget._toggle_physics()
                widget._place_window(float(throw_max_x) - 1.0, throw_collision_y)
                widget._throw_position = [float(throw_max_x) - 1.0, throw_collision_y]
                widget._throw_velocity = [1000.0, 0.0]
                widget._throw_last_tick = 8000.0
                widget._throw_active = True
                throw_physics_off = widget._advance_throw(8000.016)
                throw_physics_off_clamps = (
                    not throw_physics_off["collision"]
                    and not widget._throw_active
                    and widget.root.winfo_x() == throw_max_x
                )
                widget.physics_var.set(True)
                widget._toggle_physics()
                widget.throw_var.set(False)
                widget.fixed_var.set(True)
                widget._toggle_fixed()
                original_skin = widget._active_skin_id
                skin_records: dict[str, Any] = {}
                for skin_id in SKIN_IDS:
                    widget._set_skin(skin_id)
                    widget.root.update_idletasks()
                    visual_keys = [
                        "normal",
                        "stunned",
                        *(f"idle:{name}" for name in widget._active_idle_files()),
                    ]
                    visual_records = {
                        visual_key: widget._whale_variant(
                            visual_key == "stunned", visual_key=visual_key,
                        )
                        for visual_key in visual_keys
                    }
                    skin_records[skin_id] = {
                        "label": SKIN_DEFINITIONS[skin_id]["label"],
                        "bubbleTitle": widget.canvas.itemcget(
                            widget.bubble_title_text, "text"
                        ),
                        "baseSize": list(widget._whale_base_size()),
                        "idleCount": len(widget._active_idle_files()),
                        "allRenderSafe": all(
                            bool(record["alphaBBox"])
                            and record["translucentPixels"] == 0
                            and record["magentaPixels"] == 0
                            and list(record["renderSize"]) == list(widget._whale_base_size())
                            for record in visual_records.values()
                        ),
                    }
                widget._set_skin(original_skin)
                skin_switch_contract = (
                    set(skin_records) == set(SKIN_IDS)
                    and all(record["idleCount"] == 7 for record in skin_records.values())
                    and all(record["allRenderSafe"] for record in skin_records.values())
                    and skin_records["deepseek-whale"]["bubbleTitle"] == "CODEX · 小鲸鱼"
                    and skin_records["endfield-yu"]["bubbleTitle"] == "CODEX · 祀"
                    and len({tuple(record["baseSize"]) for record in skin_records.values()}) == 1
                    and widget._active_skin_id == original_skin
                )

                original_sound_profile = widget._selected_sound_profile()
                original_sound_volume = widget._selected_sound_volume()
                sound_profile_records: dict[str, Any] = {}
                for profile_id in SOUND_PROFILE_IDS:
                    widget._set_sound_profile(profile_id, wait=True)
                    sound_profile_records[profile_id] = {
                        "label": SOUND_PROFILE_DEFINITIONS[profile_id]["label"],
                        "paths": [str(path) for path in widget._selected_sound_paths()],
                        "filesPresent": all(
                            path.is_file() for path in widget._selected_sound_paths()
                        ),
                        "collisionPreloaded": widget._collision_audio_ready,
                        "collisionPath": str(widget._collision_audio_path or ""),
                    }
                widget._set_sound_volume(25, wait=True)
                quarter_volume_applied = (
                    widget.sound_volume_var.get() == 25
                    and widget.settings["soundVolume"] == 25
                    and bool(widget._collision_audio_alias)
                    and widget._set_audio_alias_volume(
                        widget._collision_audio_alias, wait=True
                    )
                )
                widget._set_sound_volume(0)
                mute_without_fallback = (
                    widget.sound_volume_var.get() == 0
                    and widget._play_preloaded_collision_audio()
                )
                widget._set_sound_volume(original_sound_volume, wait=True)
                widget._set_sound_profile(original_sound_profile, wait=True)
                collision_submit_started = time.perf_counter()
                collision_audio_submitted = widget._play_preloaded_collision_audio()
                collision_submit_ms = (
                    time.perf_counter() - collision_submit_started
                ) * 1000.0
                click_submit_started = time.perf_counter()
                click_audio_submitted = widget._play_selected_click()
                click_submit_ms = (time.perf_counter() - click_submit_started) * 1000.0
                audio_submission_nonblocking = (
                    collision_audio_submitted
                    and click_audio_submitted
                    and collision_submit_ms < 8.0
                    and click_submit_ms < 8.0
                )
                sound_profiles_contract = (
                    set(sound_profile_records) == set(SOUND_PROFILE_IDS)
                    and all(
                        record["filesPresent"] and record["collisionPreloaded"]
                        for record in sound_profile_records.values()
                    )
                    and quarter_volume_applied
                    and mute_without_fallback
                    and widget._selected_sound_profile() == original_sound_profile
                    and widget._selected_sound_volume() == original_sound_volume
                    and audio_submission_nonblocking
                    and widget._audio_thread.is_alive()
                    and widget._audio_submit_dropped == 0
                )
                labels = widget.menu_labels()
                follow_labels = widget.follow_menu_labels()
                skin_labels = widget.skin_menu_labels()
                sound_labels = widget.sound_menu_labels()
                audio_assets = [
                    (_widget_root() / "assets" / path).is_file()
                    for definition in SOUND_PROFILE_DEFINITIONS.values()
                    for path in definition["files"]
                ]
                stunned_render_record = widget._whale_variant(
                    True, visual_key="stunned"
                )
                stunned_translucent_pixels = int(
                    stunned_render_record["translucentPixels"]
                )
                stunned_visible_magenta_pixels = int(
                    stunned_render_record["magentaPixels"]
                )
                result = {
                    "ok": all(
                        (
                            initial["bubbleHidden"],
                            initial["noIdleMotion"],
                            initial["bubbleShownOnClick"],
                            initial["bubbleHiddenAfterMs"],
                            initial["clickCount"] == 1,
                            initial["bubbleStages"] == [0.3, 0.64, 1.0],
                            initial["bubbleContentVisible"],
                            initial["bubbleLayoutReadable"],
                            initial["statusTextCentered"],
                            initial["detailTextCentered"],
                            initial["largeStatusPanelRemoved"],
                            initial["statusDotStateColors"],
                            initial["postClickCoords"] == initial["whaleCoords"],
                            bool(initial["deformationFrames"]),
                            initial["deformationFrames"][0][0] > 1.0,
                            initial["deformationFrames"][0][1] < 1.0,
                            initial["deformationFrames"][-1] == (1.0, 1.0),
                            labels == list(MENU_LABELS),
                            follow_labels == list(FOLLOW_SUBMENU_LABELS),
                            skin_labels == [
                                str(SKIN_DEFINITIONS[skin_id]["label"])
                                for skin_id in SKIN_IDS
                            ],
                            sound_labels == [
                                *(
                                    str(SOUND_PROFILE_DEFINITIONS[profile_id]["label"])
                                    for profile_id in SOUND_PROFILE_IDS
                                ),
                                "音量",
                                "试听当前音效",
                            ],
                            skin_switch_contract,
                            sound_profiles_contract,
                            follow_disables_fixed,
                            fixed_disables_follow,
                            absolute_disables_other_modes,
                            absolute_preset_applied,
                            absolute_drag_locked,
                            absolute_scale_resized,
                            visible_edge_alignment,
                            len(widget.settings["absolutePresets"]) == ABSOLUTE_PRESET_LIMIT,
                            follow_speeds[55] > follow_speeds[8] > 0,
                            follow_caps[-1] > follow_caps[8],
                            all(
                                acceleration <= cap + 0.001
                                for acceleration, cap in zip(follow_accelerations, follow_caps)
                            ),
                            max(step_lengths) < 30,
                            inertia_distance > 0,
                            follow_click_freezes,
                            bounce_telemetry["collision"],
                            "right" in bounce_telemetry["collisionSides"],
                            bounce_velocity[0] < 0,
                            bounce_telemetry["reboundMultiplier"] > 1.0,
                            stunned_started,
                            stunned_ignores_target,
                            stun_expires_to_normal,
                            low_speed_stopped,
                            physics_off_stops_at_wall,
                            stun_duration_setting_works,
                            impact_scaled_rebound,
                            collision_cooldown_pass,
                            widget._collision_visual_prewarmed,
                            collision_visual_cache_hit,
                            collision_visual_switch_ms < 16.0,
                            collision_frame_ms < 16.0,
                            widget._collision_audio_ready,
                            audio_submission_nonblocking,
                            rapid_click_no_cooldown,
                            reset_credit_count_only,
                            idle_variants_render_safe,
                            idle_switch_nonblocking,
                            idle_boundary_works,
                            idle_interaction_restores_normal,
                            throw_disables_other_modes,
                            drag_release_activates_throw,
                            throw_inertia_continues,
                            throw_bounces_at_edge,
                            throw_settles_where_released,
                            throw_physics_off_clamps,
                            widget._last_whale_translucent_pixels == 0,
                            widget._last_whale_magenta_pixels == 0,
                            stunned_translucent_pixels == 0,
                            stunned_visible_magenta_pixels == 0,
                            wheel_bindings_removed,
                            abs(proportion_scale - 1.25) < 0.001,
                            widget.scale_percent_var.get() in SCALE_PERCENT_OPTIONS,
                            minimum_scale == SCALE_MIN,
                            maximum_scale == SCALE_MAX,
                            all(audio_assets),
                        )
                    ),
                    "title": widget.root.title(),
                    "windowSize": [widget.root.winfo_width(), widget.root.winfo_height()],
                    "percentageScale": proportion_scale,
                    "percentageScaledWindowSize": proportion_size,
                    "percentageOptions": list(SCALE_PERCENT_OPTIONS),
                    "wheelBindingsRemoved": wheel_bindings_removed,
                    "minimumScale": minimum_scale,
                    "minimumWindowSize": minimum_size,
                    "maximumScale": maximum_scale,
                    "maximumWindowSize": maximum_size,
                    "topmost": bool(int(widget.root.attributes("-topmost"))),
                    "borderless": bool(widget.root.overrideredirect()),
                    "dragDelta": [new_x - old_x, new_y - old_y],
                    "menuLabels": labels,
                    "followMenuLabels": follow_labels,
                    "skinMenuLabels": skin_labels,
                    "soundMenuLabels": sound_labels,
                    "skins": {
                        "activeRestored": widget._active_skin_id,
                        "records": skin_records,
                        "switchContract": skin_switch_contract,
                    },
                    "sounds": {
                        "activeRestored": widget._selected_sound_profile(),
                        "volumeRestored": widget._selected_sound_volume(),
                        "profiles": sound_profile_records,
                        "quarterVolumeApplied": quarter_volume_applied,
                        "muteWithoutFallback": mute_without_fallback,
                        "workerThreadAlive": widget._audio_thread.is_alive(),
                        "collisionSubmissionMs": round(collision_submit_ms, 3),
                        "clickSubmissionMs": round(click_submit_ms, 3),
                        "submissionNonblocking": audio_submission_nonblocking,
                        "queueDrops": widget._audio_submit_dropped,
                        "workerResults": list(widget._audio_worker_results),
                        "contract": sound_profiles_contract,
                    },
                    "bubbleInitiallyHidden": initial["bubbleHidden"],
                    "bubbleShownOnClick": initial["bubbleShownOnClick"],
                    "bubbleHiddenAfterMs": initial["bubbleHiddenAfterMs"],
                    "bubbleDurationMs": BUBBLE_MS,
                    "bubbleStages": initial["bubbleStages"],
                    "bubbleContentVisibleAtFullSize": initial["bubbleContentVisible"],
                    "bubbleLayoutReadable": initial["bubbleLayoutReadable"],
                    "statusTextCentered": initial["statusTextCentered"],
                    "detailTextCentered": initial["detailTextCentered"],
                    "largeStatusPanelRemoved": initial["largeStatusPanelRemoved"],
                    "statusDotStateColors": initial["statusDotStateColors"],
                    "statusDotColors": dict(STATUS_DOT_COLORS),
                    "noIdleMotion": initial["noIdleMotion"],
                    "clickCount": initial["clickCount"],
                    "clickDeformationFrames": initial["deformationFrames"],
                    "clickTranslationRemoved": initial["postClickCoords"] == initial["whaleCoords"],
                    "followDisablesFixed": follow_disables_fixed,
                    "fixedDisablesFollow": fixed_disables_follow,
                    "absoluteDisablesOtherModes": absolute_disables_other_modes,
                    "absolutePresetLimit": ABSOLUTE_PRESET_LIMIT,
                    "absolutePresetSaved": saved_preset,
                    "absolutePresetApplied": absolute_preset_applied,
                    "absoluteDragLocked": absolute_drag_locked,
                    "absoluteScaleResized": absolute_scale_resized,
                    "visibleEdgeAlignment": visible_edge_alignment,
                    "visibleEdgeCoordinates": visible_edge_coordinates,
                    "followIntervalMs": FOLLOW_INTERVAL_MS,
                    "followEarlySpeed": round(follow_speeds[8], 3),
                    "followLaterSpeed": round(follow_speeds[55], 3),
                    "followEarlyAccelerationCap": round(follow_caps[8], 3),
                    "followLateAccelerationCap": round(follow_caps[-1], 3),
                    "followConfiguredAccelerationCap": widget.acceleration_var.get(),
                    "followMaxStep": round(max(step_lengths), 3),
                    "followInertiaDistance": round(inertia_distance, 3),
                    "followClickFreezes": follow_click_freezes,
                    "edgeBounce": {
                        "telemetry": bounce_telemetry,
                        "velocityAfter": [round(value, 3) for value in bounce_velocity],
                        "freeflightTelemetry": freeflight_telemetry,
                        "freeflightDistance": round(freeflight_distance, 3),
                        "freeflightFrameSteps": [round(value, 3) for value in freeflight_steps],
                        "freeflightSmooth": freeflight_smooth,
                        "stunnedStarted": stunned_started,
                        "stunnedIgnoresMouseTarget": stunned_ignores_target,
                        "stunExpiresToNormal": stun_expires_to_normal,
                        "lowSpeedStopped": low_speed_stopped,
                        "impactScaledRebound": impact_scaled_rebound,
                        "reboundRange": [PHYSICS_REBOUND_MIN, PHYSICS_REBOUND_MAX],
                        "stunRestitution": PHYSICS_STUN_RESTITUTION,
                        "collisionFrameMs": round(collision_frame_ms, 3),
                        "visualSwitchMs": round(collision_visual_switch_ms, 3),
                        "visualCacheHit": collision_visual_cache_hit,
                        "visualPrewarmed": widget._collision_visual_prewarmed,
                        "visualPrewarmMs": round(widget._collision_visual_prewarm_ms, 3),
                    },
                    "physicsCanBeDisabled": physics_off_stops_at_wall,
                    "stunDurationSettingWorks": stun_duration_setting_works,
                    "stunDurationOptionsMs": list(STUN_DURATION_OPTIONS),
                    "collisionSoundCooldownMs": COLLISION_SOUND_COOLDOWN_MS,
                    "collisionSoundSequence": collision_sound_sequence,
                    "collisionSoundCount": widget._collision_sound_count,
                    "collisionAudioPreloaded": widget._collision_audio_ready,
                    "collisionAudioPrepareMs": round(widget._collision_audio_prepare_ms, 3),
                    "rapidClickNoCooldown": rapid_click_no_cooldown,
                    "resetCredits": {
                        "text": widget.canvas.itemcget(widget.reset_credit_text, "text"),
                        "countOnly": reset_credit_count_only,
                        "activeResetControlPresent": hasattr(widget, "reset_credit_button"),
                    },
                    "idleVariants": {
                        "timeoutSeconds": IDLE_VARIANT_SECONDS,
                        "count": len(widget._active_idle_files()),
                        "records": idle_variant_records,
                        "allRenderSafe": idle_variants_render_safe,
                        "switchNonblocking": idle_switch_nonblocking,
                        "activatesAtFiveMinuteBoundary": idle_boundary_works,
                        "interactionRestoresNormal": idle_interaction_restores_normal,
                    },
                    "throwMode": {
                        "disablesOtherModes": throw_disables_other_modes,
                        "dragReleaseVelocity": [round(value, 3) for value in drag_release_velocity],
                        "dragReleaseActivatesThrow": drag_release_activates_throw,
                        "inertiaContinues": throw_inertia_continues,
                        "freeflight": throw_freeflight,
                        "edgeBounce": throw_collision,
                        "bouncesAtEdge": throw_bounces_at_edge,
                        "framesUntilSettled": throw_frames,
                        "settledPosition": settled_position,
                        "settlesWhereReleased": throw_settles_where_released,
                        "physicsOffClamps": throw_physics_off_clamps,
                        "sampleWindowSeconds": THROW_SAMPLE_WINDOW_SECONDS,
                        "minimumThrowSpeed": THROW_MIN_SPEED,
                        "stopSpeed": THROW_STOP_SPEED,
                    },
                    "displayAlphaThreshold": DISPLAY_ALPHA_THRESHOLD,
                    "visibleTranslucentPixels": widget._last_whale_translucent_pixels,
                    "visibleMagentaPixels": widget._last_whale_magenta_pixels,
                    "stunnedVisibleMagentaPixels": stunned_visible_magenta_pixels,
                    "stunnedTranslucentPixels": stunned_translucent_pixels,
                    "pillowDisplayPath": widget._pil_whale_source is not None,
                    "allAudioAssets": audio_assets,
                    "autostartRegistryTouched": False,
                    "whaleBounds": list(widget.canvas.bbox("whale") or ()),
                }
                print(json.dumps(result, ensure_ascii=False), flush=True)
                widget.close()

            widget.root.after(150, begin_report)
        widget.run()
        return 0
    except Exception as exc:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, _compact_error(exc), APP_NAME, 0x10)
        except Exception:
            print(_compact_error(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
