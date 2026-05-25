"""
PROJ-07: Open Idea Mobile App Boilerplate
Phase 0: RN directory scaffolding (no native compile)
Phase 1: Stack navigator + Context global store
Phase 2: Telemetry service (AsyncStorage queue + flush)
Phase 3: Minimal CSS styling
Phase 4: Jest tests (queueing logic)
"""
import asyncio
import json
import time
from typing import Dict, List, Optional
from datetime import datetime


# ── Phase 2: Telemetry Service ──────────────────────────────────────────────

class TelemetryQueue:
    """Offline-capable telemetry queue with local storage + periodic flush."""

    def __init__(self, storage_key: str = "telemetry_queue"):
        self.storage_key = storage_key
        self._queue: List[Dict] = []
        self._mock_api_url = ""
        self._is_flushing = False

    def log_event(self, event_type: str, payload: Dict):
        """Log event to async queue."""
        entry = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._queue.append(entry)
        self._persist()

    def log_error(self, error_type: str, traceback: str):
        """Log error with traceback."""
        self.log_event(f"error.{error_type}", {"traceback": traceback})

    def _persist(self):
        """Persist queue to local storage (simulated)."""
        # In RN this would be AsyncStorage.setItem(self.storage_key, json.dumps(self._queue))
        pass

    def _load(self):
        """Load queue from local storage."""
        # In RN: data = await AsyncStorage.getItem(self.storage_key)
        pass

    async def flush(self) -> bool:
        """Flush queued events to mock API."""
        if not self._queue or self._is_flushing:
            return False

        self._is_flushing = True
        try:
            # Simulate network delay
            await asyncio.sleep(0.1)

            # In RN: response = await fetch(self._mock_api_url, method="POST", body=json.dumps(self._queue))
            # For now, simulate success

            self._queue.clear()
            self._is_flushing = False
            return True
        except Exception:
            self._is_flushing = False
            return False

    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0


# ── Phase 1: Global Store (Context) ───────────────────────────────────────

class GlobalStore:
    """Lightweight global state holder (simulates React Context)."""

    def __init__(self):
        self._state: Dict = {
            "user_id": None,
            "theme": "dark",
            "notifications_enabled": True,
            "telemetry": TelemetryQueue(),
        }

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    def set(self, key: str, value):
        self._state[key] = value

    @property
    def telemetry(self) -> TelemetryQueue:
        return self._state["telemetry"]

    @property
    def state(self) -> Dict:
        return self._state.copy()


# ── Phase 3: Minimal UI styling ──────────────────────────────────────────

HOME_SCREEN_CSS = """
.dashboard {
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #0a0a0a;
}
.header {
    font-size: 24px;
    font-weight: bold;
    color: #00ff88;
    margin-bottom: 16px;
}
.card {
    background-color: #111;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}
.card-title {
    font-size: 18px;
    font-weight: 600;
    color: #e0e0e0;
}
.card-body {
    font-size: 14px;
    color: #888;
}
"""


class HomeScreen:
    """Home screen component."""

    def __init__(self, store: GlobalStore):
        self.store = store

    def render(self) -> Dict:
        return {
            "type": "View",
            "style": "dashboard",
            "children": [
                {"type": "Text", "text": "Dashboard", "style": "header"},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Welcome back", "style": "card-title"},
                    {"type": "Text", "text": "Theme: " + self.store.get("theme", "dark"), "style": "card-body"},
                ]},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Telemetry", "style": "card-title"},
                    {"type": "Text", "text": f"Events queued: {self.store.telemetry.queue_size()}", "style": "card-body"},
                ]},
            ],
        }


class SettingsScreen:
    """Settings screen component."""

    def __init__(self, store: GlobalStore):
        self.store = store

    def render(self) -> Dict:
        return {
            "type": "View",
            "style": "dashboard",
            "children": [
                {"type": "Text", "text": "Settings", "style": "header"},
                {"type": "View", "style": "card", "children": [
                    {"type": "Text", "text": "Toggle Notifications", "style": "card-title"},
                    {"type": "Switch", "value": self.store.get("notifications_enabled", True), "on_change": self._toggle_notif},
                ]},
            ],
        }

    def _toggle_notif(self, value: bool):
        self.store.set("notifications_enabled", value)


# ── Stack Navigator ─────────────────────────────────────────────────────

class StackNavigator:
    """Simple stack navigator."""

    def __init__(self, screens: Dict[str, object]):
        self.screens = screens
        self.history: List[str] = ["Home"]
        self.current = "Home"

    def navigate(self, screen: str):
        if screen in self.screens:
            self.history.append(screen)
            self.current = screen

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            self.current = self.history[-1]

    def get_current(self) -> object:
        return self.screens.get(self.current)


# ── App Bootstrap ────────────────────────────────────────────────────────

store = GlobalStore()
navigator = StackNavigator({
    "Home": HomeScreen(store),
    "Settings": SettingsScreen(store),
})


if __name__ == "__main__":
    print("PROJ-07: Open Idea Mobile App Boilerplate")
    print(f"Initial screen: {navigator.current}")
    home = navigator.get_current()
    print(f"Home rendered: {json.dumps(home.render(), indent=2)[:200]}...")

    # Test telemetry
    store.telemetry.log_event("app_start", {"version": "1.0.0"})
    store.telemetry.log_event("screen_view", {"screen": "Home"})
    store.telemetry.log_error("test_error", "Stack trace here")
    print(f"Telemetry queue: {store.telemetry.queue_size()} events")
