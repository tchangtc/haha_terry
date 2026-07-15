"""Tests for the desktop launcher (terry/desktop.py).

The system-tray path falls back to browser-only mode when neither rumps nor
pystray is importable — both are forced unimportable here, the WebUI server is
stubbed, and ``time.sleep`` raises ``KeyboardInterrupt`` to break the keep-alive
loop so the shutdown branch is exercised.
"""

from __future__ import annotations

import contextlib
import io
import sys

import terry.desktop as desktop


class TestOpenBrowser:
    def test_opens_given_url(self, monkeypatch):
        opened: list[str] = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
        desktop.open_browser("http://example:9999")
        assert opened == ["http://example:9999"]

    def test_default_url(self, monkeypatch):
        opened: list[str] = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
        desktop.open_browser()
        assert opened == ["http://127.0.0.1:8670"]


class TestStartBrowserOnly:
    def test_delegates_to_start_webui(self, monkeypatch):
        called: dict = {}

        def fake_start_webui(agent_factory=None, host="127.0.0.1", port=8670, **_kw):
            called.update(host=host, port=port)
            return "SERVER"

        monkeypatch.setattr("terry.webui.server.start_webui", fake_start_webui)
        assert desktop.start_browser_only(host="1.2.3.4", port=1234) == "SERVER"
        assert called == {"host": "1.2.3.4", "port": 1234}


class TestStartSystemTrayFallback:
    """When no tray library is available, desktop must start the server,
    open the browser, and shut down cleanly on KeyboardInterrupt."""

    def _force_no_tray(self, monkeypatch):
        # A None entry in sys.modules makes `import <name>` raise ImportError.
        monkeypatch.setitem(sys.modules, "rumps", None)
        monkeypatch.setitem(sys.modules, "pystray", None)

    def test_fallback_browser_only_shutdown(self, monkeypatch):
        self._force_no_tray(monkeypatch)

        events: list[str] = []

        class FakeServer:
            def __init__(self, *_, **__):
                pass

            def start(self):
                events.append("start")

            def stop(self):
                events.append("stop")

        monkeypatch.setattr("terry.webui.server.WebUIServer", FakeServer)

        opened: list[str] = []
        monkeypatch.setattr(desktop, "open_browser", lambda url: opened.append(url))

        def fake_sleep(_n):
            raise KeyboardInterrupt

        monkeypatch.setattr("time.sleep", fake_sleep)

        with contextlib.redirect_stdout(io.StringIO()):
            desktop.start_system_tray(host="127.0.0.1", port=8670)

        assert "start" in events
        assert "stop" in events  # server.stop() called on KeyboardInterrupt
        assert opened and "127.0.0.1:8670" in opened[0]

    def test_custom_host_port_passed_to_server_and_browser(self, monkeypatch):
        self._force_no_tray(monkeypatch)

        class FakeServer:
            def __init__(self, *_, host="", port=0, **__):
                self.host = host
                self.port = port

            def start(self):
                pass

            def stop(self):
                pass

        monkeypatch.setattr("terry.webui.server.WebUIServer", FakeServer)
        opened: list[str] = []
        monkeypatch.setattr(desktop, "open_browser", lambda url: opened.append(url))
        monkeypatch.setattr("time.sleep", lambda _n: (_ for _ in ()).throw(KeyboardInterrupt))

        with contextlib.redirect_stdout(io.StringIO()):
            desktop.start_system_tray(host="0.0.0.0", port=9000)

        assert opened == ["http://0.0.0.0:9000"]
