#!/bin/bash
# ============================================================
# Terry Install Script
# Usage: curl -fsSL https://terry.ai/install.sh | bash
# Installs the single-binary Terry CLI
# ============================================================
set -euo pipefail

TERRY_VERSION="${TERRY_VERSION:-latest}"
INSTALL_DIR="${TERRY_INSTALL_DIR:-/usr/local/bin}"
BINARY_NAME="terry"

# ── Detect platform ──────────────────────────────────────
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
    x86_64|amd64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "❌ Unsupported architecture: $ARCH"; exit 1 ;;
esac

case "$OS" in
    linux|darwin) ;;
    mingw*|msys*|cygwin*) OS="windows" ;;
    *) echo "❌ Unsupported OS: $OS"; exit 1 ;;
esac

# ── Download URL ─────────────────────────────────────────
BASE_URL="https://github.com/tchangtc/haha_terry/releases"
if [ "$TERRY_VERSION" = "latest" ]; then
    DOWNLOAD_URL="$BASE_URL/latest/download/${BINARY_NAME}-${OS}-${ARCH}"
else
    DOWNLOAD_URL="$BASE_URL/download/v${TERRY_VERSION}/${BINARY_NAME}-${OS}-${ARCH}"
fi

if [ "$OS" = "windows" ]; then
    DOWNLOAD_URL="${DOWNLOAD_URL}.exe"
    BINARY_NAME="${BINARY_NAME}.exe"
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Terry Installer                                        ║"
echo "║  Version: ${TERRY_VERSION}                              ║"
echo "║  Platform: ${OS}/${ARCH}                                ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Download ─────────────────────────────────────────────
echo ""
echo "━━━ Downloading Terry ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$DOWNLOAD_URL" -o "$TMP_DIR/$BINARY_NAME" || {
        echo "❌ Download failed from $DOWNLOAD_URL"
        exit 1
    }
elif command -v wget >/dev/null 2>&1; then
    wget -q "$DOWNLOAD_URL" -O "$TMP_DIR/$BINARY_NAME" || {
        echo "❌ Download failed from $DOWNLOAD_URL"
        exit 1
    }
else
    echo "❌ Need curl or wget to download"
    exit 1
fi

# ── Install ──────────────────────────────────────────────
echo "━━━ Installing to $INSTALL_DIR ━━━━━━━━━━━━━━━━━━━━━━"
chmod +x "$TMP_DIR/$BINARY_NAME"

if [ -w "$INSTALL_DIR" ]; then
    mv "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
else
    sudo mv "$TMP_DIR/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
fi

# ── Verify ────────────────────────────────────────────────
echo ""
if "$INSTALL_DIR/$BINARY_NAME" --version 2>/dev/null; then
    echo ""
    echo "✅ Terry installed successfully!"
    echo ""
    echo "   Quick start:"
    echo "     cd your-project"
    echo "     terry"
    echo ""
else
    echo "⚠️  Binary installed but --version check failed"
    echo "   Try: $INSTALL_DIR/$BINARY_NAME --help"
fi
