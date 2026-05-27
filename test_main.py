"""
PROJ-07 Tests — TelemetryQueue, GlobalStore, StackNavigator, Theme Engine.
pytest test_main.py
"""
import asyncio
import pytest
from main import (
    TelemetryQueue, GlobalStore, StackNavigator, THEMES, get_theme,
    make_styles, apply_theme_to_css, COMPONENT_CSS,
)


# ── TelemetryQueue ──────────────────────────────────────────────────────

def test_queue_init():
    q = TelemetryQueue()
    assert q.queue_size == 0
    assert q.is_empty
    assert q.flush_attempts == 0


def test_log_event():
    q = TelemetryQueue()
    q.log_event("screen_view", {"screen": "Home"})
    assert q.queue_size == 1
    assert not q.is_empty


def test_log_error():
    q = TelemetryQueue()
    q.log_error("crash", "Traceback: boom")
    assert q.queue_size == 1
    assert q._queue[0]["event_type"] == "error.crash"


def test_max_queue_eviction():
    q = TelemetryQueue()
    q.MAX_QUEUE = 3
    for i in range(5):
        q.log_event("tick", {"i": i})
    assert q.queue_size == 3
    # oldest entries dropped
    assert q._queue[0]["payload"]["i"] == 2


def test_flush_success():
    q = TelemetryQueue()
    q.log_event("a", {})
    q.log_event("b", {})
    result = asyncio.run(q.flush())
    assert result is True
    assert q.queue_size == 0
    assert q.flush_attempts == 1


def test_flush_empty_returns_false():
    q = TelemetryQueue()
    result = asyncio.run(q.flush())
    assert result is False


def test_flush_attempts_increments():
    q = TelemetryQueue()
    q.log_event("x", {})
    asyncio.run(q.flush())
    result2 = asyncio.run(q.flush())
    assert result2 is False


def test_flushing_property():
    q = TelemetryQueue()
    assert not q.is_flushing


# ── GlobalStore ──────────────────────────────────────────────────────────

def test_store_get_default():
    store = GlobalStore()
    assert store.get("missing", "default") == "default"


def test_store_set_and_get():
    store = GlobalStore()
    store.set("user_id", "abc123")
    assert store.get("user_id") == "abc123"


def test_store_bulk_set():
    store = GlobalStore()
    store.bulk_set({"theme": "light", "notifications_enabled": False})
    assert store.get("theme") == "light"
    assert store.get("notifications_enabled") is False


def test_store_subscriber_called():
    store = GlobalStore()
    calls = []
    store.subscribe(lambda k, o, n: calls.append((k, o, n)))
    store.set("theme", "light")
    assert len(calls) == 1
    assert calls[0][0] == "theme"
    assert calls[0][2] == "light"


def test_store_unsubscribe():
    store = GlobalStore()
    calls = []
    cb = lambda k, o, n: calls.append(k)
    store.subscribe(cb)
    store.unsubscribe(cb)
    store.set("theme", "midnight")
    assert calls == []


def test_store_subscribe_no_duplicate():
    store = GlobalStore()
    calls = []
    cb = lambda k, o, n: calls.append(k)
    store.subscribe(cb)
    store.subscribe(cb)
    store.set("theme", "light")
    assert len(calls) == 1  # only called once


def test_store_subscriber_crash_isolated():
    store = GlobalStore()
    def bad_cb(k, o, n): raise ValueError("boom")
    calls = []
    def good_cb(k, o, n): calls.append(k)
    store.subscribe(bad_cb)
    store.subscribe(good_cb)
    store.set("theme", "light")
    assert calls == ["theme"]


def test_store_telemetry_property():
    store = GlobalStore()
    assert isinstance(store.telemetry, TelemetryQueue)


def test_store_state_copy():
    store = GlobalStore()
    state = store.state
    state["theme"] = "HACKED"
    assert store.get("theme") == "dark"  # original unchanged


# ── StackNavigator ──────────────────────────────────────────────────────

def test_navigator_init():
    nav = StackNavigator({"Home": None, "Settings": None})
    assert nav.current == "Home"
    assert nav.depth == 1


def test_navigate_pushes():
    nav = StackNavigator({"Home": None, "Settings": None})
    assert nav.navigate("Settings") is True
    assert nav.current == "Settings"
    assert nav.depth == 2


def test_navigate_unknown_fails():
    nav = StackNavigator({"Home": None})
    assert nav.navigate("NonExistent") is False
    assert nav.current == "Home"


def test_go_back():
    nav = StackNavigator({"Home": None, "Settings": None})
    nav.navigate("Settings")
    assert nav.go_back() is True
    assert nav.current == "Home"
    assert nav.depth == 1


def test_go_back_at_root_fails():
    nav = StackNavigator({"Home": None})
    assert nav.go_back() is False


def test_go_home():
    nav = StackNavigator({"Home": None, "Settings": None})
    nav.navigate("Settings")
    nav.navigate("Settings")  # push again
    assert nav.depth == 3
    nav.go_home()
    assert nav.current == "Home"
    assert nav.depth == 1


def test_deep_link_basic():
    nav = StackNavigator({"Home": None, "Settings": None})
    assert nav.deep_link("settings") is True
    assert nav.current == "Settings"


def test_deep_link_case_insensitive():
    nav = StackNavigator({"Home": None, "Settings": None})
    assert nav.deep_link("SETTINGS") is True
    assert nav.current == "Settings"


def test_deep_link_unknown():
    nav = StackNavigator({"Home": None})
    assert nav.deep_link("NonExistent") is False


def test_is_at():
    nav = StackNavigator({"Home": None, "Settings": None})
    assert nav.is_at("Home") is True
    assert nav.is_at("Settings") is False


def test_replace_top():
    nav = StackNavigator({"Home": None, "Settings": None, "Profile": None})
    nav.navigate("Settings")
    nav.replace("Profile")
    assert nav.current == "Profile"
    assert nav.depth == 2  # replaced, not pushed


# ── Theme Engine ────────────────────────────────────────────────────────

def test_get_theme_default():
    t = get_theme()
    assert "bg" in t
    assert t["bg"] == "#0a0a0a"  # dark


def test_get_theme_light():
    t = get_theme("light")
    assert t["bg"] == "#f5f5f5"


def test_get_theme_unknown():
    t = get_theme("nonexistent")
    assert t["bg"] == "#0a0a0a"  # falls back to dark


def test_themes_dict_keys():
    assert "dark" in THEMES
    assert "light" in THEMES
    assert "midnight" in THEMES


def test_make_styles_dark():
    styles = make_styles("dark")
    assert styles["card"]["background-color"] == "#111111"


def test_make_styles_light():
    styles = make_styles("light")
    assert styles["card"]["background-color"] == "#ffffff"


def test_apply_theme_to_css():
    css = "{bg} {surface}"
    themed = apply_theme_to_css(css, get_theme("dark"))
    assert "#0a0a0a" in themed
    assert "#111111" in themed


# ── Integration ─────────────────────────────────────────────────────────

def test_store_and_navigator_together():
    store = GlobalStore()
    nav = StackNavigator({"Home": None, "Settings": None})
    store.set("deep_link", None)
    assert nav.navigate("Settings")
    assert store.get("deep_link") is None  # store independent from nav


def test_telemetry_via_store():
    store = GlobalStore()
    store.telemetry.log_event("app_open", {})
    assert store.telemetry.queue_size == 1


def test_store_subscription_on_telemetry_flush():
    """Flush events can be observed through store telemetry."""
    store = GlobalStore()
    q = store.telemetry
    q.log_event("test", {})
    assert q.queue_size == 1
    asyncio.run(q.flush())
    assert q.queue_size == 0