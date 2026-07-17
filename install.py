#!/usr/bin/env python3
"""Deploy and (re-)start a local JS script on a Shelly Gen2/Gen3 device.

Uses the device's local HTTP RPC API. Idempotent: an existing script with
the same name is stopped and deleted before the new one is deployed.

Requires: pip install click httpx2
"""

from typing import Any

import click
import httpx2

# ---- Configuration --------------------------------------------------------
DEFAULT_SHELLY_IP = "192.168.33.1"
DEFAULT_SCRIPT_NAME = "ChargeLimiter"
SCRIPT_FILE = "shelly_charge_limiter.js"  # local file containing the JS code
CHUNK_SIZE = 1024  # bytes per Script.PutCode call

# If "Restrict login" is enabled on the Shelly:
AUTH: tuple[str, str] | None = None  # e.g. ("admin", "YOUR_PASSWORD")
# ---------------------------------------------------------------------------


def rpc(
    base: str, method: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Call a Shelly RPC method via POST and return the parsed JSON response.

    :param base: Base URL of the device's RPC endpoint, e.g. ``http://<ip>/rpc``.
    :param method: Name of the RPC method, e.g. ``Script.List``.
    :param payload: Parameters for the RPC method; defaults to an empty dict.
    :return: The parsed JSON response, or an empty dict if the body is empty.
    :raises httpx2.HTTPError: If the request fails or returns an error status.
    """
    resp = httpx2.post(f"{base}/{method}", json=payload or {}, auth=AUTH, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def find_script_id(base: str, name: str) -> int | None:
    """Look up a script by name on the device.

    :param base: Base URL of the device's RPC endpoint.
    :param name: Name of the script to look for.
    :return: The script id, or None if no script with that name exists.
    """
    result = rpc(base, "Script.List")
    for script in result.get("scripts", []):
        if script.get("name") == name:
            return script["id"]
    return None


def delete_existing(base: str, script_id: int) -> None:
    """Stop and delete the script with the given id.

    :param base: Base URL of the device's RPC endpoint.
    :param script_id: Id of the script to remove.
    """
    rpc(base, "Script.Stop", {"id": script_id})
    rpc(base, "Script.Delete", {"id": script_id})
    click.echo(f"Removed old script (id={script_id})")


def create_script(base: str, name: str) -> int:
    """Create an empty script on the device.

    :param base: Base URL of the device's RPC endpoint.
    :param name: Name for the new script.
    :return: The id of the newly created script.
    """
    result = rpc(base, "Script.Create", {"name": name})
    return result["id"]


def upload_code(base: str, script_id: int, code: str) -> None:
    """Upload the script code in chunks via Script.PutCode.

    :param base: Base URL of the device's RPC endpoint.
    :param script_id: Id of the script to upload the code to.
    :param code: Complete JS source code to upload.
    """
    offset = 0
    first = True
    while offset < len(code):
        chunk = code[offset : offset + CHUNK_SIZE]
        rpc(
            base,
            "Script.PutCode",
            {
                "id": script_id,
                "code": chunk,
                "append": not first,
            },
        )
        offset += CHUNK_SIZE
        first = False
    click.echo(f"Uploaded code ({len(code)} characters)")


def enable_and_start(base: str, script_id: int) -> None:
    """Enable autostart for the script and start it.

    :param base: Base URL of the device's RPC endpoint.
    :param script_id: Id of the script to enable and start.
    """
    rpc(base, "Script.SetConfig", {"id": script_id, "config": {"enable": True}})
    rpc(base, "Script.Start", {"id": script_id})


@click.command()
@click.option(
    "--shelly-ip",
    "-i",
    default=DEFAULT_SHELLY_IP,
    show_default=True,
    envvar="SHELLY_IP",
    help="IP address of the Shelly device.",
)
@click.option(
    "--script-name",
    "-n",
    default=DEFAULT_SCRIPT_NAME,
    show_default=True,
    help="Name of the script on the Shelly.",
)
def main(shelly_ip: str, script_name: str) -> None:
    """Deploy shelly_charge_limiter.js to a Shelly device and start it.

    \f
    :param shelly_ip: IP address of the Shelly device.
    :param script_name: Name under which the script is stored on the device.
    """  # noqa: D301 (the \f hides the field list from click's --help output)
    base = f"http://{shelly_ip}/rpc"

    try:
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            code = f.read()
    except OSError as exc:
        raise click.ClickException(f"Could not read {SCRIPT_FILE}: {exc}")

    try:
        existing_id = find_script_id(base, script_name)
        if existing_id is not None:
            delete_existing(base, existing_id)

        new_id = create_script(base, script_name)
        click.echo(f"Created new script: id={new_id}")

        upload_code(base, new_id, code)
        enable_and_start(base, new_id)
    except httpx2.HTTPError as exc:
        raise click.ClickException(f"RPC call to {shelly_ip} failed: {exc}")

    click.echo(f"Deployed & started: id={new_id}")


if __name__ == "__main__":
    main()
