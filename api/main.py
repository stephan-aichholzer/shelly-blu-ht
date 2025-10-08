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
from pydantic import BaseModel, Field
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

tags_metadata = [
    {
        "name": "System Information",
        "description": "API metadata, health checks, and version information"
    },
    {
        "name": "Sensor Monitoring",
        "description": "Query temperature, humidity, and battery data from Shelly BLU H&T sensors"
    },
    {
        "name": "Thermostat Control",
        "description": "Configure and monitor the intelligent thermostat control system"
    },
    {
        "name": "Metrics",
        "description": "Prometheus metrics export for Grafana integration"
    }
]

app = FastAPI(
    title="Shelly BT Thermostat Control & Monitoring API",
    description="""
# IoT Temperature Monitoring & Intelligent Thermostat Control System

A production-ready REST API for monitoring Shelly BLU H&T Bluetooth temperature sensors
and controlling a heating/cooling system via Shelly Pro 2 switch with intelligent
temperature-based automation.

## System Architecture

```
Shelly BLU H&T Sensors (Bluetooth) → Shelly Pro 2 Gateway
                                           ↓
                                    HTTP Polling (30s)
                                           ↓
                                       InfluxDB
                                           ↓
                                    FastAPI + Control Loop
                                           ↓
                                    Shelly Pro 2 Switch
                                           ↓
                                    Heating/Cooling Device
```

## Key Features

- **Real-time Monitoring**: Temperature, humidity, and battery levels from multiple BLE sensors
- **Intelligent Control**: 4 operating modes (AUTO, ECO, ON, OFF) with hysteresis and timing protection
- **Temperature Averaging**: Configurable sample averaging for slow-responding thermal systems
- **Safety Mechanisms**: Minimum ON/OFF times prevent rapid cycling and equipment damage
- **Persistent Configuration**: Settings survive container restarts via JSON file storage
- **Prometheus Integration**: Full metrics export for Grafana dashboards
- **Automatic Health Monitoring**: Self-healing with Docker healthchecks

## Operating Modes

- **AUTO**: Normal operation - maintains target_temp with full control logic
- **ECO**: Energy-saving mode - maintains eco_temp (typically lower than target)
- **ON**: Manual override - forces heating/cooling ON regardless of temperature
- **OFF**: Manual override - forces heating/cooling OFF regardless of temperature

## Control Logic

The system uses **symmetric hysteresis control** to prevent oscillation:

- Turn ON when: temperature < (target - hysteresis)
- Turn OFF when: temperature >= (target + hysteresis)
- Deadband: Between thresholds, maintain current state
- Timing locks: Enforce minimum ON/OFF durations to protect equipment

Example: target=22°C, hysteresis=0.5°C
- Heating starts: < 21.5°C
- Heating stops: ≥ 22.5°C
- Deadband (21.5-22.5°C): No state change

## Background Control Loop

An async background task runs every 60-600 seconds (configurable) to:
1. Query last N temperature samples from InfluxDB
2. Calculate moving average (reduces sensor noise)
3. Apply control logic based on mode and temperature
4. Execute switch commands via Shelly RPC API
5. Log all decisions and update Prometheus metrics

## Common Workflows

### Initial Setup
1. Configure thermostat: `POST /api/v1/thermostat/config`
2. Verify configuration: `GET /api/v1/thermostat/config`
3. Monitor status: `GET /api/v1/thermostat/status`

### Temperature Monitoring
1. List sensors: `GET /api/v1/sensors`
2. Get latest readings: `GET /api/v1/latest`
3. Historical data: `GET /api/v1/temperature?start=2025-01-01T00:00:00Z`

### Grafana Integration
1. Configure Prometheus datasource pointing to `/metrics`
2. Use metrics: `thermostat_switch_state`, `thermostat_target_temperature_celsius`
3. Query sensor data: `sensor_temperature_celsius{sensor_name="temp_indoor"}`

## Hardware Requirements

- **Shelly Pro 2** (SPSW-202XE12UL): BT gateway + relay switch controller
- **Shelly BLU H&T**: 1+ Bluetooth temperature/humidity sensors
- Network connectivity for Shelly Pro 2

## Safety & Reliability

- Minimum timing constraints prevent equipment damage from rapid cycling
- Hysteresis prevents oscillation around setpoint
- Health monitoring with automatic container restart
- Configuration persisted to host filesystem
- All control decisions logged with detailed reasoning
    """,
    version="3.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "Project Repository"
    },
    license_info={
        "name": "MIT"
    }
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
    timestamp: datetime = Field(description="UTC timestamp of the reading")
    device_id: str = Field(description="Shelly device ID (e.g., '200')")
    sensor_id: Optional[str] = Field(None, description="Sensor component ID within device")
    value: float = Field(description="Measurement value (temperature in °C, humidity/battery in %)")
    unit: str = Field(description="Unit of measurement: 'celsius', 'percent'")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-08T12:30:00Z",
                "device_id": "200",
                "sensor_id": "0",
                "value": 21.5,
                "unit": "celsius"
            }
        }

class SensorInfo(BaseModel):
    device_id: str = Field(description="Shelly device ID")
    sensor_id: Optional[str] = Field(None, description="Sensor component ID")
    sensor_type: str = Field(description="Sensor type (e.g., 'bthome' for Shelly BLU H&T)")
    last_seen: Optional[datetime] = Field(None, description="UTC timestamp of last data received from sensor")
    measurements: List[str] = Field(description="Available measurement types: 'temperature', 'humidity', 'battery'")

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "200",
                "sensor_id": "0",
                "sensor_type": "bthome",
                "last_seen": "2025-10-08T12:30:00Z",
                "measurements": ["temperature", "humidity", "battery"]
            }
        }

class HealthStatus(BaseModel):
    status: str = Field(description="Overall health status: 'healthy' or 'unhealthy'")
    timestamp: datetime = Field(description="UTC timestamp of health check")
    version: str = Field(description="API version")
    influxdb_connected: bool = Field(description="True if InfluxDB is reachable and can query data")
    shelly_connected: Optional[bool] = Field(None, description="True if Shelly Pro 2 device is reachable")
    control_loop_running: Optional[bool] = Field(None, description="True if thermostat control loop background task is running")
    last_control_loop_run: Optional[datetime] = Field(None, description="UTC timestamp of last control loop execution")
    control_loop_error: Optional[str] = Field(None, description="Last error message from control loop, if any")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-08T12:30:00Z",
                "version": "2.0.0",
                "influxdb_connected": True,
                "shelly_connected": True,
                "control_loop_running": True,
                "last_control_loop_run": "2025-10-08T12:28:00Z",
                "control_loop_error": None
            }
        }

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request, call_next):
    with REQUEST_DURATION.time():
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
        response = await call_next(request)
        return response

@app.get("/", summary="API Information", tags=["System Information"])
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

@app.get("/health", response_model=HealthStatus, summary="Health Check", tags=["System Information"])
async def health_check():
    """
    Comprehensive health check endpoint that verifies all critical system components.

    Checks performed:
    - **InfluxDB Connection**: Can query time-series database
    - **Shelly Connection**: Can reach Shelly Pro 2 device
    - **Control Loop**: Background task is running and executed recently
    - **Error State**: No consecutive failures

    Returns 'healthy' status only if all components are operational.

    Used by Docker healthcheck for automatic container restart on failure.
    """
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

@app.get("/api/v1/sensors", response_model=List[SensorInfo], summary="List Sensors", tags=["Sensor Monitoring"])
async def list_sensors():
    """
    Get a list of all available Shelly BLU H&T sensors detected in the system.

    Returns sensor metadata including:
    - Device ID and sensor ID
    - Sensor type (e.g., 'bthome')
    - Last seen timestamp
    - Available measurements (temperature, humidity, battery)

    Queries the last 7 days of data to discover all active sensors.
    """
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

@app.get("/api/v1/temperature", response_model=List[SensorReading], summary="Get Temperature Data", tags=["Sensor Monitoring"])
async def get_temperature(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """
    Query historical temperature readings from InfluxDB.

    Returns temperature data sorted by timestamp (most recent first).
    Default time range is last 24 hours if no start/end specified.

    **Parameters:**
    - `device_id`: Filter by specific sensor device (e.g., "200")
    - `sensor_id`: Filter by sensor ID within device
    - `start`: Start timestamp in ISO 8601 format (e.g., "2025-01-01T00:00:00Z")
    - `end`: End timestamp in ISO 8601 format
    - `limit`: Maximum records to return (default: 1000, max: 10000)
    """
    return await get_sensor_data("temperature", device_id, sensor_id, start, end, limit)

@app.get("/api/v1/humidity", response_model=List[SensorReading], summary="Get Humidity Data", tags=["Sensor Monitoring"])
async def get_humidity(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """
    Query historical humidity readings from InfluxDB.

    Returns relative humidity percentage data sorted by timestamp (most recent first).
    Default time range is last 24 hours if no start/end specified.
    """
    return await get_sensor_data("humidity", device_id, sensor_id, start, end, limit)

@app.get("/api/v1/battery", response_model=List[SensorReading], summary="Get Battery Data", tags=["Sensor Monitoring"])
async def get_battery(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of records", le=10000)
):
    """
    Query battery level readings from Shelly BLU H&T sensors.

    Returns battery percentage (0-100%) sorted by timestamp (most recent first).
    Useful for monitoring sensor health and planning battery replacements.
    """
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

@app.get("/api/v1/latest", summary="Get Latest Readings", tags=["Sensor Monitoring"])
async def get_latest_readings():
    """
    Get the most recent readings from all sensors in a single response.

    Returns the latest temperature, humidity, and battery level for each sensor.
    Ideal for dashboard displays showing current state of all sensors.

    Queries the last hour of data to find most recent values.
    """
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

@app.get("/metrics", response_class=PlainTextResponse, summary="Prometheus Metrics", tags=["Metrics"])
async def metrics():
    """
    Prometheus metrics endpoint in text exposition format.

    Updates all gauge metrics with latest sensor and thermostat values before serving.

    **Sensor Metrics:**
    - `sensor_temperature_celsius{device_id, sensor_id, sensor_name}`: Current temperature
    - `sensor_humidity_percent{device_id, sensor_id, sensor_name}`: Current humidity
    - `sensor_battery_percent{device_id, sensor_id, sensor_name}`: Battery level

    **Thermostat Metrics:**
    - `thermostat_switch_state`: Switch state (1=ON/heating, 0=OFF)
    - `thermostat_target_temperature_celsius`: Active target temperature
    - `thermostat_current_temperature_celsius`: Current averaged indoor temperature

    **API Metrics:**
    - `api_requests_total{method, endpoint}`: Request counter
    - `api_request_duration_seconds`: Request duration histogram

    Configure Grafana to scrape this endpoint for real-time dashboards.
    """
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

@app.get(
    "/api/v1/thermostat/config",
    response_model=ThermostatConfig,
    summary="Get Thermostat Configuration",
    tags=["Thermostat Control"],
    responses={
        200: {
            "description": "Current thermostat configuration",
            "content": {
                "application/json": {
                    "example": {
                        "target_temp": 22.0,
                        "eco_temp": 18.0,
                        "mode": "AUTO",
                        "hysteresis": 0.5,
                        "min_on_time": 30,
                        "min_off_time": 10,
                        "temp_sample_count": 3,
                        "control_interval": 180
                    }
                }
            }
        }
    }
)
async def get_thermostat_config():
    """
    Retrieve the current thermostat configuration including target temperatures,
    operating mode, and control parameters.

    Configuration is persisted to `/data/thermostat_config.json` on the host and
    survives container restarts. Settings can be modified via POST to this endpoint
    or by editing the JSON file directly (requires container restart to take effect).

    **Configuration Parameters:**

    - `target_temp`: Temperature setpoint for AUTO mode (18-24°C)
    - `eco_temp`: Temperature setpoint for ECO mode (18-24°C, must be ≤ target_temp)
    - `mode`: Operating mode (AUTO/ECO/ON/OFF)
    - `hysteresis`: Symmetric deadband around target (0.1-2.0°C)
    - `min_on_time`: Minimum heating duration in minutes (1-120)
    - `min_off_time`: Minimum idle duration in minutes (1-120)
    - `temp_sample_count`: Number of samples to average (1-10, reduces noise)
    - `control_interval`: Control loop cycle time in seconds (60-600)

    **Typical Values for Different Systems:**

    - **Underfloor heating**: hysteresis=0.5°C, min_on_time=30min, samples=3-5
    - **Radiators**: hysteresis=0.3°C, min_on_time=15min, samples=2-3
    - **Fan heaters**: hysteresis=0.2°C, min_on_time=5min, samples=1-2
    """
    return thermostat_manager.get_config()

@app.post(
    "/api/v1/thermostat/config",
    response_model=ThermostatConfig,
    summary="Update Thermostat Configuration",
    tags=["Thermostat Control"],
    responses={
        200: {
            "description": "Configuration updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "target_temp": 22.0,
                        "eco_temp": 18.0,
                        "mode": "AUTO",
                        "hysteresis": 0.5,
                        "min_on_time": 30,
                        "min_off_time": 10,
                        "temp_sample_count": 3,
                        "control_interval": 180
                    }
                }
            }
        },
        422: {
            "description": "Validation error (e.g., eco_temp > target_temp)"
        },
        500: {
            "description": "Error saving configuration to file"
        }
    }
)
async def set_thermostat_config(config: ThermostatConfig):
    """
    Update thermostat configuration and persist to file.

    The new configuration is:
    1. Validated by Pydantic (all range checks, eco_temp ≤ target_temp)
    2. Written to `/data/thermostat_config.json` on the host
    3. Applied immediately to the control loop (no restart needed)
    4. Returned in the response for confirmation

    **Common Use Cases:**

    - Change mode: `{"mode": "ECO"}` (switch to energy-saving mode)
    - Adjust target: `{"target_temp": 23.0}` (increase comfort temperature)
    - Fine-tune control: `{"hysteresis": 0.3, "min_on_time": 20}` (faster response)
    - Override manual: `{"mode": "OFF"}` (disable heating completely)

    **Validation Rules:**

    - `target_temp`: 18-24°C
    - `eco_temp`: 18-24°C and ≤ target_temp
    - `hysteresis`: 0.1-2.0°C
    - `min_on_time`, `min_off_time`: 1-120 minutes
    - `temp_sample_count`: 1-10 samples
    - `control_interval`: 60-600 seconds

    Changes take effect on the next control loop iteration (typically within 3 minutes).
    """
    try:
        thermostat_manager.set_config(config)
        return thermostat_manager.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")

@app.get(
    "/api/v1/thermostat/status",
    response_model=ThermostatStatus,
    summary="Get Comprehensive Thermostat Status",
    tags=["Thermostat Control"],
    responses={
        200: {
            "description": "Complete thermostat status",
            "content": {
                "application/json": {
                    "example": {
                        "config": {
                            "target_temp": 22.0,
                            "eco_temp": 18.0,
                            "mode": "AUTO",
                            "hysteresis": 0.5,
                            "min_on_time": 30,
                            "min_off_time": 10,
                            "temp_sample_count": 3,
                            "control_interval": 180
                        },
                        "current_temp": 21.2,
                        "all_temps": {
                            "temp_outdoor": 15.3,
                            "temp_indoor": 21.2,
                            "temp_buffer": 19.8
                        },
                        "switch_state": True,
                        "active_target": 22.0,
                        "heating_needed": True,
                        "reason": "Heating: 21.2°C < 21.5°C (already ON, running 15/30min)",
                        "switch_locked_until": "2025-10-08T12:45:00Z"
                    }
                }
            }
        },
        503: {
            "description": "Shelly device unreachable",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cannot reach Shelly device: Connection timeout"
                    }
                }
            }
        }
    }
)
async def get_thermostat_status():
    """
    Get a complete snapshot of the thermostat system state.

    Returns comprehensive information including:
    - Current configuration (all settings)
    - All sensor temperatures (outdoor, indoor, buffer)
    - Current switch state (ON/OFF)
    - Control decision and detailed reasoning
    - Timing lock status (if applicable)

    **Use Cases:**

    - **Dashboard display**: Shows current state and all temperatures
    - **Troubleshooting**: Understand why heating is or isn't running
    - **Timing verification**: Check if switch is locked by min_on_time/min_off_time
    - **Mode verification**: Confirm which mode is active and target temperature

    **Control Decision Reasoning Examples:**

    - `"Turning ON: 21.2°C < 21.5°C (OFF for 15min >= 10min)"` - Temperature below threshold, off long enough, starting heat
    - `"Heating needed but locked OFF (idle 5/10min, 5min remaining)"` - Wants to heat but still locked
    - `"Temperature 21.8°C in deadband [21.5°C - 22.5°C], maintaining ON"` - In deadband, keeping current state
    - `"Manual override: Switch forced ON"` - Mode=ON, manual control active

    **Performance:**
    Queries InfluxDB for latest sensor data (5min window) and Shelly for switch status.
    Typical response time: 50-150ms.
    """
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

@app.post(
    "/api/v1/thermostat/switch",
    summary="Manual Switch Control",
    tags=["Thermostat Control"],
    responses={
        200: {
            "description": "Switch control successful",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "switch_on": True,
                        "shelly_response": {"was_on": False},
                        "note": "Switch set manually - will be controlled by configured mode on next cycle"
                    }
                }
            }
        },
        503: {
            "description": "Cannot reach Shelly device"
        }
    }
)
async def control_switch(turn_on: bool):
    """
    Manually control the Shelly Pro 2 switch (temporary override).

    **Important Behavior:**
    - This endpoint provides **temporary** manual control
    - Does NOT change the operating mode
    - The control loop will override this on its next cycle (typically 3 minutes)
    - For permanent manual control, use `POST /api/v1/thermostat/config` with mode=ON or mode=OFF

    **Use Cases:**
    - Quick testing of switch control
    - Emergency manual override
    - Temporary adjustments without changing mode

    **Parameters:**
    - `turn_on`: Boolean - true to turn switch ON (heating), false to turn OFF

    **Example:**
    ```
    curl -X POST "http://localhost:8001/api/v1/thermostat/switch?turn_on=true"
    ```

    **For Permanent Control:**
    To force heating ON permanently: `POST /api/v1/thermostat/config` with `{"mode": "ON"}`
    To disable heating permanently: `POST /api/v1/thermostat/config` with `{"mode": "OFF"}`
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

            # Detect mode changes
            if control_loop_state["last_mode"] != config.mode:
                logger.info(f"Mode changed to {config.mode.value}")
                control_loop_state["last_mode"] = config.mode
                control_loop_state["mode_action_done"] = False  # Reset flag on mode change

            # Handle ON mode - turn switch ON once, then just monitor
            if config.mode == ThermostatMode.ON:
                switch_status = shelly_controller.get_switch_status()
                current_switch_on = switch_status.get("output", False)

                if not control_loop_state["mode_action_done"]:
                    logger.info("Entering ON mode - turning switch ON once")
                    try:
                        result = shelly_controller.set_switch(True)
                        await asyncio.sleep(0.2)
                        verify_status = shelly_controller.get_switch_status()
                        if verify_status.get("output") is True:
                            thermostat_manager.update_state(True, "Manual mode: ON")
                            THERMOSTAT_SWITCH_STATE.set(1)
                            control_loop_state["mode_action_done"] = True
                            logger.info("Switch successfully set to ON")
                    except Exception as e:
                        logger.error(f"Error forcing switch ON: {e}")
                else:
                    # Just monitor and log
                    logger.info(f"Mode=ON, Switch={'ON' if current_switch_on else 'OFF'} - no action (manual mode)")

            # Handle OFF mode - turn switch OFF once, then just monitor
            elif config.mode == ThermostatMode.OFF:
                switch_status = shelly_controller.get_switch_status()
                current_switch_on = switch_status.get("output", False)

                if not control_loop_state["mode_action_done"]:
                    logger.info("Entering OFF mode - turning switch OFF once")
                    try:
                        result = shelly_controller.set_switch(False)
                        await asyncio.sleep(0.2)
                        verify_status = shelly_controller.get_switch_status()
                        if verify_status.get("output") is False:
                            thermostat_manager.update_state(False, "Manual mode: OFF")
                            THERMOSTAT_SWITCH_STATE.set(0)
                            control_loop_state["mode_action_done"] = True
                            logger.info("Switch successfully set to OFF")
                    except Exception as e:
                        logger.error(f"Error forcing switch OFF: {e}")
                else:
                    # Just monitor and log - detect manual override
                    if current_switch_on:
                        logger.info(f"Mode=OFF, Switch=ON - manual override detected, ignoring")
                    else:
                        logger.info(f"Mode=OFF, Switch=OFF - no action (manual mode)")

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
                  |> sort(columns: ["_time"], desc: false)
                '''

                temp_result = query_api.query(temp_query, org=INFLUXDB_ORG)
                temps = []
                timestamps = []

                for table in temp_result:
                    for record in table.records:
                        temps.append(record.get_value())
                        timestamps.append(record.get_time())

                # Average the samples (or fewer if not enough data yet)
                indoor_temp = sum(temps) / len(temps) if temps else None

                if indoor_temp and len(temps) > 1:
                    # Log with timestamps for debugging
                    temp_with_time = [f"{t.strftime('%H:%M:%S')}={v:.1f}" for t, v in zip(timestamps, temps)]
                    logger.info(f"Averaging {len(temps)} temperature samples: {temp_with_time} -> {indoor_temp:.2f}°C")

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

                    logger.info(f"Mode={config.mode.value}, Temp={indoor_temp:.1f}°C, Control decision: {reason}")

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