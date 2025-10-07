#!/usr/bin/env python3
"""
IoT Temperature Monitoring API
Provides REST endpoints and Prometheus metrics for sensor data
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from influxdb_client import InfluxDBClient
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'API request duration')
SENSOR_TEMPERATURE = Gauge('sensor_temperature_celsius', 'Current temperature', ['device_id', 'sensor_id', 'sensor_name'])
SENSOR_HUMIDITY = Gauge('sensor_humidity_percent', 'Current humidity', ['device_id', 'sensor_id', 'sensor_name'])
SENSOR_BATTERY = Gauge('sensor_battery_percent', 'Current battery level', ['device_id', 'sensor_id', 'sensor_name'])
SENSOR_LAST_SEEN = Gauge('sensor_last_seen_timestamp', 'Last seen timestamp', ['device_id', 'sensor_id', 'sensor_name'])
THERMOSTAT_SWITCH_STATE = Gauge('thermostat_switch_state', 'Thermostat switch state (1=ON, 0=OFF)')
THERMOSTAT_TARGET_TEMP = Gauge('thermostat_target_temperature_celsius', 'Thermostat target temperature')
THERMOSTAT_CURRENT_TEMP = Gauge('thermostat_current_temperature_celsius', 'Current indoor temperature used for control')

app = FastAPI(
    title="IoT Temperature Monitoring API",
    description="REST API for temperature and humidity sensor data",
    version="1.0.0"
)

# Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "iot-admin-token-12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor-data")

# InfluxDB client
influx_client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)
query_api = influx_client.query_api()

# Data models
class SensorReading(BaseModel):
    timestamp: datetime
    device_id: str
    sensor_id: Optional[str] = None
    value: float
    unit: str

class SensorInfo(BaseModel):
    device_id: str
    sensor_id: Optional[str] = None
    sensor_type: str
    last_seen: Optional[datetime] = None
    measurements: List[str]

class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    version: str
    influxdb_connected: bool
    shelly_connected: Optional[bool] = None
    control_loop_running: Optional[bool] = None
    last_control_loop_run: Optional[datetime] = None
    control_loop_error: Optional[str] = None

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request, call_next):
    with REQUEST_DURATION.time():
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
        response = await call_next(request)
        return response

@app.get("/", summary="API Information")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "IoT Temperature Monitoring API",
        "version": "2.0.0",
        "endpoints": {
            "sensors": "/api/v1/sensors",
            "temperature": "/api/v1/temperature",
            "humidity": "/api/v1/humidity",
            "battery": "/api/v1/battery",
            "latest": "/api/v1/latest",
            "thermostat_config": "/api/v1/thermostat/config",
            "thermostat_status": "/api/v1/thermostat/status",
            "thermostat_switch": "/api/v1/thermostat/switch",
            "metrics": "/metrics",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/health", response_model=HealthStatus, summary="Health Check")
async def health_check():
    """Health check endpoint - checks all critical components"""
    from thermostat import shelly_controller, control_loop_state

    # Test InfluxDB connection
    try:
        buckets = influx_client.buckets_api().find_buckets()
        influxdb_connected = True
    except Exception:
        influxdb_connected = False

    # Test Shelly connection
    shelly_connected = False
    try:
        shelly_controller.get_switch_status()
        shelly_connected = True
    except Exception:
        pass

    # Check control loop health
    now = datetime.utcnow()
    control_loop_healthy = True
    control_loop_running = control_loop_state.get("running", False)
    last_run = control_loop_state.get("last_run")
    error = control_loop_state.get("last_error")

    # Control loop should run at least every 6 minutes (3min interval + 3min grace)
    if last_run and (now - last_run).total_seconds() > 360:
        control_loop_healthy = False

    # Determine overall health
    is_healthy = (
        influxdb_connected and
        shelly_connected and
        control_loop_healthy and
        error is None
    )

    return HealthStatus(
        status="healthy" if is_healthy else "unhealthy",
        timestamp=now,
        version="2.0.0",
        influxdb_connected=influxdb_connected,
        shelly_connected=shelly_connected,
        control_loop_running=control_loop_running,
        last_control_loop_run=last_run,
        control_loop_error=error
    )

@app.get("/api/v1/sensors", response_model=List[SensorInfo], summary="List Sensors")
async def list_sensors():
    """Get list of all available sensors"""
    try:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -7d)
        |> filter(fn: (r) => r._measurement == "temperature" or r._measurement == "humidity")
        |> group(columns: ["device_id", "sensor_id", "sensor_type"])
        |> last()
        |> group()
        '''

        result = query_api.query(query)
        sensors = {}

        for table in result:
            for record in table.records:
                device_id = record.values.get("device_id", "unknown")
                sensor_id = record.values.get("sensor_id")
                sensor_type = record.values.get("sensor_type", "unknown")
                measurement = record.get_measurement()

                key = (device_id, sensor_id)
                if key not in sensors:
                    sensors[key] = {
                        "device_id": device_id,
                        "sensor_id": sensor_id,
                        "sensor_type": sensor_type,
                        "last_seen": record.get_time(),
                        "measurements": []
                    }

                if measurement not in sensors[key]["measurements"]:
                    sensors[key]["measurements"].append(measurement)

                # Update last seen if this record is newer
                if record.get_time() > sensors[key]["last_seen"]:
                    sensors[key]["last_seen"] = record.get_time()

        return [SensorInfo(**sensor) for sensor in sensors.values()]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying sensors: {str(e)}")

@app.get("/api/v1/temperature", response_model=List[SensorReading], summary="Get Temperature Data")
async def get_temperature(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """Get temperature readings"""
    return await get_sensor_data("temperature", device_id, sensor_id, start, end, limit)

@app.get("/api/v1/humidity", response_model=List[SensorReading], summary="Get Humidity Data")
async def get_humidity(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """Get humidity readings"""
    return await get_sensor_data("humidity", device_id, sensor_id, start, end, limit)

@app.get("/api/v1/battery", response_model=List[SensorReading], summary="Get Battery Data")
async def get_battery(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """Get battery level readings"""
    return await get_sensor_data("battery", device_id, sensor_id, start, end, limit, "level")

async def get_sensor_data(
    measurement: str,
    device_id: Optional[str],
    sensor_id: Optional[str],
    start: Optional[datetime],
    end: Optional[datetime],
    limit: int,
    field: str = "value"
) -> List[SensorReading]:
    """Generic function to get sensor data"""
    try:
        # Build time range
        time_range = "start: -24h"
        if start and end:
            time_range = f'start: {start.isoformat()}Z, stop: {end.isoformat()}Z'
        elif start:
            time_range = f'start: {start.isoformat()}Z'

        # Build filters
        filters = [f'r._measurement == "{measurement}"', f'r._field == "{field}"']

        if device_id:
            filters.append(f'r.device_id == "{device_id}"')
        if sensor_id:
            filters.append(f'r.sensor_id == "{sensor_id}"')

        filter_str = " and ".join(filters)

        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range({time_range})
        |> filter(fn: (r) => {filter_str})
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: {limit})
        '''

        result = query_api.query(query)
        readings = []

        # Unit mapping
        unit_map = {
            "temperature": "celsius",
            "humidity": "percent",
            "battery": "percent"
        }

        for table in result:
            for record in table.records:
                reading = SensorReading(
                    timestamp=record.get_time(),
                    device_id=record.values.get("device_id", "unknown"),
                    sensor_id=record.values.get("sensor_id"),
                    value=record.get_value(),
                    unit=unit_map.get(measurement, "unknown")
                )
                readings.append(reading)

        # Update Prometheus metrics with latest values
        if readings:
            latest = readings[0]  # Most recent due to desc sort
            if measurement == "temperature":
                SENSOR_TEMPERATURE.labels(
                    device_id=latest.device_id,
                    sensor_id=latest.sensor_id or "unknown"
                ).set(latest.value)
            elif measurement == "humidity":
                SENSOR_HUMIDITY.labels(
                    device_id=latest.device_id,
                    sensor_id=latest.sensor_id or "unknown"
                ).set(latest.value)
            elif measurement == "battery":
                SENSOR_BATTERY.labels(
                    device_id=latest.device_id,
                    sensor_id=latest.sensor_id or "unknown"
                ).set(latest.value)

            SENSOR_LAST_SEEN.labels(
                device_id=latest.device_id,
                sensor_id=latest.sensor_id or "unknown"
            ).set(latest.timestamp.timestamp())

        return readings

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying {measurement} data: {str(e)}")

@app.get("/api/v1/latest", summary="Get Latest Readings")
async def get_latest_readings():
    """Get the latest reading for each sensor"""
    try:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "temperature" or r._measurement == "humidity" or r._measurement == "battery")
        |> group(columns: ["device_id", "sensor_id", "_measurement"])
        |> last()
        |> group()
        '''

        result = query_api.query(query)
        latest_readings = {}

        for table in result:
            for record in table.records:
                device_id = record.values.get("device_id", "unknown")
                sensor_id = record.values.get("sensor_id", "unknown")
                measurement = record.get_measurement()
                value = record.get_value()
                timestamp = record.get_time()

                key = (device_id, sensor_id)
                if key not in latest_readings:
                    latest_readings[key] = {
                        "device_id": device_id,
                        "sensor_id": sensor_id,
                        "timestamp": timestamp,
                        "readings": {}
                    }

                latest_readings[key]["readings"][measurement] = value

                # Update timestamp if this reading is newer
                if timestamp > latest_readings[key]["timestamp"]:
                    latest_readings[key]["timestamp"] = timestamp

        return list(latest_readings.values())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying latest readings: {str(e)}")

@app.get("/metrics", response_class=PlainTextResponse, summary="Prometheus Metrics")
async def metrics():
    """Prometheus metrics endpoint - updates gauges with latest values"""
    # Update Prometheus gauges with latest sensor data before serving metrics
    await update_prometheus_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def update_prometheus_metrics():
    """Update Prometheus gauges with latest sensor values from database"""
    try:
        # Get latest temperature readings for all sensors
        temp_query = '''
        from(bucket: "sensor-data")
          |> range(start: -5m)
          |> filter(fn: (r) => r["_measurement"] == "temperature")
          |> group(columns: ["gateway_id", "sensor_id"])
          |> last()
        '''

        temp_result = query_api.query(temp_query, org=INFLUXDB_ORG)

        for table in temp_result:
            for record in table.records:
                gateway_id = record.values.get("gateway_id", "unknown")
                sensor_id = record.values.get("sensor_id", "unknown")
                sensor_name = record.values.get("sensor_name", "unknown")
                value = record.get_value()

                SENSOR_TEMPERATURE.labels(
                    device_id=gateway_id,
                    sensor_id=sensor_id,
                    sensor_name=sensor_name
                ).set(value)

        # Get latest humidity readings
        humidity_query = '''
        from(bucket: "sensor-data")
          |> range(start: -5m)
          |> filter(fn: (r) => r["_measurement"] == "humidity")
          |> group(columns: ["gateway_id", "sensor_id"])
          |> last()
        '''

        humidity_result = query_api.query(humidity_query, org=INFLUXDB_ORG)

        for table in humidity_result:
            for record in table.records:
                gateway_id = record.values.get("gateway_id", "unknown")
                sensor_id = record.values.get("sensor_id", "unknown")
                sensor_name = record.values.get("sensor_name", "unknown")
                value = record.get_value()

                SENSOR_HUMIDITY.labels(
                    device_id=gateway_id,
                    sensor_id=sensor_id,
                    sensor_name=sensor_name
                ).set(value)

        # Get latest battery readings
        battery_query = '''
        from(bucket: "sensor-data")
          |> range(start: -5m)
          |> filter(fn: (r) => r["_measurement"] == "battery")
          |> group(columns: ["gateway_id", "sensor_id"])
          |> last()
        '''

        battery_result = query_api.query(battery_query, org=INFLUXDB_ORG)

        for table in battery_result:
            for record in table.records:
                gateway_id = record.values.get("gateway_id", "unknown")
                sensor_id = record.values.get("sensor_id", "unknown")
                sensor_name = record.values.get("sensor_name", "unknown")
                value = record.get_value()

                SENSOR_BATTERY.labels(
                    device_id=gateway_id,
                    sensor_id=sensor_id,
                    sensor_name=sensor_name
                ).set(value)

    except Exception as e:
        # Log error but don't fail the metrics endpoint
        print(f"Error updating Prometheus metrics: {e}")

# ============================================================================
# THERMOSTAT CONTROL ENDPOINTS
# ============================================================================

from thermostat import (
    ThermostatConfig, ThermostatStatus, ThermostatMode,
    thermostat_manager, shelly_controller, calculate_control_decision
)

@app.get("/api/v1/thermostat/config", response_model=ThermostatConfig, summary="Get Thermostat Configuration")
async def get_thermostat_config():
    """Get current thermostat configuration"""
    return thermostat_manager.get_config()

@app.post("/api/v1/thermostat/config", response_model=ThermostatConfig, summary="Set Thermostat Configuration")
async def set_thermostat_config(config: ThermostatConfig):
    """Update thermostat configuration (writes to persistent JSON file on host)"""
    try:
        thermostat_manager.set_config(config)
        return thermostat_manager.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")

@app.get("/api/v1/thermostat/status", response_model=ThermostatStatus, summary="Get Thermostat Status")
async def get_thermostat_status():
    """Get current thermostat status including all sensor temperatures and switch state"""
    try:
        config = thermostat_manager.get_config()
        state = thermostat_manager.get_state()

        # Get all temperature sensor readings from InfluxDB
        temp_query = '''
        from(bucket: "sensor-data")
          |> range(start: -5m)
          |> filter(fn: (r) => r["_measurement"] == "temperature")
          |> group(columns: ["sensor_name"])
          |> last()
        '''

        temp_result = query_api.query(temp_query, org=INFLUXDB_ORG)
        all_temps = {}
        indoor_temp = None

        for table in temp_result:
            for record in table.records:
                sensor_name = record.values.get("sensor_name", "unknown")
                value = record.get_value()
                all_temps[sensor_name] = value

                # Use indoor sensor as control sensor
                if sensor_name == "temp_indoor":
                    indoor_temp = value

        # Get switch status from Shelly
        try:
            switch_status = shelly_controller.get_switch_status()
            switch_on = switch_status.get("output", False)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Cannot reach Shelly device: {str(e)}")

        # Determine active target based on mode
        if config.mode == ThermostatMode.AUTO:
            active_target = config.target_temp
        elif config.mode == ThermostatMode.ECO:
            active_target = config.eco_temp
        else:
            active_target = config.target_temp  # For ON/OFF modes, show AUTO target

        # Calculate control decision for AUTO/ECO modes
        heating_needed = None
        reason = None
        switch_locked_until = None

        if indoor_temp is not None and config.mode in [ThermostatMode.AUTO, ThermostatMode.ECO]:
            should_be_on, decision_reason = calculate_control_decision(
                current_temp=indoor_temp,
                target_temp=active_target,
                hysteresis=config.hysteresis,
                current_switch_on=switch_on,
                last_switch_change=state.last_switch_change,
                min_on_time=config.min_on_time,
                min_off_time=config.min_off_time
            )
            heating_needed = should_be_on
            reason = decision_reason

            # Calculate when switch will be unlocked
            if state.last_switch_change:
                if switch_on:
                    unlock_time = state.last_switch_change + timedelta(minutes=config.min_on_time)
                else:
                    unlock_time = state.last_switch_change + timedelta(minutes=config.min_off_time)

                if unlock_time > datetime.utcnow():
                    switch_locked_until = unlock_time
        elif config.mode == ThermostatMode.ON:
            reason = "Manual override: Switch forced ON"
        elif config.mode == ThermostatMode.OFF:
            reason = "Manual override: Switch forced OFF"

        return ThermostatStatus(
            config=config,
            current_temp=indoor_temp,
            all_temps=all_temps,
            switch_state=switch_on,
            active_target=active_target,
            heating_needed=heating_needed,
            reason=reason,
            switch_locked_until=switch_locked_until
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting thermostat status: {str(e)}")

@app.post("/api/v1/thermostat/switch", summary="Manual Switch Control")
async def control_switch(turn_on: bool):
    """
    Manually control the switch (overrides AUTO/ECO mode temporarily)
    Note: This does NOT change the mode - switch will be controlled by mode on next status check
    """
    try:
        result = shelly_controller.set_switch(turn_on)
        thermostat_manager.update_state(turn_on, f"Manual switch control: {'ON' if turn_on else 'OFF'}")
        THERMOSTAT_SWITCH_STATE.set(1 if turn_on else 0)
        return {
            "success": True,
            "switch_on": turn_on,
            "shelly_response": result,
            "note": "Switch set manually - will be controlled by configured mode on next cycle"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error controlling switch: {str(e)}")

# ============================================================================
# BACKGROUND CONTROL LOOP
# ============================================================================

from thermostat import control_loop_state

async def thermostat_control_loop():
    """
    Background task that runs the thermostat control loop every 60 seconds
    Automatically controls the switch based on mode and temperature
    """
    from thermostat import ThermostatMode

    logger.info("Starting thermostat control loop")
    control_loop_state["running"] = True

    while True:
        try:
            control_loop_state["last_run"] = datetime.utcnow()

            # Get current configuration
            config = thermostat_manager.get_config()

            # Skip control loop if mode is manual (ON/OFF)
            if config.mode == ThermostatMode.ON:
                logger.debug("Mode is ON - forcing switch ON")
                try:
                    result = shelly_controller.set_switch(True)
                    if result.get("output") is True:
                        thermostat_manager.update_state(True, "Manual mode: ON")
                        THERMOSTAT_SWITCH_STATE.set(1)
                except Exception as e:
                    logger.error(f"Error forcing switch ON: {e}")

            elif config.mode == ThermostatMode.OFF:
                logger.debug("Mode is OFF - forcing switch OFF")
                try:
                    result = shelly_controller.set_switch(False)
                    if result.get("output") is False:
                        thermostat_manager.update_state(False, "Manual mode: OFF")
                        THERMOSTAT_SWITCH_STATE.set(0)
                except Exception as e:
                    logger.error(f"Error forcing switch OFF: {e}")

            elif config.mode in [ThermostatMode.AUTO, ThermostatMode.ECO]:
                # Get last N temperature samples and average them for slow-responding systems
                sample_count = config.temp_sample_count
                temp_query = f'''
                from(bucket: "sensor-data")
                  |> range(start: -5m)
                  |> filter(fn: (r) => r["_measurement"] == "temperature")
                  |> filter(fn: (r) => r["sensor_name"] == "temp_indoor")
                  |> sort(columns: ["_time"], desc: true)
                  |> limit(n: {sample_count})
                '''

                temp_result = query_api.query(temp_query, org=INFLUXDB_ORG)
                temps = []

                for table in temp_result:
                    for record in table.records:
                        temps.append(record.get_value())

                # Average the samples (or fewer if not enough data yet)
                indoor_temp = sum(temps) / len(temps) if temps else None

                if indoor_temp and len(temps) > 1:
                    logger.info(f"Averaging {len(temps)} temperature samples: {[f'{t:.1f}' for t in temps]} -> {indoor_temp:.2f}°C")

                if indoor_temp is None:
                    logger.warning("No indoor temperature data available")
                    control_loop_state["last_error"] = "No indoor temperature data"
                    control_loop_state["consecutive_errors"] += 1
                else:
                    # Clear error state on success
                    control_loop_state["last_error"] = None
                    control_loop_state["consecutive_errors"] = 0

                    # Determine target temperature
                    target = config.target_temp if config.mode == ThermostatMode.AUTO else config.eco_temp

                    # Update target temperature metric
                    THERMOSTAT_TARGET_TEMP.set(target)
                    THERMOSTAT_CURRENT_TEMP.set(indoor_temp)

                    # Get current switch state
                    state = thermostat_manager.get_state()
                    switch_status = shelly_controller.get_switch_status()
                    current_switch_on = switch_status.get("output", False)

                    # Calculate control decision
                    should_be_on, reason = calculate_control_decision(
                        current_temp=indoor_temp,
                        target_temp=target,
                        hysteresis=config.hysteresis,
                        current_switch_on=current_switch_on,
                        last_switch_change=state.last_switch_change,
                        min_on_time=config.min_on_time,
                        min_off_time=config.min_off_time
                    )

                    logger.info(f"Control decision: {reason}")

                    # Execute switch control if state should change
                    if should_be_on != current_switch_on:
                        logger.info(f"Changing switch state: {current_switch_on} -> {should_be_on}")
                        result = shelly_controller.set_switch(should_be_on)

                        # Small delay to let switch settle (race condition fix)
                        await asyncio.sleep(0.2)

                        # Verify the switch was set correctly
                        # Shelly Switch.Set returns {"was_on": bool} not {"output": bool}
                        # So we need to query the status to verify
                        verify_status = shelly_controller.get_switch_status()
                        actual_state = verify_status.get("output", None)

                        if actual_state == should_be_on:
                            thermostat_manager.update_state(should_be_on, reason)
                            logger.info(f"Switch successfully set to {'ON' if should_be_on else 'OFF'}")
                            THERMOSTAT_SWITCH_STATE.set(1 if should_be_on else 0)
                        else:
                            logger.error(f"Switch state mismatch after command: expected {should_be_on}, got {actual_state}")
                            control_loop_state["last_error"] = f"Switch verification failed: expected {should_be_on}, got {actual_state}"
                            control_loop_state["consecutive_errors"] += 1
                    else:
                        # Update state even if not changing (for decision logging)
                        thermostat_manager.update_state(current_switch_on, reason)
                        THERMOSTAT_SWITCH_STATE.set(1 if current_switch_on else 0)

        except Exception as e:
            logger.error(f"Error in control loop: {e}", exc_info=True)
            control_loop_state["last_error"] = str(e)
            control_loop_state["consecutive_errors"] += 1

            # If too many consecutive errors, log critical warning
            if control_loop_state["consecutive_errors"] >= 5:
                logger.critical(f"Control loop has failed {control_loop_state['consecutive_errors']} times consecutively!")

        # Wait for configured interval before next iteration
        # Read config to get current interval (allows dynamic adjustment)
        try:
            config = thermostat_manager.get_config()
            sleep_time = config.control_interval
        except:
            sleep_time = 180  # Default to 3 minutes if config read fails

        logger.debug(f"Sleeping for {sleep_time} seconds until next control loop iteration")
        await asyncio.sleep(sleep_time)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    logger.info("Application starting up - initializing background tasks")
    asyncio.create_task(thermostat_control_loop())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Application shutting down")
    control_loop_state["running"] = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)