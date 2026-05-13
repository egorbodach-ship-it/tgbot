#!/bin/bash
# ============================================================
# deploy.sh — §6 Full-Chest Overlay Deployment
# ============================================================
# This script deploys the invisible-item technique to the server
# via Pterodactyl API. Run it on any machine with internet access.
#
# Prerequisites:
#   - curl, python3 (for URL encoding)
#   - This deploy_v6/ folder with all generated files
#
# Usage:
#   export PTERODACTYL_KEY="ptlc_xxxxx"
#   bash deploy.sh
#
# What it does:
#   1. Uploads invisible item texture (empty.png)
#   2. Uploads Oraxen item config (menu_empty.yml)
#   3. Uploads all 30 patched menu YAMLs
#   4. Runs oraxen reload all
#   5. Runs dm reload
#   6. Verifies pack regeneration
# ============================================================

set -euo pipefail

# === CONFIG ===
KEY="${PTERODACTYL_KEY:?Set PTERODACTYL_KEY env var}"
BASE="https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

upload_file() {
    local local_path="$1"
    local remote_path="$2"
    local enc
    enc=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$remote_path'))")
    
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $KEY" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@$local_path" \
        "$BASE/files/write?file=$enc")
    
    if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
        ok "Uploaded: $remote_path"
        return 0
    else
        warn "Upload $remote_path — HTTP $http_code"
        return 1
    fi
}

run_command() {
    local cmd="$1"
    curl -s -X POST \
        -H "Authorization: Bearer $KEY" \
        -H "Content-Type: application/json" \
        -d "{\"command\":\"$cmd\"}" \
        "$BASE/command" > /dev/null
    ok "Executed: $cmd"
}

read_file() {
    local remote_path="$1"
    local enc
    enc=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$remote_path'))")
    curl -sf -H "Authorization: Bearer $KEY" "$BASE/files/contents?file=$enc"
}

echo "============================================"
echo "  §6 Deploy: Invisible Items + Full Overlay"
echo "============================================"
echo ""

# --- Step 0: Verify connectivity ---
echo ">>> Step 0: Testing API connection..."
TEST=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $KEY" "$BASE/files/list?directory=%2F")
if [ "$TEST" != "200" ]; then
    err "Cannot connect to Pterodactyl API (HTTP $TEST). Check KEY and network."
fi
ok "API connection verified"
echo ""

# --- Step 1: Upload invisible texture ---
echo ">>> Step 1: Uploading invisible item texture..."
upload_file "$SCRIPT_DIR/textures/empty.png" "/plugins/Oraxen/pack/textures/items/empty.png"
echo ""

# --- Step 2: Upload Oraxen item config ---
echo ">>> Step 2: Uploading Oraxen item config (menu_empty.yml)..."
upload_file "$SCRIPT_DIR/oraxen_items/menu_empty.yml" "/plugins/Oraxen/items/menu_empty.yml"
echo ""

# --- Step 3: Upload patched menu YAMLs ---
echo ">>> Step 3: Uploading 30 patched menu YAMLs..."
MENU_DIR="$SCRIPT_DIR/patched_menus"
SUCCESS=0
FAIL=0

for f in "$MENU_DIR"/*.yml; do
    fname=$(basename "$f")
    # Convert filename to server path:
    #   menu__xxx.yml  → /plugins/DeluxeMenus/menu/xxx.yml
    #   shop__xxx.yml  → /plugins/DeluxeMenus/shop/xxx.yml
    if [[ "$fname" == menu__* ]]; then
        remote_name="${fname#menu__}"
        remote_path="/plugins/DeluxeMenus/menu/$remote_name"
    elif [[ "$fname" == shop__* ]]; then
        remote_name="${fname#shop__}"
        remote_path="/plugins/DeluxeMenus/shop/$remote_name"
    else
        warn "Unknown prefix: $fname — skipping"
        continue
    fi
    
    if upload_file "$f" "$remote_path"; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "  Uploaded: $SUCCESS, Failed: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    warn "Some uploads failed. Check above for details."
    read -p "Continue with reload? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        err "Aborted by user."
    fi
fi

# --- Step 4: Reload Oraxen ---
echo ">>> Step 4: Reloading Oraxen (regenerates pack)..."
run_command "oraxen reload all"
echo "  Waiting 10s for pack generation..."
sleep 10
echo ""

# --- Step 5: Reload DeluxeMenus ---
echo ">>> Step 5: Reloading DeluxeMenus..."
run_command "dm reload"
sleep 3
echo ""

# --- Step 6: Verify ---
echo ">>> Step 6: Verification..."
echo "  Reading server.properties for new pack hash..."
PROPS=$(read_file "/server.properties" 2>/dev/null || echo "")
if echo "$PROPS" | grep -q "resource-pack="; then
    PACK_URL=$(echo "$PROPS" | grep "resource-pack=" | head -1)
    ok "Pack URL: $PACK_URL"
else
    warn "Could not read server.properties (non-critical — Oraxen handles pack delivery)"
fi

echo ""
echo "  Checking if menu_empty item was registered..."
LOG=$(read_file "/logs/latest.log" 2>/dev/null || echo "")
if echo "$LOG" | grep -qi "menu_empty"; then
    ok "menu_empty found in logs"
elif echo "$LOG" | grep -qi "error.*menu_empty"; then
    warn "Errors related to menu_empty in logs!"
else
    ok "No errors detected (item likely loaded fine)"
fi

echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Join the server as Devesuch"
echo "  2. Run: /oraxen pack send Devesuch"
echo "  3. Open /menu — you should see the full overlay"
echo "  4. Check that placed chests still look vanilla"
echo ""
echo "If the overlay doesn't cover the full chest:"
echo "  - The current PNGs + ascent:13 render in the title bar"
echo "  - With invisible items, the slot bevels are now transparent"
echo "  - If you still see grey slots, the invisible item isn't"
echo "    loading — run: /oraxen pack send Devesuch"
echo "  - Check /plugins/Oraxen/pack/ for items/empty.png"
echo ""
echo "Rollback:"
echo "  Upload files from backups/menu_yamls_pre_bulk/ back to"
echo "  /plugins/DeluxeMenus/menu/ and /shop/, then dm reload"
echo ""
