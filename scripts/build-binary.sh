#!/bin/bash
# ============================================================
# Terry Single-Binary Build Script
# Uses PyInstaller to create a standalone executable
# Output: dist/terry (Linux/macOS) or dist/terry.exe (Windows)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

BINARY_NAME="terry"
VERSION=$(python3 -c "from terry import __version__; print(__version__)")
OUTPUT_DIR="dist/binary"
mkdir -p "$OUTPUT_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Terry Single-Binary Build v$VERSION                         ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Dependencies ──────────────────────────────────────────
echo ""
echo "━━━ Checking PyInstaller ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pip3 install pyinstaller --break-system-packages -q 2>/dev/null || pip install pyinstaller -q
echo "  ✅ PyInstaller ready"

# ── Data files ───────────────────────────────────────────
# WebUI static files and locale
DATA_ARGS=""
for data_dir in "terry/webui/static" "terry/locale" "skills"; do
    if [ -d "$data_dir" ]; then
        DATA_ARGS="$DATA_ARGS --add-data=$data_dir:$(echo $data_dir | tr '/' '.')"
        echo "  📦 $data_dir"
    fi
done

# ── Hidden imports ───────────────────────────────────────
# Auto-discover all Terry modules for hidden imports
HIDDEN_ARGS=""
for pyfile in $(find terry -name "*.py" ! -path "*__pycache__*"); do
    modpath=$(echo "$pyfile" | sed 's|/|.|g' | sed 's|\.py$||')
    HIDDEN_ARGS="$HIDDEN_ARGS --hidden-import=$modpath"
done

# ── Collect all Python files ──────────────────────────────
COLLECT_ARGS=""
for pkg in terry skills; do
    if [ -d "$pkg" ]; then
        COLLECT_ARGS="$COLLECT_ARGS --collect-all=$pkg"
    fi
done

# ── Build ────────────────────────────────────────────────
echo ""
echo "━━━ Building $BINARY_NAME ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m PyInstaller \
    --name="$BINARY_NAME" \
    --onefile \
    --console \
    --clean \
    --noconfirm \
    --distpath="$OUTPUT_DIR" \
    --workpath=build/pyinstaller \
    --specpath=build \
    $DATA_ARGS \
    $HIDDEN_ARGS \
    $COLLECT_ARGS \
    terry/cli.py 2>&1 | grep -E "INFO: Building|INFO: Appending|WARNING|ERROR|Building EXE|completed" || true

# ── Verify output ────────────────────────────────────────
if [ -f "$OUTPUT_DIR/$BINARY_NAME" ]; then
    BINARY_SIZE=$(du -h "$OUTPUT_DIR/$BINARY_NAME" | cut -f1)
    echo ""
    echo "━━━ Build Complete ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ $OUTPUT_DIR/$BINARY_NAME ($BINARY_SIZE)"
    echo "  📦 Version: v$VERSION"
    "$OUTPUT_DIR/$BINARY_NAME" --version 2>/dev/null || true
else
    echo "  ❌ Build failed"
    exit 1
fi
