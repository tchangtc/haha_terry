# Terry Mobile App — Build Guide

## Android APK (TWA — Trusted Web Activity)

Converts the existing PWA into a native Android APK publishable on Google Play.

### Prerequisites
- Node.js 18+
- Android SDK (or Android Studio)
- Java JDK 17+

### Build Steps

```bash
# 1. Install Bubblewrap
npm install -g @bubblewrap/cli

# 2. Initialize TWA project
bubblewrap init --manifest=https://YOUR_SERVER/terry/webui/static/manifest.json

# 3. Build APK
bubblewrap build

# Output: app-release-signed.apk (~3-5 MB)
```

### Install directly (without Google Play)
```bash
# Copy APK to phone and install
adb install app-release-signed.apk
```

### Publish to Google Play
1. Create app at play.google.com/console
2. Upload `app-release-signed.apk`
3. Fill store listing
4. Submit for review

---

## iOS App (WKWebView Wrapper)

Minimal native iOS app that wraps the Terry WebUI in a WKWebView.

### 1. Open Xcode → New Project → iOS App
- Name: Terry
- Interface: SwiftUI
- Language: Swift

### 2. Replace ContentView.swift:

```swift
import SwiftUI
import WebKit

struct ContentView: View {
    var body: some View {
        WebView(url: URL(string: "http://127.0.0.1:8670")!)
    }
}

struct WebView: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        let view = WKWebView(frame: .zero, configuration: config)
        view.load(URLRequest(url: url))
        return view
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
```

### 3. Add App Transport Security exception to Info.plist:
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
```

### 4. Build → Archive → Distribute to App Store

---

## PWA (No Build Required — Already Works)

Open `http://YOUR_SERVER:8670` in mobile browser → Share → Add to Home Screen.
Works on both Android (Chrome) and iOS (Safari) without any build step.
