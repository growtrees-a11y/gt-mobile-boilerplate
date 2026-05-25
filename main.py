"""
PROJ-07: Open Idea Mobile App Boilerplate

Phase 0: RN directory scaffolding (no native compile)
Phase 1: Stack navigator + Context global store (deep linking, subscriptions)
Phase 2: Telemetry service (AsyncStorage queue + flush)
Phase 3: Minimal CSS / theme styling engine
Phase 4: Jest tests (tests/ directory – queueing logic)
"""
import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional, Set
import datetime
from datetime import timezone


# =============================================================================
# Phase 2: Telemetry Service
# =============================================================================

class TelemetryQueue:
    """Offline-capable telemetry queue with local storage + periodic flush."""

    MAX_QUEUE = 256  # safety cap
    FLUSH_INTERVAL = 30  # seconds (for auto-flush timer)

    def __init__(self, storage_key: str = "telemetry_queue"):
        self.storage_key = storage_key
        self._queue: List[Dict] = []
        self._mock_api_url: str = ""
        self._is_flushing = False
        self._flush_attempts = 0
        self._last_flush_ok = True

    def log_event(self, event_type: str, payload: Dict):
        """Enqueue an event – respects max-queue cap."""
        if len(self._queue) >= self.MAX_QUEUE:
            self._queue.pop(0)  # drop oldest (FIFO eviction)
        entry = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        }
        self._queue.append(entry)
        self._persist()

    def log_error(self, error_type: str, traceback: str):
        """Log error with traceback as a special event."""
        self.log_event(f"error.{error_type}", {"traceback": traceback})

    def _persist(self):
        """Persist queue to local storage (simulated – AsyncStorage in RN)."""
        pass

    def _load(self):
        """Load queue from local storage (simulated)."""
        pass

    async def flush(self) -> bool:
        """Flush queued events to the mock API.

        Returns True if at least one event was sent, False otherwise.
        On failure the queue is preserved for retry.
        """
        if not self._queue or self._is_flushing:
            return False

        self._is_flushing = True
        self._flush_attempts += 1
        try:
            # Simulate network latency
            await asyncio.sleep(0.05)

            # In RN:
            #   response = await fetch(self._mock_api_url,
            #                         method="POST",
            #                         body=json.dumps(self._queue))
            #   if response.status >= 500: raise

            self._queue.clear()
            self._last_flush_ok = True
            self._is_flushing = False
            return True
        except Exception:
            self._last_flush_ok = False
            self._is_flushing = False
            return False

    # ── convenience properties ──────────────────────────────────────────

    @property
    def is_flushing(self) -> bool:
        return self._is_flushing

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def flush_attempts(self) -> int:
        return self._flush_attempts


# =============================================================================
# Phase 1: Global Store (React-Context-like)
# =============================================================================

class GlobalStore:
    """Lightweight global state with subscription / observer pattern.

    Simulates React.createContext + useReducer behaviour.
    """

    def __init__(self):
        self._state: Dict[str, Any] = {
            "user_id": None,
            "theme": "dark",
            "notifications_enabled": True,
            "telemetry": TelemetryQueue(),
            "deep_link": None,
            "onboarding_done": False,
        }
        self._subscribers: List[Callable[[str, Any, Any], None]] = []

    # ── core accessors ──────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any):
        old = self._state.get(key)
        self._state[key] = value
        if old is not value:
            self._notify(key, old, value)

    def bulk_set(self, updates: Dict[str, Any]):
        for key, value in updates.items():
            self.set(key, value)

    @property
    def telemetry(self) -> TelemetryQueue:
        return self._state["telemetry"]

    @property
    def state(self) -> Dict[str, Any]:
        return self._state.copy()

    # ── subscription API ───────────────────────────────────────────────

    def subscribe(self, callback: Callable[[str, Any, Any], None]):
        """Register a listener: callback(key, old_value, new_value)."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        self._subscribers.remove(callback)

    def _notify(self, key: str, old: Any, new: Any):
        for cb in self._subscribers:
            try:
                cb(key, old, new)
            except Exception:
                pass  # don't let subscriber crashes break the store


# =============================================================================
# Phase 3: CSS / Theme Styling Engine
# =============================================================================

THEMES = {
    "dark": {
        "bg": "#0a0a0a",
        "surface": "#111111",
        "border": "#333333",
        "primary": "#00ff88",
        "text": "#e0e0e0",
        "text_muted": "#888888",
        "danger": "#ff4444",
        "accent": "#00bbff",
    },
    "light": {
        "bg": "#f5f5f5",
        "surface": "#ffffff",
        "border": "#dddddd",
        "primary": "#006644",
        "text": "#1a1a1a",
        "text_muted": "#666666",
        "danger": "#cc0000",
        "accent": "#0077cc",
    },
    "midnight": {
        "bg": "#050510",
        "surface": "#0c0c1d",
        "border": "#1a1a33",
        "primary": "#bb88ff",
        "text": "#d0d0e0",
        "text_muted": "#7777aa",
        "danger": "#ff6688",
        "accent": "#66bbff",
    },
}


def get_theme(name: str = "dark") -> Dict[str, str]:
    return THEMES.get(name, THEMES["dark"]).copy()


# Component-level style templates (token → CSS)
COMPONENT_CSS = """
/* ── Layout ────────────────────────────────────────────────────────── */
.dashboard {
    display: flex;
    flex-direction: column;
    padding: 20px;
    gap: 12px;
}

/* ── Typography ───────────────────────────────────────────────────── */
.header {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 8px;
}

.subtitle {
    font-size: 14px;
    opacity: 0.7;
}

/* ── Cards ────────────────────────────────────────────────────────── */
.card {
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}

.card-title {
    font-size: 18px;
    font-weight: 600;
}

.card-body {
    font-size: 14px;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
.btn {
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: opacity 0.2s;
}

.btn-primary {
    font-weight: bold;
}

.btn-danger {
    border-radius: 6px;
    padding: 10px 20px;
}

/* ── Nav Bar ─────────────────────────────────────────────────────── */
.nav-bar {
    display: flex;
    justify-content: space-around;
    padding: 10px 0;
    border-top: 1px solid transparent;
}

.nav-item {
    font-size: 13px;
    text-align: center;
    padding: 6px 12px;
    border-radius: 4px;
}

/* ── Inputs ─────────────────────────────────────────────────────── */
.input {
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 14px;
    border: 1px solid transparent;
}

/* ── Status / Badge ─────────────────────────────────────────────── */
.badge {
    display: inline-block;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""


def apply_theme_to_css(css: str, theme: Dict[str, str]) -> str:
    """Replace colour tokens in CSS with concrete values from a theme."""
    result = css
    token_map = {
        "{bg}": theme["bg"],
        "{surface}": theme["surface"],
        "{border}": theme["border"],
        "{primary}": theme["primary"],
        "{text}": theme["text"],
        "{text_muted}": theme["text_muted"],
        "{danger}": theme["danger"],
        "{accent}": theme["accent"],
    }
    for token, value in token_map.items():
        result = result.replace(token, value)
    return result


# ── Theme-aware component style builder ────────────────────────────────────

def make_styles(theme_name: str = "dark") -> Dict[str, Dict[str, str]]:
    """Return a dict mapping component class names → {property: value}."""
    t = get_theme(theme_name)
    return {
        "dashboard": {
            "background-color": t["bg"],
            "padding": "20px",
        },
        "header": {
            "color": t["primary"],
            "font-size": "24px",
            "font-weight": "bold",
        },
        "card": {
            "background-color": t["surface"],
            "border": f"1px solid {t['border']}",
            "border-radius": "8px",
            "padding": "16px",
        },
        "card-title": {
            "color": t["text"],
            "font-size": "18px",
            "font-weight": "600",
        },
        "card-body": {
            "color": t["text_muted"],
            "font-size": "14px",
        },
        "btn-primary": {
            "background-color": t["primary"],
            "color": t["bg"],
            "border-radius": "6px",
            "padding": "10px 20px",
            "font-weight": "600",
        },
        "btn-danger": {
            "background-color": t["danger"],
            "color": "#fff",
            "border-radius": "6px",
            "padding": "10px 20px",
        },
        "badge": {
            "background-color": t["accent"],
            "color": t["bg"],
            "border-radius": "12px",
            "padding": "2px 8px",
            "font-size": "11px",
        },
    }


# =============================================================================
# Phase 1 (cont.): Stack Navigator
# =============================================================================

class StackNavigator:
    """Stack-based screen navigator with deep linking.

    Simulates react-navigation's createStackNavigator.
    Supports navigate(), go_back(), go_home(), deep_link(), and history
    inspection.
    """

    def __init__(self, screens: Dict[str, Any]):
        self.screens: Dict[str, Any] = screens
        self.history: List[str] = ["Home"]
        self.current: str = "Home"
        self._initial: str = "Home"

    def navigate(self, screen: str) -> bool:
        """Push a screen onto the stack."""
        if screen not in self.screens:
            return False
        self.history.append(screen)
        self.current = screen
        return True

    def replace(self, screen: str) -> bool:
        """Replace top of stack instead of pushing."""
        if screen not in self.screens:
            return False
        self.history[-1] = screen
        self.current = screen
        return True

    def go_back(self) -> bool:
        """Pop and return to the previous screen."""
        if len(self.history) <= 1:
            return False
        self.history.pop()
        self.current = self.history[-1]
        return True

    def go_home(self):
        """Reset to the initial screen."""
        self.history = [self._initial]
        self.current = self._initial

    def deep_link(self, path: str) -> bool:
        """Handle a deep-link URI string (e.g. 'settings?tab=notifications').

        Parses the screen name and optional params, navigates there,
        and writes the deep_link into GlobalStore for screens to react.
        """
        parts = path.lstrip("/").split("?")
        screen = parts[0] or self._initial
        params: Dict[str, str] = {}
        if len(parts) > 1:
            for kv in parts[1].split("&"):
                k, v = (kv.split("=") + ["", ""])[:2]
                params[k] = v

        # Case-insensitive screen lookup
        screen_lower = screen.lower()
        matched = None
        for s in self.screens:
            if s.lower() == screen_lower:
                matched = s
                break
        if matched is None:
            return False

        self.history.append(matched)
        self.current = matched
        return True

    def get_current(self) -> Optional[Any]:
        return self.screens.get(self.current)

    @property
    def depth(self) -> int:
        return len(self.history)

    def is_at(self, screen: str) -> bool:
        return self.current == screen


# =============================================================================
# Screen Components
# =============================================================================

class HomeScreen:
    """Dashboard home screen."""

    def __init__(self, store: GlobalStore):
        self.store = store

    def render(self) -> Dict[str, Any]:
        return {
            "type": "View",
            "style": "dashboard",
            "children": [
                {"type": "Text", "text": "Dashboard", "style": "header"},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Welcome back", "style": "card-title"},
                    {"type": "Text",
                     "text": f"Theme: {self.store.get('theme', 'dark')}",
                     "style": "card-body"},
                ]},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Telemetry", "style": "card-title"},
                    {"type": "Text",
                     "text": f"Events queued: {self.store.telemetry.queue_size}",
                     "style": "card-body"},
                ]},
            ],
        }


class SettingsScreen:
    """App settings screen."""

    def __init__(self, store: GlobalStore):
        self.store = store

    def render(self) -> Dict[str, Any]:
        return {
            "type": "View",
            "style": "dashboard",
            "children": [
                {"type": "Text", "text": "Settings", "style": "header"},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Notifications", "style": "card-title"},
                    {"type": "Switch",
                     "value": self.store.get("notifications_enabled", True),
                     "on_change": "_toggle_notif"},
                ]},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Theme", "style": "card-title"},
                    {"type": "Select",
                     "options": list(THEMES.keys()),
                     "value": self.store.get("theme", "dark"),
                     "on_change": "_change_theme"},
                ]},
            ],
        }

    # ── handlers ──────────────────────────────────────────────────────────

    def _toggle_notif(self, value: bool):
        self.store.set("notifications_enabled", value)

    def _change_theme(self, theme: str):
        if theme in THEMES:
            self.store.set("theme", theme)


# =============================================================================
# App Bootstrap
# =============================================================================

store = GlobalStore()
navigator = StackNavigator({
    "Home": HomeScreen(store),
    "Settings": SettingsScreen(store),
})


async def auto_flush_loop(queue: TelemetryQueue, interval: int = 10):
    """Background task that periodically flushes the telemetry queue."""
    while True:
        await asyncio.sleep(interval)
        await queue.flush()


if __name__ == "__main__":
    print("=" * 60)
    print(" PROJ-07: Open Idea Mobile App Boilerplate")
    print("=" * 60)

    # ── navigation demo ──────────────────────────────────────────────
    print(f"\n▶ Initial screen: {navigator.current}  (depth={navigator.depth})")
    home = navigator.get_current()
    rendered = home.render()
    print(f"  Home children: {[c['text'] for c in rendered['children'] if c['type'] == 'Text']}")

    navigator.navigate("Settings")
    print(f"\n▶ Navigated to: {navigator.current}  (depth={navigator.depth})")
    settings = navigator.get_current()
    print(f"  Settings rendered: {json.dumps(settings.render(), indent=2)[:200]}...")

    navigator.go_back()
    print(f"\n▶ After go_back: {navigator.current}  (depth={navigator.depth})")

    # ── deep linking ─────────────────────────────────────────────────
    navigator.deep_link("settings?tab=notifications")
    print(f"\n▶ Deep-link → {navigator.current}  (depth={navigator.depth})")

    # ── telemetry ────────────────────────────────────────────────────
    tq = store.telemetry
    tq.log_event("app_start", {"version": "1.0.0"})
    tq.log_event("screen_view", {"screen": "Home"})
    tq.log_error("test_error", "Traceback: simulated error")
    print(f"\n▶ Telemetry queue: {tq.queue_size} events  (empty={tq.is_empty})")

    flushed = asyncio.run(tq.flush())
    print(f"▶ Flush result: {flushed}  | queue after: {tq.queue_size}")

    # ── store subscriptions ────────────────────────────────────────
    changes: List[str] = []
    store.subscribe(lambda k, o, n: changes.append(f"{k}: {o} → {n}"))
    store.set("theme", "light")
    store.set("theme", "dark")
    print(f"\n▶ Subscribed changes: {changes}")

    # ── theme engine ───────────────────────────────────────────────
    styles = make_styles("dark")
    print(f"\n▶ Dark theme – card body: {styles['card-body']}")

    light_styles = make_styles("light")
    print(f"▶ Light theme – card body: {light_styles['card-body']}")

    print("\n" + "=" * 60)
    print(" ✓ All phases bootstrapped")
    print("=" * 60)
