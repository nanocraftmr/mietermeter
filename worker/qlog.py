"""Read QUNDIS Q log 5.5 telegrams over Bluetooth RFCOMM."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Record:
    vif: int
    storage: int
    function: int
    value: int | datetime | None


def _decode_manufacturer(value: int) -> str:
    return "".join(
        chr(((value >> shift) & 0x1F) + 64) for shift in (10, 5, 0)
    )


def _decode_bcd_le(data: bytes) -> int | None:
    digits = "".join(f"{byte:02x}" for byte in reversed(data))
    if any(character not in "0123456789" for character in digits):
        return None
    return int(digits)


def _decode_date(data: bytes) -> datetime | None:
    if len(data) != 2 or data == b"\xff\xff":
        return None
    day = data[0] & 0x1F
    month = data[1] & 0x0F
    year = 2000 + ((data[0] & 0xE0) >> 5) + ((data[1] & 0xF0) >> 1)
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _decode_datetime(data: bytes) -> datetime | None:
    if len(data) != 4 or data == b"\xff\xff\xff\xff":
        return None
    minute = data[0] & 0x3F
    hour = data[1] & 0x1F
    day = data[2] & 0x1F
    month = data[3] & 0x0F
    year = 2000 + ((data[2] & 0xE0) >> 5) + ((data[3] & 0xF0) >> 1)
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def _data_length(dif: int, data: bytes, offset: int) -> tuple[int, int]:
    lengths = {
        0x0: 0,
        0x1: 1,
        0x2: 2,
        0x3: 3,
        0x4: 4,
        0x5: 4,
        0x6: 6,
        0x7: 8,
        0x8: 0,
        0x9: 1,
        0xA: 2,
        0xB: 3,
        0xC: 4,
        0xE: 6,
    }
    coding = dif & 0x0F
    if coding == 0xD:
        if offset >= len(data):
            return 0, offset
        return data[offset], offset + 1
    return lengths.get(coding, 0), offset


def _decode_record_value(dif: int, vif: int, raw: bytes):
    coding = dif & 0x0F
    if vif == 0x6C:
        return _decode_date(raw)
    if vif == 0x6D:
        return _decode_datetime(raw)
    if coding in (0x9, 0xA, 0xB, 0xC, 0xE):
        return _decode_bcd_le(raw)
    if coding in (0x1, 0x2, 0x3, 0x4, 0x6, 0x7):
        return int.from_bytes(raw, "little", signed=False)
    return None


def _parse_records(data: bytes) -> list[Record]:
    records = []
    offset = 0
    while offset < len(data):
        dif = data[offset]
        offset += 1
        if dif in (0x0F, 0x1F, 0x2F, 0x7F):
            break

        storage = (dif >> 6) & 1
        extension_index = 0
        extension = dif
        while extension & 0x80:
            if offset >= len(data):
                return records
            extension = data[offset]
            offset += 1
            storage |= (extension & 0x0F) << (1 + 4 * extension_index)
            extension_index += 1

        if offset >= len(data):
            break
        vif_byte = data[offset]
        offset += 1
        vif = vif_byte & 0x7F
        while vif_byte & 0x80:
            if offset >= len(data):
                return records
            vif_byte = data[offset]
            offset += 1

        length, offset = _data_length(dif, data, offset)
        if offset + length > len(data):
            break
        raw = data[offset : offset + length]
        offset += length
        records.append(
            Record(
                vif=vif,
                storage=storage,
                function=(dif >> 4) & 0x03,
                value=_decode_record_value(dif, vif, raw),
            )
        )
    return records


def _slip_unescape(data: bytes) -> bytes:
    return data.replace(b"\xdb\xdc", b"\xc0").replace(b"\xdb\xdd", b"\xdb")


def parse_qlog_frame(frame: bytes) -> dict | None:
    """Decode one Q log frame. Returns None for unsupported frames."""
    frame = _slip_unescape(frame)
    if len(frame) < 8 or frame[2] != 0x02:
        return None

    wmbus_length = frame[3] + 1
    wmbus_end = 3 + wmbus_length
    if wmbus_end >= len(frame):
        return None
    wmbus = frame[3:wmbus_end]
    if len(wmbus) < 15 or wmbus[1] != 0x44:
        return None

    records = _parse_records(wmbus[15:])
    current = next(
        (r.value for r in records if r.vif == 0x6E and r.storage == 0), None
    )
    setpoint = next(
        (r.value for r in records if r.vif == 0x6E and r.storage == 1), None
    )
    setpoint_date = next(
        (r.value for r in records if r.vif == 0x6C and r.storage == 1), None
    )
    meter_time = next((r.value for r in records if r.vif == 0x6D), None)
    error_date = next(
        (
            r.value
            for r in records
            if r.vif == 0x6C and r.function == 3
        ),
        None,
    )

    manufacturer_value = int.from_bytes(wmbus[2:4], "little")
    status = wmbus[12]
    rssi_byte = frame[wmbus_end]
    return {
        "meter_id": "".join(f"{byte:02x}" for byte in reversed(wmbus[4:8])),
        "manufacturer": _decode_manufacturer(manufacturer_value),
        "version": wmbus[8],
        "device_type": wmbus[9],
        "access_number": wmbus[11],
        "current_value": current,
        "setpoint_value": setpoint,
        "setpoint_date": setpoint_date,
        "meter_time": meter_time,
        "battery_low": bool(status & 0x04),
        "status": status,
        "error_date": error_date,
        "rssi_dbm": rssi_byte - 256 if rssi_byte >= 128 else rssi_byte,
    }


def _frames_from_buffer(buffer: bytearray):
    while True:
        start = buffer.find(0xC0)
        if start < 0:
            buffer.clear()
            return
        end = buffer.find(0xC0, start + 1)
        if end < 0:
            if start:
                del buffer[:start]
            return
        frame = bytes(buffer[start + 1 : end])
        del buffer[: end + 1]
        if frame:
            yield frame


def collect_readings(
    address: str,
    channel: int = 5,
    collection_seconds: int = 16 * 60,
    minimum_cycle_seconds: int = 10 * 60,
) -> list[dict]:
    """Collect one radio cycle, keeping each meter only once."""
    readings_by_id = {}
    started_at = time.monotonic()
    deadline = started_at + collection_seconds
    first_meter_id = None
    buffer = bytearray()

    with socket.socket(
        socket.AF_BLUETOOTH,
        socket.SOCK_STREAM,
        socket.BTPROTO_RFCOMM,
    ) as connection:
        connection.settimeout(30)
        connection.connect((address, channel))

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            connection.settimeout(max(0.1, min(10, remaining)))
            try:
                chunk = connection.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer.extend(chunk)

            for frame in _frames_from_buffer(buffer):
                reading = parse_qlog_frame(frame)
                if reading is None:
                    continue
                meter_id = reading["meter_id"]
                if first_meter_id is None:
                    first_meter_id = meter_id
                elif (
                    meter_id == first_meter_id
                    and time.monotonic() - started_at >= minimum_cycle_seconds
                ):
                    return list(readings_by_id.values())
                if meter_id not in readings_by_id:
                    readings_by_id[meter_id] = reading

    return list(readings_by_id.values())
