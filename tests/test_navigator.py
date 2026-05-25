"""
PROJ-07 – Stack Navigator Tests
"""
import pytest
from main import StackNavigator, GlobalStore, HomeScreen, SettingsScreen


@pytest.fixture
def store():
    return GlobalStore()


@pytest.fixture
def nav(store):
    return StackNavigator({
        "Home": HomeScreen(store),
        "Settings": SettingsScreen(store),
    })


class TestNavigate:
    def test_initial(self, nav):
        assert nav.current == "Home"
        assert nav.depth == 1

    def test_navigate_pushes(self, nav):
        nav.navigate("Settings")
        assert nav.current == "Settings"
        assert nav.depth == 2

    def test_navigate_unknown_returns_false(self, nav):
        assert nav.navigate("NonExistent") is False
        assert nav.current == "Home"

    def test_replace(self, nav):
        """replace swaps top-of-stack; depth stays the same."""
        nav.navigate("Settings")
        assert nav.depth == 2
        nav.replace("Home")
        assert nav.current == "Home"
        assert nav.depth == 2  # depth unchanged

    def test_replace_unknown(self, nav):
        assert nav.replace("Foo") is False


class TestGoBack:
    def test_back(self, nav):
        nav.navigate("Settings")
        nav.go_back()
        assert nav.current == "Home"

    def test_back_at_root(self, nav):
        assert nav.go_back() is False
        assert nav.current == "Home"


class TestGoHome:
    def test_reset(self, nav):
        nav.navigate("Settings")
        nav.go_home()
        assert nav.current == "Home"
        assert nav.depth == 1


class TestDeepLink:
    def test_basic(self, nav):
        assert nav.deep_link("settings") is True
        assert nav.current == "Settings"

    def test_with_query(self, nav):
        assert nav.deep_link("settings?tab=notif") is True
        assert nav.current == "Settings"

    def test_slash_prefix(self, nav):
        assert nav.deep_link("/settings") is True

    def test_unknown(self, nav):
        assert nav.deep_link("unknown_screen") is False


class TestIsAt:
    def test_true(self, nav):
        assert nav.is_at("Home") is True
        assert nav.is_at("Settings") is False

    def test_after_nav(self, nav):
        nav.navigate("Settings")
        assert nav.is_at("Settings") is True
