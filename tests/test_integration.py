"""Integration tests — full mobile boilerplate workflow."""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import (
    TelemetryQueue,
    GlobalStore,
    StackNavigator,
    HomeScreen,
    SettingsScreen,
    get_theme,
    make_styles,
    auto_flush_loop,
)
from lambda_handler import lambda_handler, _extract_events
from app.main import app


class TestIntegrationTelemetry:
    """Integration tests for telemetry pipeline."""

    async def test_telemetry_queue_workflow(self):
        """Full telemetry workflow: log → flush → verify."""
        tq = TelemetryQueue()

        # Log events
        tq.log_event("app_start", {"version": "1.0.0"})
        tq.log_event("screen_view", {"screen": "Home"})
        tq.log_event("button_click", {"button": "save"})

        assert tq.queue_size == 3
        assert not tq.is_empty

        # Flush
        result = await tq.flush()
        assert result is True
        assert tq.queue_size == 0
        assert tq.is_empty

    async def test_telemetry_max_queue(self):
        """Test max queue cap (256 events)."""
        tq = TelemetryQueue()

        # Fill queue to max
        for i in range(TelemetryQueue.MAX_QUEUE + 10):
            tq.log_event("test", {"i": i})

        assert tq.queue_size == TelemetryQueue.MAX_QUEUE

    async def test_telemetry_concurrent_flush(self):
        """Concurrent flush operations are safe."""
        tq = TelemetryQueue()
        tq.log_event("test", {"data": "1"})

        # Multiple concurrent flushes
        results = await asyncio.gather(
            tq.flush(),
            tq.flush(),
            tq.flush(),
        )

        # At least one should succeed
        assert any(results)

    def test_telemetry_error_logging(self):
        """Error logging creates error events."""
        tq = TelemetryQueue()
        tq.log_error("test_error", "Traceback: simulated error")

        assert tq.queue_size == 1
        # Error events use special event type
        assert tq._queue[0]["event_type"] == "error.test_error"


class TestIntegrationNavigation:
    """Integration tests for navigation + store."""

    def test_navigator_store_integration(self):
        """Navigator works with global store."""
        store = GlobalStore()
        screens = {
            "Home": HomeScreen(store),
            "Settings": SettingsScreen(store),
        }
        nav = StackNavigator(screens)

        assert nav.current == "Home"
        assert nav.depth == 1

        # Navigate to settings
        nav.navigate("Settings")
        assert nav.current == "Settings"
        assert nav.depth == 2

        # Go back
        nav.go_back()
        assert nav.current == "Home"
        assert nav.depth == 1

    def test_deep_link_integration(self):
        """Deep linking works with navigator."""
        store = GlobalStore()
        screens = {
            "Home": HomeScreen(store),
            "Settings": SettingsScreen(store),
        }
        nav = StackNavigator(screens)

        # Deep link to settings with tab param
        result = nav.deep_link("settings?tab=notifications")
        assert result is True
        assert nav.current == "Settings"
        assert nav.depth == 2

    def test_invalid_screen_navigation(self):
        """Invalid screen name returns False."""
        store = GlobalStore()
        screens = {"Home": HomeScreen(store)}
        nav = StackNavigator(screens)

        result = nav.navigate("NonExistent")
        assert result is False
        assert nav.current == "Home"

    def test_go_back_from_home(self):
        """Cannot go back from home."""
        store = GlobalStore()
        screens = {"Home": HomeScreen(store)}
        nav = StackNavigator(screens)

        result = nav.go_back()
        assert result is False
        assert nav.current == "Home"

    def test_go_home_resets(self):
        """go_home resets to initial screen."""
        store = GlobalStore()
        screens = {
            "Home": HomeScreen(store),
            "Settings": SettingsScreen(store),
        }
        nav = StackNavigator(screens)

        nav.navigate("Settings")
        nav.go_home()

        assert nav.current == "Home"
        assert nav.depth == 1


class TestIntegrationStore:
    """Integration tests for global store."""

    def test_store_subscription(self):
        """Store subscriptions work correctly."""
        store = GlobalStore()
        changes = []

        store.subscribe(lambda k, o, n: changes.append((k, o, n)))
        store.set("theme", "light")
        store.set("theme", "dark")

        assert len(changes) == 2
        assert changes[0] == ("theme", "dark", "light")
        assert changes[1] == ("theme", "light", "dark")

    def test_store_bulk_set(self):
        """Bulk set triggers multiple notifications."""
        store = GlobalStore()
        changes = []

        store.subscribe(lambda k, o, n: changes.append(k))
        store.bulk_set({"theme": "light", "notifications_enabled": False})

        assert "theme" in changes
        assert "notifications_enabled" in changes

    def test_store_telemetry_integration(self):
        """Store telemetry property works."""
        store = GlobalStore()
        telemetry = store.telemetry

        telemetry.log_event("test", {"data": "1"})
        assert telemetry.queue_size == 1

    def test_store_unsubscribe(self):
        """Unsubscribe removes callback."""
        store = GlobalStore()
        changes = []

        callback = lambda k, o, n: changes.append(k)
        store.subscribe(callback)
        store.set("theme", "light")

        assert len(changes) == 1

        store.unsubscribe(callback)
        store.set("theme", "dark")

        assert len(changes) == 1  # No new change


class TestIntegrationTheme:
    """Integration tests for theme engine."""

    def test_get_theme_returns_copy(self):
        """get_theme returns a copy."""
        theme1 = get_theme("dark")
        theme2 = get_theme("dark")

        theme1["bg"] = "#000000"
        assert theme2["bg"] != "#000000"  # Should not be modified

    def test_get_theme_default(self):
        """Default theme is dark."""
        theme = get_theme()
        assert theme["bg"] == "#0a0a0a"

    def test_get_theme_invalid(self):
        """Invalid theme name returns dark."""
        theme = get_theme("nonexistent")
        assert theme["bg"] == "#0a0a0a"

    def test_make_styles_dark(self):
        """Dark theme styles are correct."""
        styles = make_styles("dark")
        assert styles["dashboard"]["background-color"] == "#0a0a0a"
        assert styles["header"]["color"] == "#00ff88"

    def test_make_styles_light(self):
        """Light theme styles are correct."""
        styles = make_styles("light")
        assert styles["dashboard"]["background-color"] == "#f5f5f5"
        assert styles["header"]["color"] == "#006644"

    def test_make_styles_midnight(self):
        """Midnight theme styles are correct."""
        styles = make_styles("midnight")
        assert styles["dashboard"]["background-color"] == "#050510"
        assert styles["header"]["color"] == "#bb88ff"


class TestIntegrationLambda:
    """Integration tests for Lambda handler."""

    def test_lambda_handler_empty(self):
        """Lambda handler with empty event."""
        result = lambda_handler({})
        assert result["statusCode"] == 200

    def test_lambda_handler_single(self):
        """Lambda handler with single event."""
        import json
        event = {
            "body": json.dumps({
                "device_id": "d1",
                "event_type": "test",
                "payload": {},
            }),
        }
        result = lambda_handler(event)
        assert result["statusCode"] == 200

    def test_lambda_handler_batch(self):
        """Lambda handler with batch events."""
        import json
        events = [
            {"device_id": "d1", "event_type": "test", "payload": {}},
            {"device_id": "d2", "event_type": "test", "payload": {}},
        ]
        event = {"body": json.dumps({"events": events})}
        result = lambda_handler(event)
        assert result["statusCode"] == 200


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""

    async def test_full_mobile_workflow(self):
        """Full workflow: navigate → log → flush."""
        store = GlobalStore()
        nav = StackNavigator({
            "Home": HomeScreen(store),
            "Settings": SettingsScreen(store),
        })

        # Start at home
        assert nav.current == "Home"

        # Navigate to settings
        nav.navigate("Settings")
        assert nav.current == "Settings"

        # Log telemetry
        store.telemetry.log_event("screen_view", {"screen": "Settings"})
        store.telemetry.log_event("button_click", {"button": "save"})

        assert store.telemetry.queue_size == 2

        # Flush
        result = await store.telemetry.flush()
        assert result is True
        assert store.telemetry.queue_size == 0

    def test_full_app_bootstrap(self):
        """Full app bootstrap with all components."""
        store = GlobalStore()
        nav = StackNavigator({
            "Home": HomeScreen(store),
            "Settings": SettingsScreen(store),
        })

        # Verify all components are connected
        assert nav.current == "Home"
        assert store.get("theme") == "dark"
        assert store.telemetry.is_empty

        # Trigger telemetry
        store.telemetry.log_event("app_start", {"version": "1.0.0"})
        assert not store.telemetry.is_empty

        # Change theme via store
        store.set("theme", "light")
        assert store.get("theme") == "light"

        # Navigate and log
        nav.navigate("Settings")
        store.telemetry.log_event("screen_view", {"screen": "Settings"})

        assert nav.current == "Settings"
        assert store.telemetry.queue_size == 2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
