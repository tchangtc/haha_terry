"""Terry Desktop — system tray app and native launcher.

Supports:
  - System tray icon with quick actions (macOS, Windows, Linux)
  - Opens WebUI in default browser
  - Background agent with notifications
  - Auto-start on login (optional)

Usage:
    terry desktop              # Start desktop mode (system tray + WebUI)
    terry desktop --no-tray    # WebUI only, no tray icon
    terry desktop --browser    # Open WebUI in browser without tray
"""

from __future__ import annotations

import threading
import webbrowser


def open_browser(url: str = "http://127.0.0.1:8670") -> None:
    """Open the Terry WebUI in the default browser."""
    webbrowser.open(url)


def start_system_tray(
    agent_factory=None,
    host: str = "127.0.0.1",
    port: int = 8670,
) -> None:
    """Start Terry in desktop mode with system tray icon.

    Supports macOS (via rumps), Windows/Linux (via pystray).
    Falls back to browser-only mode if no tray library is available.
    """
    from terry.webui.server import WebUIServer

    # Start WebUI server
    server = WebUIServer(agent_factory=agent_factory, host=host, port=port)
    server.start()

    tray_available = False

    # Try rumps (macOS native)
    try:
        import rumps

        class TerryTrayApp(rumps.App):
            def __init__(self):
                super().__init__("Terry", icon=None, quit_button=None)

            @rumps.clicked("Open WebUI")
            def open_webui(self, _):
                webbrowser.open(f"http://{host}:{port}")

            @rumps.clicked("🔄 New Session")
            def new_session(self, _):
                webbrowser.open(f"http://{host}:{port}")

            @rumps.clicked("Quit Terry")
            def quit_terry(self, _):
                server.stop()
                rumps.quit_application()

        tray_available = True
        TerryTrayApp().run()

    except ImportError:
        pass

    # Try pystray (cross-platform)
    if not tray_available:
        try:
            import pystray
            from PIL import Image, ImageDraw

            def create_icon():
                img = Image.new("RGB", (64, 64), "#1a1a2e")
                draw = ImageDraw.Draw(img)
                draw.ellipse([16, 16, 48, 48], fill="#00d4aa")
                return img

            def on_open():
                webbrowser.open(f"http://{host}:{port}")

            def on_quit(icon, item):
                server.stop()
                icon.stop()

            icon = pystray.Icon(
                "terry",
                create_icon(),
                "Terry AI Agent",
                menu=pystray.Menu(
                    pystray.MenuItem("Open WebUI", on_open),
                    pystray.MenuItem("Quit", on_quit),
                ),
            )

            tray_available = True
            threading.Thread(target=icon.run, daemon=True).start()
            print("🖥️  Terry Desktop running (system tray)")
            print("   Use tray icon to open WebUI or quit")
            print("   Press Ctrl+C to stop\n")

            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                icon.stop()
                server.stop()

        except ImportError:
            pass

    # Fallback: browser-only mode
    if not tray_available:
        print("🖥️  Terry Desktop (browser mode)")
        print(f"   WebUI: http://{host}:{port}")
        print("   Install 'rumps' (macOS) or 'pystray' for system tray support")
        print("   Press Ctrl+C to stop\n")
        open_browser(f"http://{host}:{port}")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
            print("Terry Desktop stopped.")


def start_browser_only(host="127.0.0.1", port=8670):
    """Quick start: server + open browser, no tray."""
    from terry.webui.server import start_webui
    return start_webui(host=host, port=port)
