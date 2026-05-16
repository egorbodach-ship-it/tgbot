#!/bin/bash
# Deploy 28 PNGs to Pterodactyl server, reload Oraxen pack and DM menus
set -e

API_KEY="ptlc_q1LTOfeHyId0pGueJl1WQMYKfK6nqXngMuqcgKRgbQd"
SERVER_ID="944c2567"
HOST="https://mgr.hosting-minecraft.pro"
TEX_DIR="$1"
[ -z "$TEX_DIR" ] && { echo "Usage: $0 <texture_dir>"; exit 1; }

REMOTE_BASE="/plugins/Oraxen/pack/textures/font/menus"

echo "=== Uploading PNGs from $TEX_DIR ==="
cnt=0
fail=0
for f in "$TEX_DIR"/*.png; do
    name=$(basename "$f")
    enc_path=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote('${REMOTE_BASE}/$name', safe=''))")
    http_code=$(curl -sS -o /tmp/upload_resp.txt -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@$f" \
        "$HOST/api/client/servers/$SERVER_ID/files/write?file=${enc_path}")
    if [ "$http_code" = "204" ]; then
        cnt=$((cnt+1))
        printf "  [OK]   %s\n" "$name"
    else
        fail=$((fail+1))
        printf "  [FAIL %s] %s : %s\n" "$http_code" "$name" "$(cat /tmp/upload_resp.txt)"
    fi
done
echo "=== Uploaded: $cnt   Failed: $fail ==="
[ $fail -gt 0 ] && exit 1

echo
echo "=== /oraxen reload pack ==="
curl -sS -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d '{"command":"oraxen reload pack"}' \
    "$HOST/api/client/servers/$SERVER_ID/command"
echo

sleep 3

echo "=== /dm reload ==="
curl -sS -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d '{"command":"dm reload"}' \
    "$HOST/api/client/servers/$SERVER_ID/command"
echo

echo "Done. Tell the player to press F3+T to reload the resource pack."
