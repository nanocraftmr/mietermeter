"""Fetch Fronius Solar API lifetime counters for nightly Supabase push."""

from __future__ import annotations

import requests

TIMEOUT_SECONDS = 10


def _get_json(url: str) -> dict:
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _first_inverter(data: dict) -> dict | None:
    body = (data or {}).get("Body", {}).get("Data") or {}
    if not isinstance(body, dict) or not body:
        return None
    first = next(iter(body.values()))
    return first if isinstance(first, dict) else None


def _first_meter(data: dict) -> dict | None:
    body = (data or {}).get("Body", {}).get("Data") or {}
    if not isinstance(body, dict) or not body:
        return None
    first = next(iter(body.values()))
    return first if isinstance(first, dict) else None


def _total_energy_wh(inverter_data: dict) -> float | None:
    total = (inverter_data or {}).get("Body", {}).get("Data", {}).get("TOTAL_ENERGY")
    if not isinstance(total, dict):
        return None
    values = total.get("Values")
    if isinstance(values, dict) and values:
        value = next(iter(values.values()))
        return None if value is None else float(value)
    if "Value" in total and total["Value"] is not None:
        return float(total["Value"])
    return None


def _api_timestamp(*responses: dict) -> str | None:
    for response in responses:
        ts = (response or {}).get("Head", {}).get("Timestamp")
        if ts:
            return str(ts)
    return None


def fetch_pv_reading(ip: str) -> dict:
    """Read one Fronius host into a pv_readings row (without created_at).

    device_name comes from GetInverterInfo CustomName (e.g. "PV Esterhazy").
    Counters are lifetime Wh from the Solar API.
    """
    base = f"http://{ip}/solar_api/v1"
    info = _get_json(f"{base}/GetInverterInfo.cgi")
    inverter = _get_json(f"{base}/GetInverterRealtimeData.cgi?Scope=System")
    meter = _get_json(f"{base}/GetMeterRealtimeData.cgi?Scope=System")

    inverter_info = _first_inverter(info) or {}
    custom_name = inverter_info.get("CustomName")
    device_name = (str(custom_name).strip() if custom_name else "") or f"fronius-{ip}"

    meter_row = _first_meter(meter) or {}
    read_at = _api_timestamp(inverter, meter, info)
    if not read_at:
        raise ValueError(f"No Timestamp in Fronius response for {ip}")

    return {
        "device_name": device_name,
        "ip_address": ip,
        "read_at": read_at,
        "total_production": _total_energy_wh(inverter),
        "total_feed_in": (
            None
            if meter_row.get("EnergyReal_WAC_Sum_Produced") is None
            else float(meter_row["EnergyReal_WAC_Sum_Produced"])
        ),
        "total_grid_import": (
            None
            if meter_row.get("EnergyReal_WAC_Sum_Consumed") is None
            else float(meter_row["EnergyReal_WAC_Sum_Consumed"])
        ),
    }


def fetch_all_pv_readings(ips: list[str]) -> tuple[list[dict], list[str]]:
    """Fetch readings for every configured IP. Returns (rows, error messages)."""
    rows: list[dict] = []
    errors: list[str] = []
    for ip in ips:
        try:
            rows.append(fetch_pv_reading(ip))
        except Exception as exc:  # keep going for remaining devices
            errors.append(f"{ip}: {exc}")
    return rows, errors
