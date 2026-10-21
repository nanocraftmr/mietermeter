import time
import datetime
import sys
import threading
import uuid

from app_modules import config, logger, utils, camera_handler, supabase_handler

try:
    from worker import hdg, qlog
except ImportError:
    logger.log_error(
        "Failed to import worker modules. Ensure worker files exist.",
        include_traceback=True,
    )
    sys.exit("Critical Error: Cannot import worker modules.")


def process_hdg_source(source_config, query_id, mac_address):
    ip = source_config.get("ip")
    name = source_config.get("name", "Unknown")
    if not ip:
        logger.log_error(f"No IP for source {name}. Skipping.", include_traceback=False)
        return

    logger.log_message(f"Processing: {name} | IP: {ip} | ID: {query_id}")

    try:
        result = hdg.fetch_hdg_data(ip, query_id)
        if not isinstance(result, list) or not result or not isinstance(result[0], dict) or 'text' not in result[0]:
            logger.log_error(f"Bad result format from {name}: {result}", include_traceback=False)
            return

        value = result[0]['text']
        data = {
            "anlage": name,
            "key": query_id,
            "value": value,
            "ip": ip,
            "mac": mac_address
        }

        success = supabase_handler.save_hdg_data(data)
        if not success:
            logger.log_error(f"Failed to save data for {name} ({query_id})")

    except AttributeError:
        logger.log_error("Missing 'fetch_hdg_data' in worker.hdg", include_traceback=True)
    except Exception as e:
        logger.log_error(f"Error from {name} ({query_id}): {e}", include_traceback=True)


def screenshot_worker(mac_address):
    logger.log_message("Screenshot thread started.")
    taken_today = {8: None, 20: None}

    while True:
        now = datetime.datetime.now()
        if now.hour in taken_today:
            if taken_today[now.hour] != now.date():
                logger.log_message(f"Taking scheduled screenshot for {now.hour}:00.")
                camera_handler.take_and_upload_screenshot(mac_address)
                taken_today[now.hour] = now.date()
        time.sleep(60)  # check every minute


def collect_and_save_heating_data(mac_address):
    logger.log_message(
        f"Starting Q log collection from {config.QLOG_ADDRESS} for up to "
        f"{config.QLOG_COLLECTION_SECONDS} seconds."
    )
    try:
        readings = qlog.collect_readings(
            address=config.QLOG_ADDRESS,
            channel=config.QLOG_CHANNEL,
            collection_seconds=config.QLOG_COLLECTION_SECONDS,
            minimum_cycle_seconds=config.QLOG_MINIMUM_CYCLE_SECONDS,
        )
    except Exception as e:
        logger.log_error(f"Q log collection failed: {e}", include_traceback=True)
        return False

    if not readings:
        logger.log_error(
            "Q log collection completed without meter readings.",
            include_traceback=False,
        )
        return False

    collection_id = str(uuid.uuid4())
    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = []
    for reading in readings:
        rows.append(
            {
                "collection_id": collection_id,
                "captured_at": captured_at,
                "source_mac": mac_address,
                "qlog_address": config.QLOG_ADDRESS,
                "meter_id": reading["meter_id"],
                "manufacturer": reading["manufacturer"],
                "version": reading["version"],
                "device_type": reading["device_type"],
                "access_number": reading["access_number"],
                "current_value": reading["current_value"],
                "setpoint_value": reading["setpoint_value"],
                "setpoint_date": (
                    reading["setpoint_date"].date().isoformat()
                    if reading["setpoint_date"]
                    else None
                ),
                "meter_time": (
                    reading["meter_time"].isoformat()
                    if reading["meter_time"]
                    else None
                ),
                "battery_low": reading["battery_low"],
                "status": reading["status"],
                "error_date": (
                    reading["error_date"].date().isoformat()
                    if reading["error_date"]
                    else None
                ),
                "rssi_dbm": reading["rssi_dbm"],
            }
        )

    meter_ids = ", ".join(sorted(row["meter_id"] for row in rows))
    logger.log_message(
        f"Q log collection found {len(rows)} unique meters: {meter_ids}"
    )
    return supabase_handler.save_heating_data(rows)


def heating_worker(mac_address):
    logger.log_message(
        "Heating scheduler started for hours: "
        + ", ".join(str(hour) for hour in config.QLOG_READING_HOURS)
    )
    collected_today = {hour: None for hour in config.QLOG_READING_HOURS}

    while True:
        now = datetime.datetime.now()
        if (
            now.hour in collected_today
            and collected_today[now.hour] != now.date()
        ):
            collected_today[now.hour] = now.date()
            collect_and_save_heating_data(mac_address)
        time.sleep(60)


def main_loop():
    logger.log_message("=" * 30 + " Script Start " + "=" * 30)
    logger.log_message(f"Current Time: {datetime.datetime.now()}")

    try:
        config.check_essential_config()
    except ValueError as e:
        logger.log_error(f"Config error: {e}", include_traceback=False)
        sys.exit("Missing essential config.")

    mac_address = utils.get_mac_address()
    logger.log_message(f"MAC Address: {mac_address}")

    supabase_client = supabase_handler.init_supabase_client()
    if not supabase_client:
        logger.log_error("Supabase init failed.", include_traceback=False)

    if config.CAMERA_RTSP_URL:
        threading.Thread(target=screenshot_worker, args=(mac_address,), daemon=True).start()
        logger.log_message("Screenshot scheduler started.")
        camera_handler.take_and_upload_screenshot(mac_address)

    if config.QLOG_ADDRESS:
        threading.Thread(
            target=heating_worker,
            args=(mac_address,),
            daemon=True,
        ).start()
    else:
        logger.log_message(
            "QLOG_ADDRESS not configured; heating collection disabled."
        )

    cycle = 0
    while True:
        cycle += 1
        logger.log_message(f"--- Cycle {cycle} @ {datetime.datetime.now()} ---")

        query_data = utils.load_query_data()
        if not query_data:
            logger.log_error("Query data missing or invalid.")
            time.sleep(600)
            continue

        for idx, item in enumerate(query_data):
            query_id = str(item.get("id"))
            if not query_id:
                continue

            logger.log_message(f"Processing item {idx+1}/{len(query_data)} ID={query_id}")
            for source in config.HDG_SOURCES:
                process_hdg_source(source, query_id, mac_address)
                time.sleep(1)

        logger.cleanup_old_logs()
        time.sleep(min(300, config.MAIN_LOOP_SLEEP_MINUTES * 60))


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.log_message("Script interrupted by user.")
    except SystemExit as e:
        logger.log_error(f"Exited: {e}", include_traceback=False)
    except Exception as e:
        logger.log_error(f"Critical error in main: {e}", include_traceback=True)
    finally:
        logger.log_message("=" * 30 + " Script End " + "=" * 30)
