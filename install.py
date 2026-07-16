#!/usr/bin/env python3
"""
Deploy & (re-)start a local JS script on a Shelly Gen2/Gen3 device via die
lokale HTTP-RPC-API. Idempotent: ein vorhandenes Script mit gleichem Namen
wird zuvor gestoppt und gelöscht.

Benoetigt: pip install requests
"""

import sys
import requests

# ---- Konfiguration -------------------------------------------------------
SHELLY_IP = "192.168.1.50"                 # anpassen
SCRIPT_NAME = "ChargeLimiter"
SCRIPT_FILE = "shelly_charge_limiter.js"   # lokale Datei mit dem JS-Code
CHUNK_SIZE = 1024                          # Bytes pro Script.PutCode-Aufruf

# Falls "Restrict login" im Shelly aktiviert ist:
AUTH = None  # z.B. ("admin", "DEIN_PASSWORT")
# ---------------------------------------------------------------------------


def rpc(base, method, payload=None):
    """Ruft eine Shelly-RPC-Methode per POST auf und gibt das JSON zurueck."""
    resp = requests.post(f"{base}/{method}", json=payload or {}, auth=AUTH, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def find_script_id(base, name):
    result = rpc(base, "Script.List")
    for script in result.get("scripts", []):
        if script.get("name") == name:
            return script["id"]
    return None


def delete_existing(base, script_id):
    rpc(base, "Script.Stop", {"id": script_id})
    rpc(base, "Script.Delete", {"id": script_id})
    print(f"Altes Script (id={script_id}) entfernt")


def create_script(base, name):
    result = rpc(base, "Script.Create", {"name": name})
    return result["id"]


def upload_code(base, script_id, code):
    offset = 0
    first = True
    while offset < len(code):
        chunk = code[offset:offset + CHUNK_SIZE]
        rpc(base, "Script.PutCode", {
            "id": script_id,
            "code": chunk,
            "append": not first,
        })
        offset += CHUNK_SIZE
        first = False
    print(f"Code hochgeladen ({len(code)} Zeichen)")


def enable_and_start(base, script_id):
    rpc(base, "Script.SetConfig", {"id": script_id, "config": {"enable": True}})
    rpc(base, "Script.Start", {"id": script_id})


def main():
    base = f"http://{SHELLY_IP}/rpc"

    try:
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            code = f.read()
    except OSError as exc:
        sys.exit(f"Konnte {SCRIPT_FILE} nicht lesen: {exc}")

    existing_id = find_script_id(base, SCRIPT_NAME)
    if existing_id is not None:
        delete_existing(base, existing_id)

    new_id = create_script(base, SCRIPT_NAME)
    print(f"Neues Script angelegt: id={new_id}")

    upload_code(base, new_id, code)
    enable_and_start(base, new_id)
    print(f"Deployed & gestartet: id={new_id}")


if __name__ == "__main__":
    main()