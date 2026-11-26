#!/usr/bin/env python3
"""Fenrir Doctor: local-only dashboard and Ollama bridge using the Python standard library."""
from __future__ import annotations

import json
import os
import re
import select
import shutil
import sqlite3
import subprocess
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typing import Any
from urllib.parse import urlparse

APP = Path(__file__).resolve().parent
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
STATE = STATE_HOME / "fenrir-doctor"
DB = STATE / "history.sqlite3"
SETTINGS_FILE = CONFIG_HOME / "fenrir-doctor" / "settings.json"
LEGACY_STATE = STATE_HOME / "sun-ai"
LEGACY_DB = LEGACY_STATE / "history.sqlite3"
LEGACY_SETTINGS = CONFIG_HOME / "sun-ai" / "settings.json"
CATALOG_SOURCE = Path(os.environ.get("FENRIR_CATALOG_SOURCE", Path.home() / ".local/share/fenrir/catalog-source"))
CATALOG_HOME = Path(os.environ.get("FENRIR_CATALOG_HOME", Path.home() / ".local/share/fenrir/catalog"))
CATALOG_DB = Path(os.environ.get("FENRIR_CATALOG_DB", CATALOG_HOME / "catalog.sqlite3"))
QUARANTINE_ROOT = Path(os.environ.get("FENRIR_QUARANTINE_ROOT", CATALOG_HOME / "quarantine"))
WALLPAPER_DIRECTORY = Path(os.environ.get("FENRIR_WALLPAPER_DIRECTORY", Path.home() / "Pictures/Wallpapers"))
APP_VERSION = "0.12.2"
LOCAL_RELEASES = {
    "Fenrir-Arch": "0.8.1",
    "Fenrir-Dots": "0.12.2",
    "Fenrir-Wallpaper-Catalog": "0.28.0",
}
RELEASE_CACHE: dict[str, Any] | None = None
RELEASE_CACHE_AT = 0.0
RELEASE_CACHE_TTL = 900.0
INSTALLED_VERSIONS_FILE = Path.home() / ".local/share/fenrir/installed-versions.json"


def installed_release_versions() -> dict[str, str]:
    """Read exact local component versions written by the Arch installer.

    Missing manifests preserve compatibility with existing installations.
    Malformed, oversized, symlinked or unknown entries are ignored; this file
    is local status metadata and never supplies executable paths or URLs.
    """
    versions = dict(LOCAL_RELEASES)
    path = INSTALLED_VERSIONS_FILE
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            return versions
        raw = strict_json(path.read_bytes())
        if not isinstance(raw, dict):
            return versions
        for name, version in raw.items():
            if (
                name in versions
                and isinstance(version, str)
                and re.fullmatch(r"\d+\.\d+\.\d+", version)
            ):
                versions[name] = version
    except (OSError, ValueError, TypeError, BadJSON):
        return versions
    return versions
WALLPAPER_SYNC: subprocess.Popen | None = None
WALLPAPER_SYNC_LOG = STATE / "wallpaper-sync.log"
DISCOVERY_PROCESS: subprocess.Popen | None = None
DISCOVERY_LOG = STATE / "wallpaper-discovery.log"
DISCOVERY_STATE = STATE / "wallpaper-discovery.json"
DISCOVERY_SCHEDULE_FILE = STATE / "wallpaper-discovery-schedule.json"
DISCOVERY_LOCK = threading.RLock()
RIGHTS_STUDIO_LOCK = threading.RLock()
RIGHTS_STUDIO_PROCESS: subprocess.Popen | None = None
RIGHTS_STUDIO_URL: str | None = None
DISCOVERY_SCHEDULER_STOP = threading.Event()
DISCOVERY_SCHEDULER_THREAD: threading.Thread | None = None
DISCOVERY_SCHEDULE_INTERVALS = {60, 180, 360, 720, 1440}
DISCOVERY_PROFILES = frozenset({
    "fenrir-nordic-fantasy-v1",
    "fenrir-cinematic-nature-v1",
    "fenrir-cosmic-sci-fi-v1",
    "fenrir-arctic-blue-v1",
    "fenrir-architecture-monochrome-v1",
    "fenrir-red-violet-dark-fantasy-v1",
})
FENRIR_USER_STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "fenrir"
DISCOVERY_SLICE_MAX_QUERIES = 2
DISCOVERY_SLICE_MAX_PAGES = 2
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MAX_BODY = 256 * 1024
MAX_OLLAMA_RESPONSE = 8 * 1024 * 1024

parsed_ollama = urlparse(OLLAMA)
if parsed_ollama.scheme != "http" or parsed_ollama.hostname not in {"127.0.0.1", "localhost"} or parsed_ollama.port not in {None, 11434}:
    raise SystemExit("OLLAMA_HOST must point to the local Ollama API on 127.0.0.1:11434")

class BadJSON(ValueError):
    pass


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise BadJSON(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def strict_json(data: bytes) -> Any:
    return json.loads(
        data.decode("utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(BadJSON(f"invalid constant: {value}")),
    )


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def default_settings() -> dict[str, Any]:
    return {
        "default_model": "",
        "weather": {"location": "", "latitude": None, "longitude": None},
        "wallpaper_target_count": 5000,
    }


def read_settings() -> dict[str, Any]:
    try:
        raw = strict_json(SETTINGS_FILE.read_bytes())
        if not isinstance(raw, dict):
            raise ValueError("settings must be an object")
        settings = default_settings()
        model = raw.get("default_model", "")
        if isinstance(model, str) and len(model) <= 160:
            settings["default_model"] = model
        target_count = raw.get("wallpaper_target_count", 5000)
        if target_count in {5000, 10000, 20000}:
            settings["wallpaper_target_count"] = target_count
        weather = raw.get("weather", {})
        if isinstance(weather, dict):
            location = weather.get("location", "")
            lat = weather.get("latitude")
            lon = weather.get("longitude")
            if isinstance(location, str) and len(location) <= 100:
                settings["weather"]["location"] = location
            if isinstance(lat, (int, float)) and not isinstance(lat, bool) and -90 <= lat <= 90:
                settings["weather"]["latitude"] = float(lat)
            if isinstance(lon, (int, float)) and not isinstance(lon, bool) and -180 <= lon <= 180:
                settings["weather"]["longitude"] = float(lon)
        return settings
    except (OSError, ValueError, TypeError, BadJSON):
        return default_settings()


@contextmanager
def db():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(STATE, 0o700)
    except OSError:
        pass
    conn = sqlite3.connect(DB, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          role TEXT NOT NULL CHECK(role IN ('user','assistant')),
          content TEXT NOT NULL,
          model TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages(conversation_id,id);
        """
    )
    try:
        os.chmod(DB, 0o600)
    except OSError:
        pass
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ollama_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(f"{OLLAMA}{path}", data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_OLLAMA_RESPONSE + 1)
    if len(body) > MAX_OLLAMA_RESPONSE:
        raise RuntimeError("Ollama response exceeded the 8 MiB safety limit")
    return strict_json(body)


def system_snapshot() -> dict[str, Any]:
    cpu_percent: float | None = None
    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()[1:]
        numbers = [int(value) for value in fields]
        total = sum(numbers)
        idle = numbers[3] + (numbers[4] if len(numbers) > 4 else 0)
        previous = getattr(system_snapshot, "_cpu", None)
        system_snapshot._cpu = (total, idle)  # type: ignore[attr-defined]
        if previous:
            delta_total = total - previous[0]
            delta_idle = idle - previous[1]
            if delta_total > 0:
                cpu_percent = round(max(0.0, min(100.0, 100 * (delta_total - delta_idle) / delta_total)), 1)
    except (OSError, ValueError, IndexError):
        pass

    memory: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value = line.split(":", 1)
            memory[key] = int(value.strip().split()[0])
        total_kib = memory.get("MemTotal", 0)
        available_kib = memory.get("MemAvailable", 0)
        memory_percent = round(100 * (total_kib - available_kib) / total_kib, 1) if total_kib else None
        memory_used_gib = round((total_kib - available_kib) / 1024 / 1024, 1)
        memory_total_gib = round(total_kib / 1024 / 1024, 1)
    except (OSError, ValueError, ZeroDivisionError):
        memory_percent = None
        memory_used_gib = memory_total_gib = None

    uptime_seconds: int | None = None
    try:
        uptime_seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    gpu_percent: float | None = None
    gpu_name = "AMD GPU"
    try:
        candidates: list[tuple[int, int, Path]] = []
        for device in Path("/sys/class/drm").glob("card*/device"):
            try:
                vendor = (device / "vendor").read_text(encoding="ascii").strip().lower()
                busy = device / "gpu_busy_percent"
                if vendor != "0x1002" or not busy.exists():
                    continue
                # Prefer a discrete adapter with dedicated VRAM. This matters on
                # systems such as the target workstation that expose both a
                # Ryzen iGPU and a Radeon RX 6750 XT.
                try:
                    vram = int((device / "mem_info_vram_total").read_text(encoding="ascii").strip())
                except (OSError, ValueError):
                    vram = 0
                candidates.append((1 if vram >= 1024**3 else 0, vram, device))
            except (OSError, ValueError):
                continue
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            selected = candidates[0][2]
            gpu_percent = float((selected / "gpu_busy_percent").read_text(encoding="ascii").strip())
            try:
                gpu_name = (selected / "product_name").read_text(encoding="utf-8").strip()
            except OSError:
                pci_id = (selected / "device").read_text(encoding="ascii").strip().lower()
                gpu_name = "Radeon RX 6750 XT" if pci_id == "0x73df" else f"AMD GPU ({pci_id})"
    except (OSError, ValueError):
        pass

    home_usage = shutil.disk_usage(Path.home())
    disk_percent = round(100 * home_usage.used / home_usage.total, 1) if home_usage.total else None
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "memory_used_gib": memory_used_gib,
        "memory_total_gib": memory_total_gib,
        "gpu_percent": gpu_percent,
        "gpu_name": gpu_name,
        "disk_percent": disk_percent,
        "disk_used_gib": round(home_usage.used / 1024**3, 1),
        "disk_total_gib": round(home_usage.total / 1024**3, 1),
        "uptime_seconds": uptime_seconds,
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
    }


WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Dense drizzle", 56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Heavy freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def weather_snapshot() -> dict[str, Any]:
    location = read_settings()["weather"]
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is None or lon is None:
        return {"configured": False, "location": location.get("location", ""), "message": "Set a location in Sun AI settings to enable weather."}
    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "forecast_days": 5,
        "timezone": "auto",
    })
    request = urllib.request.Request(
        f"https://api.open-meteo.com/v1/forecast?{query}",
        headers={"User-Agent": "FenrirDoctor/0.2 (local desktop weather panel)"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        data = strict_json(response.read(512 * 1024))
    current = data.get("current", {})
    daily = data.get("daily", {})
    days = []
    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    for index, date in enumerate(dates[:5]):
        code = codes[index] if index < len(codes) else -1
        days.append({
            "date": date,
            "description": WEATHER_CODES.get(code, "Weather unavailable"),
            "high": highs[index] if index < len(highs) else None,
            "low": lows[index] if index < len(lows) else None,
        })
    return {
        "configured": True,
        "location": location.get("location", "Configured location"),
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "description": WEATHER_CODES.get(current.get("weather_code"), "Weather unavailable"),
        "is_day": bool(current.get("is_day", 1)),
        "days": days,
        "provider": "Open-Meteo",
    }



def migrate_legacy_data() -> None:
    """Copy legacy Sun AI user data without deleting the original files."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if LEGACY_DB.is_file() and not DB.exists():
        try:
            source = sqlite3.connect(f"file:{LEGACY_DB}?mode=ro", uri=True, timeout=5)
            target = sqlite3.connect(DB, timeout=5)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
                source.close()
            os.chmod(DB, 0o600)
        except sqlite3.Error as exc:
            print(f"Fenrir Doctor: legacy chat history migration skipped: {exc}", flush=True)
            DB.unlink(missing_ok=True)
    if LEGACY_SETTINGS.is_file() and not SETTINGS_FILE.exists():
        try:
            shutil.copy2(LEGACY_SETTINGS, SETTINGS_FILE)
            os.chmod(SETTINGS_FILE, 0o600)
        except OSError as exc:
            print(f"Fenrir Doctor: legacy settings migration skipped: {exc}", flush=True)


def _command_result(args: list[str], timeout: float = 5.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        detail = (result.stdout or result.stderr or "").strip().splitlines()
        return result.returncode == 0, detail[0][:220] if detail else ("Command completed." if result.returncode == 0 else "Command reported an error.")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)[:220]


def _check(name: str, status: str, detail: str, group: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail, "group": group}


def catalog_integrity_snapshot() -> dict[str, Any]:
    """Run a read-only SQLite quick_check against the configured local catalog."""
    path = CATALOG_DB
    if path.is_symlink() or not path.is_file():
        return {
            "available": False,
            "integrity": None,
            "schema_version": None,
            "detail": "Catalog database is missing or is a symbolic link.",
        }
    try:
        quoted = urllib.parse.quote(str(path.resolve()), safe="/")
        connection = sqlite3.connect(f"file:{quoted}?mode=ro", uri=True, timeout=3)
        try:
            connection.execute("PRAGMA query_only=ON")
            integrity_row = connection.execute("PRAGMA quick_check(1)").fetchone()
            version_row = connection.execute("PRAGMA user_version").fetchone()
        finally:
            connection.close()
        integrity = str(integrity_row[0]) if integrity_row else "unknown"
        schema_version = int(version_row[0]) if version_row else 0
        return {
            "available": True,
            "integrity": integrity,
            "schema_version": schema_version,
            "detail": "SQLite quick_check passed." if integrity == "ok" else f"SQLite quick_check reported: {integrity[:180]}",
        }
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        return {
            "available": True,
            "integrity": "error",
            "schema_version": None,
            "detail": f"Catalog database check failed: {str(exc)[:180]}",
        }


def wallpaper_runtime_snapshot() -> dict[str, Any]:
    """Inspect wallpaper qualification, monitor state and the no-repeat history."""
    result: dict[str, Any] = {
        "available": False,
        "directory": str(current_wallpaper_directory()),
        "valid_count": None,
        "file_count": None,
        "rejected_count": None,
        "minimum_count": 5000,
        "monitor_mode": "shared",
        "history_depth": 20,
        "monitor_count": None,
        "history_records": 0,
        "detail": "Wallpaper companion is unavailable.",
    }
    directory = current_wallpaper_directory()
    if directory.is_symlink() or not directory.is_dir():
        result["detail"] = "Configured wallpaper directory is missing or is a symbolic link."
        return result
    executable = shutil.which("fenrir-wallpaper")
    if not executable:
        return result
    try:
        completed = subprocess.run(
            [executable, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=18,
            check=False,
        )
        if completed.returncode != 0:
            result["detail"] = (completed.stderr or completed.stdout or "Wallpaper status command failed.")[:220]
            return result
        payload = strict_json(completed.stdout.encode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Wallpaper status must be a JSON object.")
        result.update({
            "available": True,
            "valid_count": int(payload.get("valid_count", 0)),
            "file_count": int(payload.get("file_count", 0)),
            "rejected_count": int(payload.get("rejected_count", 0)),
            "minimum_count": int(payload.get("minimum_count", 5000)),
            "monitor_mode": payload.get("monitor_mode", "shared"),
            "history_depth": int(payload.get("history_depth", 20)),
            "detail": "Wallpaper qualification report loaded from the local companion.",
        })
        state_file = FENRIR_USER_STATE / "wallpaper-history.json"
        if state_file.is_file() and not state_file.is_symlink() and state_file.stat().st_size <= 65536:
            history = strict_json(state_file.read_bytes())
            monitors = history.get("monitors", {}) if isinstance(history, dict) else {}
            if isinstance(monitors, dict):
                result["history_records"] = sum(
                    len(items) for items in monitors.values() if isinstance(items, list)
                )
        try:
            outputs = subprocess.run(
                ["hyprctl", "-j", "monitors"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if outputs.returncode == 0:
                decoded = strict_json(outputs.stdout.encode("utf-8"))
                if isinstance(decoded, list):
                    result["monitor_count"] = sum(
                        1 for item in decoded
                        if isinstance(item, dict) and isinstance(item.get("name"), str)
                    )
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, BadJSON):
            pass
        return result
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, BadJSON) as exc:
        result["detail"] = f"Wallpaper status unavailable: {str(exc)[:180]}"
        return result


def diagnostics_snapshot() -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    checks.append(_check(
        "Arch Linux",
        "ok" if Path("/etc/arch-release").exists() else "attention",
        "Arch release marker found." if Path("/etc/arch-release").exists() else "This installer targets Arch Linux.",
        "system",
    ))
    hypr_ok, hypr_detail = _command_result(["hyprctl", "-j", "version"])
    checks.append(_check("Hyprland", "ok" if hypr_ok else "warning", hypr_detail if hypr_ok else "Run diagnostics inside the Fenrir Hyprland session.", "desktop"))
    vulkan_ok, vulkan_detail = _command_result(["vulkaninfo", "--summary"], timeout=8) if shutil.which("vulkaninfo") else (False, "vulkaninfo is not installed.")
    checks.append(_check("Vulkan", "ok" if vulkan_ok else "warning", vulkan_detail, "graphics"))
    audio_ok, audio_detail = _command_result(["wpctl", "status"])
    checks.append(_check("PipeWire audio", "ok" if audio_ok else "warning", audio_detail, "audio"))
    network_ok, network_detail = _command_result(["systemctl", "is-active", "NetworkManager.service"])
    checks.append(_check("NetworkManager", "ok" if network_ok else "attention", network_detail, "system"))
    wallpaper_ok, wallpaper_detail = _command_result(["systemctl", "--user", "is-active", "fenrir-wallpaper.service"])
    checks.append(_check("Wallpaper service", "ok" if wallpaper_ok else "warning", wallpaper_detail, "wallpaper"))
    catalog_ready = (
        shutil.which("fenrir-catalog") is not None
        and CATALOG_DB.is_file() and not CATALOG_DB.is_symlink()
        and QUARANTINE_ROOT.is_dir() and not QUARANTINE_ROOT.is_symlink()
    )
    checks.append(_check(
        "Wallpaper Catalog",
        "ok" if catalog_ready else "warning",
        "Local catalog and quarantine are ready." if catalog_ready else "Install or initialize the local Fenrir Wallpaper Catalog to enable wallpaper intelligence.",
        "wallpaper",
    ))
    catalog_integrity = catalog_integrity_snapshot()
    integrity_status = (
        "attention" if catalog_integrity["integrity"] == "error"
        else ("ok" if catalog_integrity["integrity"] == "ok" else "warning")
    )
    checks.append(_check(
        "Catalog database integrity",
        integrity_status,
        catalog_integrity["detail"],
        "catalog",
    ))
    wallpaper_runtime = wallpaper_runtime_snapshot()
    if wallpaper_runtime["available"]:
        valid_count = wallpaper_runtime["valid_count"]
        target = wallpaper_runtime["minimum_count"]
        quality_status = "ok" if valid_count > 0 else ("attention" if wallpaper_runtime["file_count"] else "warning")
        quality_detail = (
            f"{valid_count:,} qualifying of {wallpaper_runtime['file_count']:,} files; "
            f"{wallpaper_runtime['rejected_count']:,} rejected; target {target:,}."
        )
    else:
        quality_status = "warning"
        quality_detail = wallpaper_runtime["detail"]
    checks.append(_check("Wallpaper library quality", quality_status, quality_detail, "wallpaper"))
    monitor_count = wallpaper_runtime.get("monitor_count")
    monitor_detail = (
        f"{monitor_count} connected output(s); {wallpaper_runtime['monitor_mode']} wallpaper mode; "
        f"{wallpaper_runtime['history_records']} recent rotation records."
        if monitor_count is not None else
        f"{wallpaper_runtime['monitor_mode']} wallpaper mode; monitor geometry unavailable outside Hyprland."
    )
    checks.append(_check(
        "Monitor-aware rotation",
        "ok" if wallpaper_runtime["available"] else "warning",
        monitor_detail,
        "display",
    ))
    usage = shutil.disk_usage(Path.home())
    used_percent = round(100 * usage.used / usage.total, 1) if usage.total else 0
    disk_status = "attention" if used_percent >= 95 else ("warning" if used_percent >= 85 else "ok")
    checks.append(_check("Home disk space", disk_status, f"{used_percent:.1f}% used ({round(usage.free / 1024**3, 1)} GiB free).", "storage"))
    ok_count = sum(1 for item in checks if item["status"] == "ok")
    attention_count = sum(1 for item in checks if item["status"] == "attention")
    return {
        "app_version": APP_VERSION,
        "checks": checks,
        "summary": {"total": len(checks), "ok": ok_count, "warning": sum(1 for item in checks if item["status"] == "warning"), "attention": attention_count},
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _version_key(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:4]) if parts else (0,)


def _latest_private_catalog_release() -> dict[str, Any]:
    current = installed_release_versions()["Fenrir-Wallpaper-Catalog"]
    if not (CATALOG_SOURCE / ".git").is_dir():
        return {
            "repository": "Fenrir-Wallpaper-Catalog",
            "current": current,
            "latest": None,
            "update_available": False,
            "status": "unavailable",
            "detail": "Local authenticated Catalog checkout is missing.",
        }
    try:
        result = subprocess.run(
            ["git", "-C", str(CATALOG_SOURCE), "ls-remote", "--tags", "--refs", "origin", "refs/tags/v*"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            return {
                "repository": "Fenrir-Wallpaper-Catalog",
                "current": current,
                "latest": None,
                "update_available": False,
                "status": "unavailable",
                "detail": (result.stderr or "GitHub authentication is unavailable.")[:180],
            }
        tags = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            tag = parts[1].rsplit("/", 1)[-1]
            if re.fullmatch(r"v\d+\.\d+\.\d+", tag):
                tags.append(tag)
        if not tags:
            return {
                "repository": "Fenrir-Wallpaper-Catalog",
                "current": current,
                "latest": None,
                "update_available": False,
                "status": "no_release",
            }
        tag = max(tags, key=_version_key)
        latest = tag[1:]
        return {
            "repository": "Fenrir-Wallpaper-Catalog",
            "current": current,
            "latest": latest,
            "update_available": _version_key(latest) > _version_key(current),
            "tag": tag,
            "url": f"https://github.com/sunxsaturn/Fenrir-Wallpaper-Catalog/releases/tag/{tag}",
            "published_at": None,
            "status": "available",
        }
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        return {
            "repository": "Fenrir-Wallpaper-Catalog",
            "current": current,
            "latest": None,
            "update_available": False,
            "status": "unavailable",
            "detail": str(exc)[:180],
        }


def _latest_release(repository: str) -> dict[str, Any]:
    if repository == "Fenrir-Wallpaper-Catalog":
        return _latest_private_catalog_release()
    request = urllib.request.Request(
        f"https://api.github.com/repos/sunxsaturn/{repository}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Fenrir-Doctor/0.5"},
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = strict_json(response.read(256 * 1024))
        tag = payload.get("tag_name", "")
        latest = tag[1:] if isinstance(tag, str) and tag.startswith("v") else str(tag)
        current = installed_release_versions()[repository]
        return {
            "repository": repository,
            "current": current,
            "latest": latest,
            "update_available": bool(latest and _version_key(latest) > _version_key(current)),
            "tag": tag,
            "url": payload.get("html_url"),
            "published_at": payload.get("published_at"),
            "status": "available",
        }
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"repository": repository, "current": LOCAL_RELEASES[repository], "latest": None, "update_available": False, "status": "no_release"}
        return {"repository": repository, "current": LOCAL_RELEASES[repository], "latest": None, "update_available": False, "status": "unavailable"}
    except (OSError, ValueError, TypeError) as exc:
        return {"repository": repository, "current": LOCAL_RELEASES[repository], "latest": None, "update_available": False, "status": "unavailable", "detail": str(exc)[:180]}


def updates_snapshot() -> dict[str, Any]:
    global RELEASE_CACHE, RELEASE_CACHE_AT
    now = time.monotonic()
    if RELEASE_CACHE is not None and now - RELEASE_CACHE_AT < RELEASE_CACHE_TTL:
        return RELEASE_CACHE
    updates = [_latest_release(name) for name in LOCAL_RELEASES]
    RELEASE_CACHE = {
        "components": updates,
        "update_available": any(item["update_available"] for item in updates),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    RELEASE_CACHE_AT = now
    return RELEASE_CACHE


def backups_snapshot() -> dict[str, Any]:
    root = Path.home() / ".local/state/fenrir/backups"
    if not root.is_dir() or root.is_symlink():
        return {"backups": [], "root": str(root)}
    backups = []
    for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True):
        if not path.is_dir() or path.is_symlink() or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", path.name):
            continue
        files = sum(1 for item in path.rglob("*") if item.is_file() and not item.is_symlink())
        backups.append({"id": path.name, "files": files, "modified": int(path.stat().st_mtime)})
    return {"backups": backups[:30], "root": str(root)}


RESTORE_ALLOWLIST = (
    ".config/hypr",
    ".config/waybar",
    ".config/fuzzel",
    ".config/kitty",
    ".config/mako",
    ".config/gtk-3.0",
    ".config/gtk-4.0",
    ".config/fenrir",
    ".config/systemd/user",
    ".local/share/icons/Fenrir-Obsidian",
    ".local/share/fenrir/apps",
    ".local/share/fenrir-doctor",
    ".local/bin",
)


def _assert_no_symlink_path(path: Path, boundary: Path) -> None:
    current = path
    while current != boundary and boundary in current.parents:
        if current.is_symlink():
            raise ValueError(f"Refusing to follow symbolic link: {current}")
        current = current.parent


def _assert_tree_no_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise ValueError(f"Refusing symbolic link in recovery tree: {root}")
    if not root.exists():
        return
    if not root.is_dir():
        return
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        for name in dirnames + filenames:
            candidate = base / name
            if candidate.is_symlink():
                raise ValueError(f"Refusing symbolic link in recovery tree: {candidate}")


def restore_backup(backup_id: str) -> dict[str, Any]:
    if not isinstance(backup_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", backup_id):
        raise ValueError("Invalid backup identifier.")
    home = Path.home()
    backup_parent = home / ".local/state/fenrir/backups"
    _assert_no_symlink_path(backup_parent, home)
    root = backup_parent.resolve()
    source_root = root / backup_id
    if root not in source_root.parents or source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Backup does not exist or is not a safe directory.")
    _assert_tree_no_symlinks(source_root)

    prepared: list[tuple[str, Path, Path]] = []
    for relative in RESTORE_ALLOWLIST:
        source = source_root / relative
        if not source.exists() and not source.is_symlink():
            continue
        _assert_tree_no_symlinks(source)
        target = home / relative
        _assert_no_symlink_path(target, home)
        if target.exists() or target.is_symlink():
            _assert_tree_no_symlinks(target)
        prepared.append((relative, source, target))

    if not prepared:
        raise ValueError("The selected backup contains no supported Fenrir configuration paths.")

    rollback_root = root / f"doctor-restore-{time.time_ns()}"
    restored: list[str] = []
    for relative, source, target in prepared:
        if target.exists():
            snapshot = rollback_root / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.copytree(target, snapshot, symlinks=False, dirs_exist_ok=True)
            else:
                shutil.copy2(target, snapshot)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, symlinks=False, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        restored.append(relative)

    return {"restored": restored, "rollback_backup": rollback_root.name if rollback_root.exists() else None}


def current_wallpaper_directory() -> Path:
    configured = os.environ.get("FENRIR_WALLPAPER_DIRECTORY")
    if not configured:
        settings_path = Path.home() / ".config/fenrir/settings.toml"
        try:
            with settings_path.open("rb") as stream:
                settings = tomllib.load(stream)
            configured = settings.get("wallpaper", {}).get("directory")
        except (OSError, tomllib.TOMLDecodeError, AttributeError):
            configured = None
    path = Path(configured).expanduser() if isinstance(configured, str) and configured.strip() else Path.home() / "Pictures/Wallpapers"
    return path.resolve()


def wallpaper_sync_destination_allowed(path: Path) -> bool:
    pictures = (Path.home() / "Pictures").resolve()
    resolved = path.resolve()
    return resolved == pictures or pictures in resolved.parents


def wallpaper_campaign_snapshot() -> dict[str, Any]:
    global DISCOVERY_PROCESS
    process_running = DISCOVERY_PROCESS is not None and DISCOVERY_PROCESS.poll() is None
    if DISCOVERY_PROCESS is not None and not process_running:
        DISCOVERY_PROCESS = None
    log_tail = ""
    try:
        if DISCOVERY_LOG.is_file() and not DISCOVERY_LOG.is_symlink():
            log_tail = DISCOVERY_LOG.read_text(encoding="utf-8", errors="replace")[-5000:]
    except OSError:
        pass

    schedule = wallpaper_discovery_schedule_snapshot()
    if not DISCOVERY_STATE.is_file() or DISCOVERY_STATE.is_symlink():
        return {
            "campaign": None, "process_running": process_running,
            "log": log_tail, "scheduler": schedule,
        }
    try:
        state = strict_json(DISCOVERY_STATE.read_bytes())
        if not isinstance(state, dict) or not isinstance(state.get("campaign_id"), str):
            raise ValueError("Saved campaign state is invalid.")
        executable = shutil.which("fenrir-catalog")
        if not executable or not CATALOG_DB.is_file():
            return {
                "campaign": None, "process_running": process_running,
                "log": log_tail, "scheduler": schedule,
                "error": "Catalog CLI or database is unavailable.",
            }
        result = subprocess.run(
            [executable, "campaign", "status", "--database", str(CATALOG_DB), state["campaign_id"]],
            capture_output=True, text=True, timeout=12, check=False,
        )
        if result.returncode != 0:
            return {
                "campaign": None, "process_running": process_running,
                "log": log_tail, "scheduler": schedule,
                "error": (result.stderr or result.stdout or "Campaign status unavailable.")[:220],
            }
        payload = strict_json(result.stdout.encode("utf-8"))
        return {
            "campaign": payload,
            "process_running": process_running,
            "source": state.get("source"),
            "profile": state.get("profile"),
            "log": log_tail,
            "scheduler": schedule,
        }
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, BadJSON) as exc:
        return {
            "campaign": None, "process_running": process_running,
            "log": log_tail, "scheduler": schedule, "error": str(exc)[:220],
        }


def wallpaper_acquisition_queue_snapshot() -> dict[str, Any]:
    """Show the read-only Catalog acquisition runway for the active campaign."""
    snapshot = wallpaper_campaign_snapshot()
    campaign = snapshot.get("campaign")
    if not isinstance(campaign, dict) or not isinstance(campaign.get("campaign_id"), str):
        return {
            "campaign": None,
            "queue": None,
            "detail": snapshot.get("error") or "No persisted discovery campaign is available yet.",
            "read_only": True,
            "downloads_started": 0,
        }

    executable = shutil.which("fenrir-catalog")
    if not executable or not CATALOG_DB.is_file():
        return {
            "campaign": {
                "campaign_id": campaign["campaign_id"],
                "source_key": campaign.get("source_key"),
                "profile_key": campaign.get("profile_key"),
                "status": campaign.get("status"),
            },
            "queue": None,
            "detail": "The Fenrir Wallpaper Catalog CLI or local database is unavailable.",
            "read_only": True,
            "downloads_started": 0,
        }

    try:
        result = subprocess.run(
            [
                executable, "catalog", "acquisition", "campaign-queue",
                "--database", str(CATALOG_DB), campaign["campaign_id"],
                "--limit", "100", "--offset", "0",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Acquisition runway unavailable.")[:260]
            return {
                "campaign": {
                    "campaign_id": campaign["campaign_id"],
                    "source_key": campaign.get("source_key"),
                    "profile_key": campaign.get("profile_key"),
                    "status": campaign.get("status"),
                },
                "queue": None,
                "detail": detail,
                "read_only": True,
                "downloads_started": 0,
            }

        payload = strict_json(result.stdout.encode("utf-8"))
        if not isinstance(payload, dict) or payload.get("report") != "org.fenrir.acquisition-campaign-queue":
            raise ValueError("Catalog returned an unsupported acquisition queue report.")
        if payload.get("downloads_started") != 0 or payload.get("read_only") is not True:
            raise ValueError("Catalog acquisition queue did not confirm its read-only contract.")
        return {
            "campaign": payload.get("campaign"),
            "queue": payload,
            "detail": "Campaign acquisition runway loaded from the local, read-only Catalog report.",
            "read_only": True,
            "downloads_started": 0,
        }
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, BadJSON) as exc:
        return {
            "campaign": {
                "campaign_id": campaign["campaign_id"],
                "source_key": campaign.get("source_key"),
                "profile_key": campaign.get("profile_key"),
                "status": campaign.get("status"),
            },
            "queue": None,
            "detail": str(exc)[:260],
            "read_only": True,
            "downloads_started": 0,
        }


def wallpaper_rights_review_snapshot() -> dict[str, Any]:
    """Return a sanitized, read-only summary of the Catalog human-review queue."""
    unavailable = {
        "available": False,
        "queue": None,
        "detail": "The local Fenrir Wallpaper Catalog CLI or database is unavailable.",
        "read_only": True,
        "rights_decisions_created": 0,
        "acquisition_authorizations_created": 0,
    }
    executable = shutil.which("fenrir-catalog")
    if not executable or CATALOG_DB.is_symlink() or not CATALOG_DB.is_file():
        return unavailable

    try:
        result = subprocess.run(
            [
                executable, "catalog", "rights", "queue",
                "--database", str(CATALOG_DB), "--limit", "100",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Rights-review queue unavailable.")[:260]
            return {**unavailable, "detail": detail}

        payload = strict_json(result.stdout.encode("utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("queue") != "human-rights-review"
            or payload.get("read_only") is not True
            or payload.get("automatic_rights_decision") is not False
            or payload.get("automatic_acquisition_authorization") is not False
        ):
            raise ValueError("Catalog rights queue did not confirm its read-only contract.")

        raw_counts = payload.get("status_counts")
        raw_items = payload.get("results")
        if not isinstance(raw_counts, dict) or not isinstance(raw_items, list):
            raise ValueError("Catalog returned an incomplete rights-review report.")

        status_counts: dict[str, int] = {}
        for status in ("unknown", "review_required", "eligible"):
            count = raw_counts.get(status, 0)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("Catalog returned an invalid rights-review status count.")
            status_counts[status] = count

        items: list[dict[str, Any]] = []
        for item in raw_items[:12]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            gaps = item.get("metadata_gaps", [])
            if not isinstance(gaps, list):
                gaps = []
            policy = item.get("policy_assessment")
            review = item.get("latest_human_review")
            items.append({
                "asset_id": item["id"][:128],
                "title": item.get("title") if isinstance(item.get("title"), str) else "Untitled asset",
                "source_key": item.get("source_key") if isinstance(item.get("source_key"), str) else "unknown",
                "rights_status": item.get("rights_status") if isinstance(item.get("rights_status"), str) else "unknown",
                "license_identifier": item.get("license_identifier") if isinstance(item.get("license_identifier"), str) else None,
                "metadata_gaps": [gap[:80] for gap in gaps[:12] if isinstance(gap, str)],
                "evidence_count": item.get("evidence_count") if isinstance(item.get("evidence_count"), int) else 0,
                "policy_decision": policy.get("decision") if isinstance(policy, dict) and isinstance(policy.get("decision"), str) else "unavailable",
                "latest_human_review": {
                    "decision": review.get("decision"),
                    "reviewer": review.get("reviewer"),
                    "recorded_at": review.get("recorded_at"),
                } if isinstance(review, dict) else None,
            })

        total_count = sum(status_counts.values())
        return {
            "available": True,
            "queue": {
                "total_count": total_count,
                "returned_count": len(items),
                "has_more": bool(payload.get("next_cursor")),
                "status_counts": status_counts,
                "items": items,
            },
            "detail": "Read-only rights-review snapshot loaded. Evidence and decisions are handled in the separate guarded Studio.",
            "read_only": True,
            "rights_decisions_created": 0,
            "acquisition_authorizations_created": 0,
        }
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, BadJSON) as exc:
        return {**unavailable, "detail": str(exc)[:260]}


def _stop_rights_review_studio_unlocked() -> None:
    global RIGHTS_STUDIO_PROCESS, RIGHTS_STUDIO_URL
    process = RIGHTS_STUDIO_PROCESS
    RIGHTS_STUDIO_PROCESS = None
    RIGHTS_STUDIO_URL = None
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            if process.stdout is not None:
                process.stdout.close()
        except OSError:
            pass


def stop_wallpaper_rights_review_studio() -> None:
    """Stop the child rights board when Fenrir Doctor shuts down."""
    with RIGHTS_STUDIO_LOCK:
        _stop_rights_review_studio_unlocked()



def _drain_rights_review_studio_output(stream: Any) -> None:
    """Consume child service logs without retaining or blocking on a full pipe."""
    try:
        for _line in stream:
            pass
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass



def start_wallpaper_rights_review_studio() -> dict[str, Any]:
    """Launch or reuse the Catalog's loopback-only, token-protected rights board."""
    global RIGHTS_STUDIO_PROCESS, RIGHTS_STUDIO_URL
    executable = shutil.which("fenrir-catalog")
    if not executable:
        raise RuntimeError("The fenrir-catalog command is not installed.")
    if CATALOG_DB.is_symlink() or not CATALOG_DB.is_file():
        raise ValueError("The Catalog database is missing or is a symbolic link.")

    reviewer = (os.environ.get("USER") or "Fenrir Doctor").strip()[:300] or "Fenrir Doctor"
    with RIGHTS_STUDIO_LOCK:
        if RIGHTS_STUDIO_PROCESS is not None and RIGHTS_STUDIO_PROCESS.poll() is None and RIGHTS_STUDIO_URL:
            return {
                "started": False,
                "already_running": True,
                "url": RIGHTS_STUDIO_URL,
                "message": "The existing local Rights Review Studio session is ready.",
            }

        _stop_rights_review_studio_unlocked()
        process = subprocess.Popen(
            [
                executable, "catalog", "rights", "board",
                "--database", str(CATALOG_DB),
                "--reviewer", reviewer,
                "--port", "0",
                "--no-browser",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            close_fds=True,
            start_new_session=True,
        )
        try:
            if process.stdout is None:
                raise RuntimeError("Catalog did not provide a startup status stream.")
            ready, _, _ = select.select([process.stdout], [], [], 10)
            if not ready:
                raise RuntimeError("The Rights Review Studio did not announce readiness within ten seconds.")
            announcement = process.stdout.readline().strip()
            prefix = "Fenrir Rights Review Board: "
            if not announcement.startswith(prefix):
                raise RuntimeError("Catalog could not start the Rights Review Studio: " + announcement[:180])
            board_url = announcement[len(prefix):].strip()
            parsed = urllib.parse.urlparse(board_url)
            if (
                parsed.scheme != "http"
                or parsed.hostname != "127.0.0.1"
                or parsed.port is None
                or not 1 <= parsed.port <= 65535
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or re.fullmatch(r"/s/[A-Za-z0-9_-]{32,64}/", parsed.path) is None
            ):
                raise RuntimeError("Catalog returned a non-loopback or invalid Rights Review Studio URL.")
            if process.poll() is not None:
                raise RuntimeError("The Rights Review Studio exited during startup.")
            threading.Thread(
                target=_drain_rights_review_studio_output,
                args=(process.stdout,),
                name="fenrir-rights-studio-output",
                daemon=True,
            ).start()
        except Exception:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                if process.stdout is not None:
                    process.stdout.close()
            except OSError:
                pass
            raise

        RIGHTS_STUDIO_PROCESS = process
        RIGHTS_STUDIO_URL = board_url
        return {
            "started": True,
            "already_running": False,
            "url": board_url,
            "message": "A private loopback-only Rights Review Studio session is ready.",
        }


def _start_wallpaper_discovery_unlocked(
    source: Any,
    profile: Any,
    contact: Any = None,
    *,
    max_queries: int = 100,
) -> dict[str, Any]:
    global DISCOVERY_PROCESS
    allowed_sources = {"openverse", "wikimedia_commons", "wallhaven"}
    allowed_profiles = DISCOVERY_PROFILES
    if isinstance(max_queries, bool) or not isinstance(max_queries, int) or not 1 <= max_queries <= 100:
        raise ValueError("Discovery max_queries must be between 1 and 100.")
    if source not in allowed_sources:
        raise ValueError("Choose Openverse, Wikimedia Commons or Wallhaven.")
    if profile not in allowed_profiles:
        raise ValueError("Choose a supported Fenrir wallpaper discovery profile.")
    if DISCOVERY_PROCESS is not None and DISCOVERY_PROCESS.poll() is None:
        raise ValueError("A wallpaper discovery campaign is already running.")
    executable = shutil.which("fenrir-catalog")
    if not executable or not CATALOG_DB.is_file():
        raise ValueError("The local Fenrir Wallpaper Catalog is not ready.")
    if source == "wikimedia_commons":
        if not isinstance(contact, str) or not contact.strip() or len(contact) > 300:
            raise ValueError("Commons discovery requires a contact email or HTTPS project URL.")
    elif contact not in (None, ""):
        raise ValueError("A contact field is accepted only for Wikimedia Commons.")

    campaign_id = None
    resumed = False
    if DISCOVERY_STATE.is_file() and not DISCOVERY_STATE.is_symlink():
        try:
            previous = strict_json(DISCOVERY_STATE.read_bytes())
            if previous.get("source") == source and previous.get("profile") == profile:
                status_result = subprocess.run(
                    [
                        executable, "campaign", "status",
                        "--database", str(CATALOG_DB), previous.get("campaign_id", ""),
                    ],
                    capture_output=True, text=True, timeout=12, check=False,
                )
                if status_result.returncode == 0:
                    previous_status = strict_json(status_result.stdout.encode("utf-8"))
                    if previous_status.get("status") in {"planned", "running", "paused", "failed"}:
                        campaign_id = previous.get("campaign_id")
                        resumed = True
        except (OSError, ValueError, TypeError, subprocess.SubprocessError, BadJSON):
            campaign_id = None

    if campaign_id is None:
        create_args = [
            executable, "campaign", "create",
            "--database", str(CATALOG_DB),
            "--source", source,
            "--profile", profile,
            "--limit", "20",
            "--max-pages-per-query", str(DISCOVERY_SLICE_MAX_PAGES),
        ]
        created = subprocess.run(
            create_args, capture_output=True, text=True, timeout=20, check=False,
        )
        if created.returncode != 0:
            raise ValueError((created.stderr or created.stdout or "Could not create discovery campaign.")[:300])
        payload = strict_json(created.stdout.encode("utf-8"))
        campaign_id = payload.get("campaign_id")
        if not isinstance(campaign_id, str) or not campaign_id:
            raise ValueError("Catalog did not return a campaign identifier.")
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_json(DISCOVERY_STATE, {
            "campaign_id": campaign_id,
            "source": source,
            "profile": profile,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    log = DISCOVERY_LOG.open("a" if resumed else "w", encoding="utf-8")
    run_args = [
        executable, "campaign", "run",
        "--database", str(CATALOG_DB),
        "--source", source,
        "--profile", profile,
        "--campaign-id", campaign_id,
        "--max-queries", str(max_queries),
        "--max-pages-per-query", str(DISCOVERY_SLICE_MAX_PAGES),
        "--limit", "20",
    ]
    if source == "wikimedia_commons":
        run_args.extend(["--contact", contact.strip()])
    try:
        DISCOVERY_PROCESS = subprocess.Popen(
            run_args,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError:
        log.close()
        raise
    log.close()
    return {
        "started": True,
        "resumed": resumed,
        "pid": DISCOVERY_PROCESS.pid,
        "campaign_id": campaign_id,
        "max_queries_per_run": max_queries,
        "max_pages_per_query": DISCOVERY_SLICE_MAX_PAGES,
        "downloads_started": False,
        "rights_decisions_created": 0,
        "acceptances_created": 0,
    }



def _default_wallpaper_discovery_schedule() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "enabled": False,
        "source": "openverse",
        "profile": "fenrir-nordic-fantasy-v1",
        "contact": None,
        "interval_minutes": 360,
        "next_run_at": None,
        "last_run_at": None,
        "last_status": "disabled",
        "pause_reason": None,
        "last_error": None,
        "campaign_id": None,
        "queue": [],
        "queue_index": 0,
    }


def _validate_wallpaper_campaign_queue(raw_queue: Any) -> list[dict[str, Any]]:
    """Validate a finite, unique source/profile queue before persisting it."""
    allowed_sources = {"openverse", "wikimedia_commons", "wallhaven"}
    if not isinstance(raw_queue, list) or not raw_queue:
        raise ValueError("Choose at least one wallpaper campaign for the queue.")
    if len(raw_queue) > 18:
        raise ValueError("A discovery queue may contain at most 18 unique source/profile campaigns.")

    queue: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_queue):
        if not isinstance(item, dict) or set(item) - {"source", "profile", "contact"}:
            raise ValueError(f"Queue item {index + 1} has an invalid structure.")
        source = item.get("source")
        profile = item.get("profile")
        contact = item.get("contact")
        if not isinstance(source, str) or source not in allowed_sources:
            raise ValueError(f"Queue item {index + 1} has an unsupported source.")
        if not isinstance(profile, str) or profile not in DISCOVERY_PROFILES:
            raise ValueError(f"Queue item {index + 1} has an unsupported profile.")
        if (source, profile) in seen:
            raise ValueError("A source/profile combination may appear only once in a queue.")
        seen.add((source, profile))

        if source == "wikimedia_commons":
            if not isinstance(contact, str) or not contact.strip() or len(contact) > 300:
                raise ValueError("Every Wikimedia Commons queue item requires a contact email or HTTPS project URL.")
            contact = contact.strip()
        elif contact not in (None, ""):
            raise ValueError("A contact identifier is accepted only for Wikimedia Commons.")
        else:
            contact = None

        queue.append({"source": source, "profile": profile, "contact": contact})
    return queue


def read_wallpaper_discovery_schedule() -> dict[str, Any]:
    """Read bounded scheduler state; malformed or symlinked state fails closed."""
    defaults = _default_wallpaper_discovery_schedule()
    path = DISCOVERY_SCHEDULE_FILE
    try:
        if path.is_symlink():
            raise ValueError("Scheduler state must not be a symbolic link.")
        if not path.exists():
            return defaults
        if not path.is_file() or path.stat().st_size > 8192:
            raise ValueError("Scheduler state is not a regular file or exceeds 8 KiB.")
        raw = strict_json(path.read_bytes())
        if not isinstance(raw, dict) or raw.get("schema_version") not in {1, 2}:
            raise ValueError("Unsupported scheduler state format.")
        if not isinstance(raw.get("enabled"), bool):
            raise ValueError("Scheduler enabled state is invalid.")
        if raw.get("source") not in {"openverse", "wikimedia_commons", "wallhaven"}:
            raise ValueError("Scheduler source is invalid.")
        if raw.get("profile") not in DISCOVERY_PROFILES:
            raise ValueError("Scheduler profile is invalid.")
        interval = raw.get("interval_minutes")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval not in DISCOVERY_SCHEDULE_INTERVALS:
            raise ValueError("Scheduler interval is invalid.")
        contact = raw.get("contact")
        if contact is not None and (not isinstance(contact, str) or len(contact) > 300):
            raise ValueError("Scheduler contact value is invalid.")
        for key in ("next_run_at", "last_run_at"):
            value = raw.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
                or value < 1 or value > 4102444800
            ):
                raise ValueError(f"Scheduler {key} value is invalid.")
        for key in ("pause_reason", "last_error"):
            value = raw.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > 1000):
                raise ValueError(f"Scheduler {key} value is invalid.")
        campaign_id = raw.get("campaign_id")
        if campaign_id is not None and (
            not isinstance(campaign_id, str) or not campaign_id or len(campaign_id) > 128
        ):
            raise ValueError("Scheduler campaign identifier is invalid.")
        status = raw.get("last_status", "disabled")
        if status not in {
            "disabled", "running", "scheduled", "paused", "needs_review",
            "paused_error", "invalid",
        }:
            raise ValueError("Scheduler status is invalid.")

        # Version 1 state is migrated in memory. The original state file remains
        # untouched until the next explicit scheduler update.
        queue = []
        queue_index = 0
        if raw.get("schema_version") == 2:
            raw_queue = raw.get("queue", [])
            if not isinstance(raw_queue, list):
                raise ValueError("Scheduler queue must be a list.")
            queue = _validate_wallpaper_campaign_queue(raw_queue) if raw_queue else []
            queue_index = raw.get("queue_index", 0)
            if (
                isinstance(queue_index, bool) or not isinstance(queue_index, int)
                or not 0 <= queue_index <= len(queue)
                or (not queue and queue_index != 0)
            ):
                raise ValueError("Scheduler queue position is invalid.")

        return {
            **defaults,
            "enabled": raw["enabled"],
            "source": raw["source"],
            "profile": raw["profile"],
            "contact": contact,
            "interval_minutes": interval,
            "next_run_at": raw.get("next_run_at"),
            "last_run_at": raw.get("last_run_at"),
            "last_status": status,
            "pause_reason": raw.get("pause_reason"),
            "last_error": raw.get("last_error"),
            "campaign_id": campaign_id,
            "queue": queue,
            "queue_index": queue_index,
        }
    except (OSError, ValueError, TypeError, BadJSON) as exc:
        defaults["last_status"] = "invalid"
        defaults["pause_reason"] = str(exc)[:500]
        return defaults


def _write_wallpaper_discovery_schedule(schedule: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    schedule["schema_version"] = 2
    atomic_json(DISCOVERY_SCHEDULE_FILE, schedule)


def wallpaper_discovery_schedule_snapshot() -> dict[str, Any]:
    schedule = read_wallpaper_discovery_schedule()
    queue = schedule["queue"]
    queue_index = schedule["queue_index"]
    # The local scheduler only needs source/profile labels in the UI. Keep
    # Commons contact identifiers private to the mode-0600 scheduler state.
    queue_summary = [
        {
            "source": item["source"],
            "profile": item["profile"],
            "contact_configured": bool(item["contact"]),
        }
        for item in queue
    ]
    return {
        "enabled": schedule["enabled"],
        "source": schedule["source"],
        "profile": schedule["profile"],
        "interval_minutes": schedule["interval_minutes"],
        "next_run_at": schedule["next_run_at"],
        "last_run_at": schedule["last_run_at"],
        "last_status": schedule["last_status"],
        "pause_reason": schedule["pause_reason"],
        "last_error": schedule["last_error"],
        "campaign_id": schedule["campaign_id"],
        "contact_configured": bool(schedule["contact"]),
        "queue": queue_summary,
        "queue_index": queue_index,
        "queue_total": len(queue),
        "queue_position": min(queue_index + 1, len(queue)) if queue else 0,
        "queue_completed": bool(queue) and queue_index >= len(queue),
        "queue_current": (
            queue_summary[queue_index] if queue_summary and queue_index < len(queue_summary) else None
        ),
    }


def start_wallpaper_discovery(
    source: Any,
    profile: Any,
    contact: Any = None,
) -> dict[str, Any]:
    with DISCOVERY_LOCK:
        schedule = read_wallpaper_discovery_schedule()
        if schedule["enabled"] and (
            source != schedule["source"] or profile != schedule["profile"]
        ):
            raise ValueError(
                "Pause automatic discovery before changing its source or profile."
            )
        return _start_wallpaper_discovery_unlocked(source, profile, contact)


def configure_wallpaper_discovery_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    """Enable, resume or pause a finite, sequential metadata-discovery queue."""
    if not isinstance(payload, dict) or not isinstance(payload.get("enabled"), bool):
        raise ValueError("Automatic discovery enabled state must be true or false.")
    with DISCOVERY_LOCK:
        schedule = read_wallpaper_discovery_schedule()
        if payload["enabled"] is False:
            was_enabled = schedule["enabled"]
            schedule["enabled"] = False
            schedule["next_run_at"] = None
            schedule["last_status"] = "paused" if was_enabled else "disabled"
            schedule["pause_reason"] = (
                "Automatic scheduling paused. Any currently running metadata slice will finish."
                if was_enabled else None
            )
            schedule["last_error"] = None
            _write_wallpaper_discovery_schedule(schedule)
            return wallpaper_discovery_schedule_snapshot()

        interval = payload.get("interval_minutes", schedule["interval_minutes"])
        if isinstance(interval, bool) or not isinstance(interval, int) or interval not in DISCOVERY_SCHEDULE_INTERVALS:
            raise ValueError("Choose an automatic discovery interval of 1, 3, 6, 12 or 24 hours.")

        resume_existing = payload.get("resume_existing_queue", False)
        if not isinstance(resume_existing, bool):
            raise ValueError("Queue resume flag must be true or false.")

        if resume_existing:
            queue = schedule["queue"]
            queue_index = schedule["queue_index"]
            if not queue or queue_index >= len(queue):
                raise ValueError("There is no unfinished saved campaign queue to resume.")
            snapshot = wallpaper_campaign_snapshot()
            campaign = snapshot.get("campaign")
            if snapshot.get("process_running"):
                active = queue[queue_index]
                if snapshot.get("source") != active["source"] or snapshot.get("profile") != active["profile"]:
                    raise ValueError("The running campaign does not match the saved queue; inspect it before resuming.")
            elif campaign is not None and campaign.get("status") == "completed":
                queue_index += 1
                if queue_index >= len(queue):
                    schedule.update({
                        "enabled": False,
                        "queue_index": len(queue),
                        "next_run_at": None,
                        "last_status": "needs_review",
                        "pause_reason": (
                            "The saved discovery queue is complete. Human rights review and explicit "
                            "acceptance are required before acquisition or desktop synchronization."
                        ),
                    })
                    _write_wallpaper_discovery_schedule(schedule)
                    return wallpaper_discovery_schedule_snapshot()
            elif campaign is not None and campaign.get("status") == "failed":
                raise ValueError("The saved campaign failed. Review the error before creating a new queue.")

            active = queue[queue_index]
            source, profile, contact = active["source"], active["profile"], active["contact"]
            process_running = DISCOVERY_PROCESS is not None and DISCOVERY_PROCESS.poll() is None
            if process_running:
                if DISCOVERY_STATE.is_symlink() or not DISCOVERY_STATE.is_file():
                    raise ValueError("The active campaign state cannot be verified; inspect it before resuming.")
                state = strict_json(DISCOVERY_STATE.read_bytes())
                campaign_id = state.get("campaign_id")
                if not isinstance(campaign_id, str) or not campaign_id:
                    raise ValueError("The active campaign identifier is invalid.")
            else:
                started = _start_wallpaper_discovery_unlocked(
                    source, profile, contact, max_queries=DISCOVERY_SLICE_MAX_QUERIES,
                )
                campaign_id = started["campaign_id"]
        else:
            if "queue" in payload:
                queue = _validate_wallpaper_campaign_queue(payload["queue"])
            else:
                source = payload.get("source", schedule["source"])
                profile = payload.get("profile", schedule["profile"])
                contact = payload.get("contact")
                queue = _validate_wallpaper_campaign_queue([{
                    "source": source, "profile": profile, "contact": contact,
                }])
            queue_index = 0
            active = queue[0]
            source, profile, contact = active["source"], active["profile"], active["contact"]

            if DISCOVERY_PROCESS is not None and DISCOVERY_PROCESS.poll() is None:
                raise ValueError("A metadata campaign is already running; let it finish or pause it before replacing the queue.")
            started = _start_wallpaper_discovery_unlocked(
                source, profile, contact, max_queries=DISCOVERY_SLICE_MAX_QUERIES,
            )
            campaign_id = started["campaign_id"]

        now = int(time.time())
        schedule.update({
            "schema_version": 2,
            "enabled": True,
            "source": source,
            "profile": profile,
            "contact": contact,
            "interval_minutes": interval,
            "next_run_at": now + interval * 60,
            "last_run_at": now,
            "last_status": "running",
            "pause_reason": None,
            "last_error": None,
            "campaign_id": campaign_id,
            "queue": queue,
            "queue_index": queue_index,
        })
        _write_wallpaper_discovery_schedule(schedule)
        return wallpaper_discovery_schedule_snapshot()


def wallpaper_discovery_scheduler_tick(now: int | None = None) -> dict[str, Any]:
    """Run one bounded slice at a time and rotate campaigns only after completion."""
    current_time = int(time.time()) if now is None else int(now)
    with DISCOVERY_LOCK:
        schedule = read_wallpaper_discovery_schedule()
        if not schedule["enabled"]:
            return wallpaper_discovery_schedule_snapshot()

        snapshot = wallpaper_campaign_snapshot()
        if snapshot.get("process_running"):
            if schedule["last_status"] != "running":
                schedule["last_status"] = "running"
                _write_wallpaper_discovery_schedule(schedule)
            return wallpaper_discovery_schedule_snapshot()

        campaign = snapshot.get("campaign")
        if campaign is not None:
            campaign_status = campaign.get("status")
            if campaign_status == "completed":
                queue = schedule["queue"]
                next_index = schedule["queue_index"] + 1 if queue else 0
                if queue and next_index < len(queue):
                    next_item = queue[next_index]
                    try:
                        result = _start_wallpaper_discovery_unlocked(
                            next_item["source"], next_item["profile"], next_item["contact"],
                            max_queries=DISCOVERY_SLICE_MAX_QUERIES,
                        )
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                        schedule.update({
                            "enabled": False,
                            "next_run_at": None,
                            "last_status": "paused_error",
                            "pause_reason": "Automatic discovery stopped while advancing to the next queued campaign.",
                            "last_error": str(exc)[:1000],
                        })
                        _write_wallpaper_discovery_schedule(schedule)
                        return wallpaper_discovery_schedule_snapshot()

                    schedule.update({
                        "source": next_item["source"],
                        "profile": next_item["profile"],
                        "contact": next_item["contact"],
                        "queue_index": next_index,
                        "campaign_id": result["campaign_id"],
                        "next_run_at": current_time + schedule["interval_minutes"] * 60,
                        "last_run_at": current_time,
                        "last_status": "running",
                        "pause_reason": None,
                        "last_error": None,
                    })
                    _write_wallpaper_discovery_schedule(schedule)
                    return wallpaper_discovery_schedule_snapshot()

                schedule.update({
                    "enabled": False,
                    "queue_index": len(queue) if queue else 0,
                    "next_run_at": None,
                    "last_status": "needs_review",
                    "pause_reason": (
                        "Metadata discovery is complete. Human rights review and explicit "
                        "acceptance are required before acquisition or desktop synchronization."
                    ),
                })
                _write_wallpaper_discovery_schedule(schedule)
                return wallpaper_discovery_schedule_snapshot()
            if campaign_status == "failed":
                error = campaign.get("error_summary") or "The Catalog campaign failed."
                schedule.update({
                    "enabled": False,
                    "next_run_at": None,
                    "last_status": "paused_error",
                    "pause_reason": "Automatic discovery stopped after a campaign error.",
                    "last_error": str(error)[:1000],
                })
                _write_wallpaper_discovery_schedule(schedule)
                return wallpaper_discovery_schedule_snapshot()
            if campaign_status not in {"planned", "running", "paused"}:
                schedule.update({
                    "enabled": False,
                    "next_run_at": None,
                    "last_status": "paused_error",
                    "pause_reason": "The campaign state is not resumable; inspect it before continuing.",
                    "last_error": f"Unexpected campaign status: {campaign_status!r}"[:1000],
                })
                _write_wallpaper_discovery_schedule(schedule)
                return wallpaper_discovery_schedule_snapshot()
        elif snapshot.get("error"):
            schedule.update({
                "enabled": False,
                "next_run_at": None,
                "last_status": "paused_error",
                "pause_reason": "Automatic discovery stopped because the Catalog status is unavailable.",
                "last_error": str(snapshot["error"])[:1000],
            })
            _write_wallpaper_discovery_schedule(schedule)
            return wallpaper_discovery_schedule_snapshot()

        next_run_at = schedule["next_run_at"]
        if next_run_at is not None and current_time < next_run_at:
            if schedule["last_status"] != "scheduled":
                schedule["last_status"] = "scheduled"
                _write_wallpaper_discovery_schedule(schedule)
            return wallpaper_discovery_schedule_snapshot()

        try:
            result = _start_wallpaper_discovery_unlocked(
                schedule["source"], schedule["profile"], schedule["contact"],
                max_queries=DISCOVERY_SLICE_MAX_QUERIES,
            )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            schedule.update({
                "enabled": False,
                "next_run_at": None,
                "last_status": "paused_error",
                "pause_reason": "Automatic discovery stopped after an execution error.",
                "last_error": str(exc)[:1000],
            })
            _write_wallpaper_discovery_schedule(schedule)
            return wallpaper_discovery_schedule_snapshot()

        schedule.update({
            "next_run_at": current_time + schedule["interval_minutes"] * 60,
            "last_run_at": current_time,
            "last_status": "running",
            "pause_reason": None,
            "last_error": None,
            "campaign_id": result["campaign_id"],
        })
        _write_wallpaper_discovery_schedule(schedule)
        return wallpaper_discovery_schedule_snapshot()


def _wallpaper_discovery_scheduler_loop() -> None:
    while not DISCOVERY_SCHEDULER_STOP.wait(30):
        try:
            wallpaper_discovery_scheduler_tick()
        except Exception as exc:
            with DISCOVERY_LOCK:
                schedule = read_wallpaper_discovery_schedule()
                if schedule["enabled"]:
                    schedule.update({
                        "enabled": False,
                        "next_run_at": None,
                        "last_status": "paused_error",
                        "pause_reason": "The scheduler encountered an unexpected error and stopped safely.",
                        "last_error": str(exc)[:1000],
                    })
                    try:
                        _write_wallpaper_discovery_schedule(schedule)
                    except OSError:
                        pass


def start_wallpaper_discovery_scheduler() -> None:
    global DISCOVERY_SCHEDULER_THREAD
    if DISCOVERY_SCHEDULER_THREAD is not None and DISCOVERY_SCHEDULER_THREAD.is_alive():
        return
    DISCOVERY_SCHEDULER_STOP.clear()
    DISCOVERY_SCHEDULER_THREAD = threading.Thread(
        target=_wallpaper_discovery_scheduler_loop,
        name="fenrir-wallpaper-discovery-scheduler",
        daemon=True,
    )
    DISCOVERY_SCHEDULER_THREAD.start()




def wallpaper_snapshot() -> dict[str, Any]:
    target_count = read_settings().get("wallpaper_target_count", 5000)
    accepted = None
    catalog_available = shutil.which("fenrir-catalog") is not None and CATALOG_DB.is_file() and QUARANTINE_ROOT.is_dir()
    detail = "Catalog is not installed or its local database has not been initialized."
    if catalog_available:
        try:
            result = subprocess.run(
                ["fenrir-catalog", "catalog", "library", "facets", "--database", str(CATALOG_DB)],
                capture_output=True, text=True, timeout=12, check=False,
            )
            if result.returncode == 0:
                payload = strict_json(result.stdout.encode("utf-8"))
                accepted = int(payload.get("accepted_asset_count", 0))
                detail = "Accepted-library count loaded from the local catalog."
            else:
                detail = (result.stderr or result.stdout or "Catalog query failed.")[:220]
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            detail = "Catalog status could not be loaded."
    wallpaper_directory = current_wallpaper_directory()
    sync_destination_allowed = wallpaper_sync_destination_allowed(wallpaper_directory)
    if not sync_destination_allowed:
        detail = "The selected wallpaper folder is outside ~/Pictures; choose a folder under Pictures before catalog sync."
    local_count = 0
    palette_metrics = {
        "excluded_palette_color": 0,
        "below_resolution_or_wrong_orientation": 0,
        "invalid_files": 0,
        "checked_files": 0,
        "cached_files": 0,
        "palette_policy": "fenrir-wallpaper-palette-v1",
    }
    if catalog_available and wallpaper_directory.is_dir() and sync_destination_allowed:
        try:
            count_result = subprocess.run(
                [
                    "fenrir-catalog", "catalog", "library", "count-local",
                    "--directory", str(wallpaper_directory),
                    "--cache-file", str(STATE / "wallpaper-palette-index.json"),
                ],
                capture_output=True, text=True, timeout=90, check=False,
            )
            if count_result.returncode == 0:
                count_payload = strict_json(count_result.stdout.encode("utf-8"))
                local_count = int(count_payload.get("count", 0))
                palette_metrics = {
                    "excluded_palette_color": int(count_payload.get("excluded_palette_color", 0)),
                    "below_resolution_or_wrong_orientation": int(count_payload.get("below_resolution_or_wrong_orientation", 0)),
                    "invalid_files": int(count_payload.get("invalid_files", 0)),
                    "checked_files": int(count_payload.get("checked_files", 0)),
                    "cached_files": int(count_payload.get("cached_files", 0)),
                    "palette_policy": count_payload.get("palette_policy", "fenrir-wallpaper-palette-v1"),
                }
            else:
                detail = (count_result.stderr or count_result.stdout or "Wallpaper palette index failed.")[:220]
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            detail = "The Catalog palette index could not be loaded."
    sync = {"running": False, "log": ""}
    global WALLPAPER_SYNC
    if WALLPAPER_SYNC is not None:
        code = WALLPAPER_SYNC.poll()
        log_tail = ""
        try:
            log_tail = WALLPAPER_SYNC_LOG.read_text(encoding="utf-8", errors="replace")[-5000:]
        except OSError:
            pass
        sync = {"running": code is None, "returncode": code, "log": log_tail}
        if code is not None:
            WALLPAPER_SYNC = None
    return {
        "catalog_available": catalog_available,
        "sync_destination_allowed": sync_destination_allowed,
        "destination": str(wallpaper_directory),
        "accepted_asset_count": accepted,
        "local_image_count": local_count,
        "palette_metrics": palette_metrics,
        "discovery": wallpaper_campaign_snapshot(),
        "target_count": target_count,
        "remaining": max(0, target_count - local_count),
        "target_reached": local_count >= target_count,
        "detail": detail,
        "sync": sync,
    }


def start_wallpaper_sync(target_count: Any) -> dict[str, Any]:
    global WALLPAPER_SYNC
    if target_count not in {5000, 10000, 20000}:
        raise ValueError("Choose a wallpaper target of 5,000, 10,000 or 20,000.")
    if WALLPAPER_SYNC is not None and WALLPAPER_SYNC.poll() is None:
        raise ValueError("A wallpaper synchronization is already running.")
    executable = shutil.which("fenrir-catalog")
    if not executable or not CATALOG_DB.is_file() or not QUARANTINE_ROOT.is_dir():
        raise ValueError("The local Fenrir Wallpaper Catalog is not ready.")
    wallpaper_directory = current_wallpaper_directory()
    if not wallpaper_sync_destination_allowed(wallpaper_directory):
        raise ValueError("Catalog sync is sandboxed to folders under ~/Pictures. Change the wallpaper directory in Fenrir Settings first.")
    wallpaper_directory.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = WALLPAPER_SYNC_LOG.open("w", encoding="utf-8")
    try:
        WALLPAPER_SYNC = subprocess.Popen(
            [
                executable, "catalog", "library", "sync",
                "--database", str(CATALOG_DB),
                "--quarantine-root", str(QUARANTINE_ROOT),
                "--destination", str(wallpaper_directory),
                "--target-count", str(target_count),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError:
        log.close()
        raise
    log.close()
    return {"started": True, "pid": WALLPAPER_SYNC.pid, "target_count": target_count}


def launch_upgrade_terminal() -> dict[str, Any]:
    terminal = shutil.which("kitty")
    updater = shutil.which("fenrir-upgrade")
    if not terminal or not updater:
        raise RuntimeError("The Fenrir upgrade command or Kitty terminal is not installed.")
    unit = f"fenrir-upgrade-{os.getpid()}"
    try:
        process = subprocess.Popen(
            [
                "systemd-run", "--user", f"--unit={unit}", "--collect",
                terminal, "--title", "Fenrir Upgrade", updater, "apply",
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not open the upgrade terminal: {exc}") from exc
    return {"started": True, "pid": process.pid, "message": "Upgrade terminal opened. Review the package transaction before confirming."}


class Handler(BaseHTTPRequestHandler):
    server_version = "FenrirDoctor/0.12.2"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log prompt, response, or request-body content.
        print(f"Fenrir Doctor: {self.address_string()} {fmt % args}")

    def secure_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def send_bytes(self, status: int, payload: Any, content_type: str = "application/json; charset=utf-8") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.secure_headers()
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self) -> bool:
        return self.headers.get("Host", "") in {"127.0.0.1:8765", "localhost:8765"}

    def origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in {"http://127.0.0.1:8765", "http://localhost:8765"}

    def get_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length <= 0 or length > MAX_BODY:
            raise ValueError("request body must be between 1 byte and 256 KiB")
        value = strict_json(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        if not self.host_ok():
            return self.send_bytes(400, {"error": "invalid host"})
        path = urlparse(self.path).path
        static = {"/": "index.html", "/assets/app.js": "assets/app.js", "/assets/style.css": "assets/style.css"}
        if path in static:
            target = (APP / static[path]).resolve()
            if APP.resolve() not in target.parents and target != APP.resolve():
                return self.send_bytes(404, {"error": "not found"})
            try:
                body = target.read_bytes()
            except OSError:
                return self.send_bytes(404, {"error": "not found"})
            content_type = "text/html; charset=utf-8" if target.suffix == ".html" else ("text/javascript; charset=utf-8" if target.suffix == ".js" else "text/css; charset=utf-8")
            return self.send_bytes(200, body, content_type)
        if path == "/api/palette":
            palette_file = CONFIG_HOME / "fenrir" / "palette.json"
            try:
                palette = strict_json(palette_file.read_bytes())
                return self.send_bytes(200, palette)
            except (OSError, ValueError, TypeError):
                return self.send_bytes(200, {"accent": "#a997ff", "accent_soft": "#51447f", "foreground": "#e8e9f2", "muted": "#9699ab", "border": "#7665bd", "surface_opacity": 0.60})
        if path == "/api/health":
            try:
                data = ollama_json("/api/tags", timeout=3)
                models = [model.get("name") for model in data.get("models", []) if model.get("name")]
                return self.send_bytes(200, {"ollama": True, "models": models})
            except Exception as exc:
                return self.send_bytes(200, {"ollama": False, "models": [], "detail": str(exc)[:240]})
        if path == "/api/models":
            try:
                data = ollama_json("/api/tags", timeout=5)
                models = [{"name": model.get("name"), "size": model.get("size")} for model in data.get("models", []) if model.get("name")]
                return self.send_bytes(200, {"models": models})
            except Exception as exc:
                return self.send_bytes(503, {"error": f"Ollama unavailable: {exc}"})
        if path == "/api/system":
            return self.send_bytes(200, system_snapshot())
        if path == "/api/doctor/diagnostics":
            return self.send_bytes(200, diagnostics_snapshot())
        if path == "/api/doctor/updates":
            return self.send_bytes(200, updates_snapshot())
        if path == "/api/doctor/backups":
            return self.send_bytes(200, backups_snapshot())
        if path == "/api/doctor/wallpapers":
            return self.send_bytes(200, wallpaper_snapshot())
        if path == "/api/doctor/wallpapers/campaign":
            return self.send_bytes(200, wallpaper_campaign_snapshot())
        if path == "/api/doctor/wallpapers/acquisition-queue":
            return self.send_bytes(200, wallpaper_acquisition_queue_snapshot())
        if path == "/api/doctor/wallpapers/rights-review":
            return self.send_bytes(200, wallpaper_rights_review_snapshot())
        if path == "/api/weather":
            try:
                return self.send_bytes(200, weather_snapshot())
            except Exception as exc:
                return self.send_bytes(503, {"error": f"Weather unavailable: {str(exc)[:200]}"})
        if path == "/api/settings":
            return self.send_bytes(200, read_settings())
        if path == "/api/chats":
            with db() as conn:
                rows = conn.execute("SELECT id,title,created_at,updated_at FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 40").fetchall()
            return self.send_bytes(200, {"chats": [dict(row) for row in rows]})
        if path.startswith("/api/chats/"):
            try:
                chat_id = int(path.rsplit("/", 1)[1])
            except ValueError:
                return self.send_bytes(400, {"error": "invalid conversation id"})
            with db() as conn:
                chat = conn.execute("SELECT id,title FROM conversations WHERE id=?", (chat_id,)).fetchone()
                if not chat:
                    return self.send_bytes(404, {"error": "conversation not found"})
                rows = conn.execute("SELECT role,content,model,created_at FROM messages WHERE conversation_id=? ORDER BY id", (chat_id,)).fetchall()
            return self.send_bytes(200, {"chat": dict(chat), "messages": [dict(row) for row in rows]})
        return self.send_bytes(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self.host_ok() or not self.origin_ok():
            return self.send_bytes(403, {"error": "request origin rejected"})
        path = urlparse(self.path).path
        try:
            obj = self.get_body()
        except (UnicodeError, json.JSONDecodeError, ValueError, BadJSON) as exc:
            return self.send_bytes(400, {"error": str(exc)})

        if path == "/api/settings":
            model = obj.get("default_model", "")
            location = obj.get("location", "")
            latitude = obj.get("latitude")
            longitude = obj.get("longitude")
            if not isinstance(model, str) or len(model) > 160:
                return self.send_bytes(400, {"error": "model name must be at most 160 characters"})
            if not isinstance(location, str) or len(location) > 100:
                return self.send_bytes(400, {"error": "location name must be at most 100 characters"})
            if latitude in (None, "") and longitude in (None, ""):
                latitude = longitude = None
            else:
                if isinstance(latitude, bool) or isinstance(longitude, bool):
                    return self.send_bytes(400, {"error": "latitude and longitude must be numeric"})
                try:
                    latitude, longitude = float(latitude), float(longitude)
                except (TypeError, ValueError):
                    return self.send_bytes(400, {"error": "provide both latitude and longitude"})
                if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                    return self.send_bytes(400, {"error": "coordinates out of range"})
            target_count = obj.get("wallpaper_target_count", read_settings().get("wallpaper_target_count", 5000))
            if target_count not in {5000, 10000, 20000}:
                return self.send_bytes(400, {"error": "Wallpaper target must be 5000, 10000 or 20000."})
            settings = {
                "default_model": model.strip(),
                "weather": {"location": location.strip(), "latitude": latitude, "longitude": longitude},
                "wallpaper_target_count": target_count,
            }
            atomic_json(SETTINGS_FILE, settings)
            return self.send_bytes(200, {"saved": True, **settings})

        if path == "/api/doctor/recovery":
            try:
                result = restore_backup(obj.get("backup_id"))
                return self.send_bytes(200, {"success": True, **result})
            except (OSError, ValueError, shutil.Error) as exc:
                return self.send_bytes(400, {"error": str(exc)[:260]})
        if path == "/api/doctor/upgrade":
            try:
                return self.send_bytes(202, launch_upgrade_terminal())
            except RuntimeError as exc:
                return self.send_bytes(503, {"error": str(exc)[:260]})
        if path == "/api/doctor/wallpapers/rights-studio":
            try:
                return self.send_bytes(200, start_wallpaper_rights_review_studio())
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                return self.send_bytes(503, {"error": str(exc)[:300]})

        if path == "/api/doctor/wallpapers/sync":
            try:
                return self.send_bytes(202, start_wallpaper_sync(obj.get("target_count", 5000)))
            except (OSError, ValueError) as exc:
                return self.send_bytes(400, {"error": str(exc)[:260]})

        if path == "/api/doctor/wallpapers/schedule":
            try:
                return self.send_bytes(202, configure_wallpaper_discovery_schedule(obj))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                return self.send_bytes(400, {"error": str(exc)[:300]})

        if path == "/api/doctor/wallpapers/discover":
            try:
                return self.send_bytes(202, start_wallpaper_discovery(
                    obj.get("source"), obj.get("profile"), obj.get("contact")
                ))
            except (OSError, ValueError) as exc:
                return self.send_bytes(400, {"error": str(exc)[:300]})

        if path != "/api/chat":
            return self.send_bytes(404, {"error": "not found"})
        model = obj.get("model") or read_settings().get("default_model")
        prompt = obj.get("message")
        raw_id = obj.get("conversation_id")
        if not isinstance(model, str) or not model or len(model) > 160:
            return self.send_bytes(400, {"error": "Choose an installed model"})
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 30000:
            return self.send_bytes(400, {"error": "Message must contain 1–30000 characters"})
        if raw_id is not None and (not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id < 1):
            return self.send_bytes(400, {"error": "Invalid conversation id"})

        with db() as conn:
            if raw_id is None:
                title = prompt.strip().replace("\n", " ")[:72]
                cursor = conn.execute("INSERT INTO conversations(title) VALUES(?)", (title,))
                chat_id = cursor.lastrowid
                history: list[dict[str, str]] = []
            else:
                exists = conn.execute("SELECT id FROM conversations WHERE id=?", (raw_id,)).fetchone()
                if not exists:
                    return self.send_bytes(404, {"error": "conversation not found"})
                chat_id = raw_id
                history = [{"role": row["role"], "content": row["content"]} for row in conn.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 20", (chat_id,)).fetchall()][::-1]

        messages = history + [{"role": "user", "content": prompt.strip()}]
        try:
            reply = ollama_json("/api/chat", {"model": model, "messages": messages, "stream": False, "keep_alive": "5m"}, timeout=240)
            answer = reply.get("message", {}).get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("Ollama returned no assistant text")
        except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
            return self.send_bytes(503, {"error": f"Model request failed: {str(exc)[:300]}"})

        with db() as conn:
            conn.execute("INSERT INTO messages(conversation_id,role,content,model) VALUES(?,?,?,?)", (chat_id, "user", prompt.strip(), model))
            conn.execute("INSERT INTO messages(conversation_id,role,content,model) VALUES(?,?,?,?)", (chat_id, "assistant", answer, model))
            conn.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (chat_id,))
        return self.send_bytes(200, {"conversation_id": chat_id, "model": model, "answer": answer})


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Serve Fenrir Doctor on the local machine only.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"} or not 1024 <= args.port <= 65535:
        parser.error("Fenrir Doctor must bind to loopback on an unprivileged port")
    migrate_legacy_data()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    start_wallpaper_discovery_scheduler()
    print(f"Fenrir Doctor listening on http://{args.host}:{args.port} (loopback only)", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        DISCOVERY_SCHEDULER_STOP.set()
        stop_wallpaper_rights_review_studio()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
