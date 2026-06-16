#!/usr/bin/env python3
"""
Add MC 1.21.4 support to the Oraxen-generated resource pack.

MC 1.21.4 (pack_format 46) replaced the `overrides` system in item models
with a new `items/` directory containing item model definitions that use
`range_dispatch` for custom_model_data.

This script:
1. Downloads the current pack.zip from the server
2. Updates pack.mcmeta to declare supported_formats 6..46
3. Reads existing item model overrides from models/item/*.json
4. Generates 1.21.4-style item model definitions in items/*.json
5. Re-packs and uploads the modified pack.zip
6. Triggers oraxen to re-host the pack

Run after every `oraxen reload pack` to re-apply 1.21.4 compat.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile

KEY = "ptlc_q1LTOfeHyId0pGueJl1WQMYKfK6nqXngMuqcgKRgbQd"
BASE = "https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"


def api_get_download_url(remote_path):
    enc = urllib.parse.quote(remote_path)
    url = f"{BASE}/files/download?file={enc}"
    r = subprocess.run(
        ["curl", "-sf", "--max-time", "15",
         "-H", f"Authorization: Bearer {KEY}", url],
        capture_output=True, timeout=20
    )
    data = json.loads(r.stdout)
    return data["attributes"]["url"]


def download_file(remote_path, local_path):
    dl_url = api_get_download_url(remote_path)
    subprocess.run(
        ["curl", "-sf", "--max-time", "60", "-o", local_path, dl_url],
        check=True, timeout=65
    )


def upload_file(local_path, remote_path):
    enc = urllib.parse.quote(remote_path)
    url = f"{BASE}/files/write?file={enc}"
    with open(local_path, "rb") as f:
        data = f.read()
    r = subprocess.run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
         "-X", "POST",
         "-H", f"Authorization: Bearer {KEY}",
         "-H", "Content-Type: application/octet-stream",
         "--data-binary", "@-", url],
        input=data, capture_output=True, timeout=120
    )
    code = r.stdout.decode().strip()
    return code


def run_cmd(command):
    url = f"{BASE}/command"
    subprocess.run(
        ["curl", "-sf", "-X", "POST",
         "-H", f"Authorization: Bearer {KEY}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"command": command}), url],
        capture_output=True, timeout=15
    )


def convert_overrides_to_items_model(item_name, overrides_json):
    """Convert legacy predicate overrides to 1.21.4 range_dispatch format."""
    overrides = overrides_json.get("overrides", [])

    cmd_entries = []
    for ov in overrides:
        pred = ov.get("predicate", {})
        model = ov.get("model", "")
        if "custom_model_data" in pred and len(pred) == 1:
            model_ref = model if ":" in model else f"minecraft:{model}"
            cmd_entries.append({
                "threshold": pred["custom_model_data"],
                "model": {
                    "type": "minecraft:model",
                    "model": model_ref
                }
            })

    if not cmd_entries:
        return None

    cmd_entries.sort(key=lambda e: e["threshold"])

    return {
        "model": {
            "type": "minecraft:range_dispatch",
            "property": "minecraft:custom_model_data",
            "scale": 1,
            "fallback": {
                "type": "minecraft:model",
                "model": f"minecraft:item/{item_name}"
            },
            "entries": cmd_entries
        }
    }


# build_special_model merged into convert_overrides_to_items_model above


def main():
    work_dir = tempfile.mkdtemp(prefix="pack_1214_")
    pack_zip = os.path.join(work_dir, "pack.zip")
    extract_dir = os.path.join(work_dir, "extracted")
    output_zip = os.path.join(work_dir, "pack_patched.zip")

    print("=== Step 1: Download pack.zip ===")
    download_file("/plugins/Oraxen/pack/pack.zip", pack_zip)
    print(f"  Downloaded {os.path.getsize(pack_zip)} bytes")

    print("\n=== Step 2: Extract ===")
    os.makedirs(extract_dir)
    with zipfile.ZipFile(pack_zip, "r") as zf:
        zf.extractall(extract_dir)
    print(f"  Extracted to {extract_dir}")

    print("\n=== Step 3: Update pack.mcmeta ===")
    mcmeta_path = os.path.join(extract_dir, "pack.mcmeta")
    with open(mcmeta_path, "r") as f:
        mcmeta = json.load(f)

    mcmeta["pack"]["pack_format"] = 46
    mcmeta["pack"]["supported_formats"] = {
        "min_inclusive": 6,
        "max_inclusive": 46
    }

    with open(mcmeta_path, "w") as f:
        json.dump(mcmeta, f, indent=2)
    print(f"  pack.mcmeta: {json.dumps(mcmeta['pack'])}")

    print("\n=== Step 4: Generate 1.21.4 item model definitions ===")
    items_dir = os.path.join(extract_dir, "assets", "minecraft", "items")
    os.makedirs(items_dir, exist_ok=True)

    models_item_dir = os.path.join(extract_dir, "assets", "minecraft",
                                   "models", "item")
    if not os.path.isdir(models_item_dir):
        print("  ERROR: models/item/ not found in pack")
        sys.exit(1)

    count = 0
    for fname in os.listdir(models_item_dir):
        if not fname.endswith(".json"):
            continue
        item_name = fname[:-5]  # remove .json
        model_path = os.path.join(models_item_dir, fname)
        with open(model_path, "r") as f:
            model_data = json.load(f)

        if "overrides" not in model_data:
            continue

        items_model = convert_overrides_to_items_model(item_name, model_data)
        if items_model is None:
            continue

        out_path = os.path.join(items_dir, fname)
        with open(out_path, "w") as f:
            json.dump(items_model, f, indent=2)
        n_entries = len(items_model["model"]["entries"])
        print(f"  {item_name}: {n_entries} entries")
        count += 1

    print(f"  Generated {count} item model definitions")

    print("\n=== Step 5: Re-pack ===")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for root, dirs, files in os.walk(extract_dir):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, extract_dir)
                zf.write(fpath, arcname)

    orig_size = os.path.getsize(pack_zip)
    new_size = os.path.getsize(output_zip)
    print(f"  Original: {orig_size} bytes")
    print(f"  Patched:  {new_size} bytes")

    print("\n=== Step 6: Upload patched pack.zip ===")
    code = upload_file(output_zip, "/plugins/Oraxen/pack/pack.zip")
    print(f"  Upload: {code}")
    if code != "204":
        print("  ERROR: Upload failed!")
        sys.exit(1)

    # Also upload the updated pack.mcmeta separately so Oraxen sees it
    code = upload_file(mcmeta_path, "/plugins/Oraxen/pack/pack.mcmeta")
    print(f"  pack.mcmeta upload: {code}")

    print("\n=== Step 7: Trigger pack re-host ===")
    # Use oraxen reload to update the pack URL (hash changes)
    run_cmd("oraxen reload pack")
    print("  Sent: oraxen reload pack")
    print("  (Wait ~10 seconds for Oraxen to re-upload)")

    print("\n=== Step 8: Cleanup ===")
    shutil.rmtree(work_dir)
    print("  Done!")

    print("\n=== Summary ===")
    print(f"  pack_format: 46 (supported: 6..46)")
    print(f"  Added {count} item model definitions for 1.21.4+")
    print("  1.16.5 clients: use legacy overrides (unchanged)")
    print("  1.21.4 clients: use items/ definitions (new)")
    print("\n  NOTE: Run this script again after every `oraxen reload pack`")


if __name__ == "__main__":
    main()
