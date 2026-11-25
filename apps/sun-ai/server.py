#!/usr/bin/env python3
"""Sun AI: local-only dashboard and Ollama bridge using the Python standard library."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
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
STATE = STATE_HOME / "sun-ai"
DB = STATE / "history.sqlite3"
SETTINGS_FILE = CONFIG_HOME / "sun-ai" / "settings.json"
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
    return {"default_model": "", "weather": {"location": "", "latitude": None, "longitude": None}}


def read_settings() -> dict[str, Any]:
    try:
        raw = strict_json(SETTINGS_FILE.read_bytes())
        if not isinstance(raw, dict):
            raise ValueError("settings must be an object")
        settings = default_settings()
        model = raw.get("default_model", "")
        if isinstance(model, str) and len(model) <= 160:
            settings["default_model"] = model
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
        headers={"User-Agent": "SunAI/0.2 (local desktop weather panel)"},
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


class Handler(BaseHTTPRequestHandler):
    server_version = "SunAI/0.2"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log prompt, response, or request-body content.
        print(f"Sun AI: {self.address_string()} {fmt % args}")

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
            settings = {"default_model": model.strip(), "weather": {"location": location.strip(), "latitude": latitude, "longitude": longitude}}
            atomic_json(SETTINGS_FILE, settings)
            return self.send_bytes(200, {"saved": True, **settings})

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

    parser = argparse.ArgumentParser(description="Serve Sun AI on the local machine only.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"} or not 1024 <= args.port <= 65535:
        parser.error("Sun AI must bind to loopback on an unprivileged port")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"Sun AI listening on http://{args.host}:{args.port} (loopback only)", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
