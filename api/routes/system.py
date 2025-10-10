"""
System routes
Health checks, API information, and Prometheus metrics
"""
from datetime import datetime
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from config import API_VERSION, INFLUXDB_BUCKET, INFLUXDB_ORG
from models import HealthStatus
from database import influx_client, query_api
from metrics import (
    SENSOR_TEMPERATURE, SENSOR_HUMIDITY, SENSOR_BATTERY,
    SENSOR_LAST_SEEN
)

router = APIRouter()


@router.get("/", summary="API Information", tags=["System Information"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "IoT Temperature Monitoring API",
        "version": API_VERSION,
        "endpoints": {
            "sensors": "/api/v1/sensors",
            "temperature": "/api/v1/temperature",
            "humidity": "/api/v1/humidity",
            "battery": "/api/v1/battery",
            "latest": "/api/v1/latest",
            "thermostat_config": "/api/v1/thermostat/config",
            "thermostat_status": "/api/v1/thermostat/status",
            "thermostat_switch": "/api/v1/thermostat/switch",
            "monitor": "/monitor",
            "metrics": "/metrics",
            "health": "/health",
            "docs": "/docs"
        }
    }


@router.get("/health", response_model=HealthStatus, summary="Health Check", tags=["System Information"])
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
        version=API_VERSION,
        influxdb_connected=influxdb_connected,
        shelly_connected=shelly_connected,
        control_loop_running=control_loop_running,
        last_control_loop_run=last_run,
        control_loop_error=error
    )


@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus Metrics", tags=["Metrics"])
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
                timestamp = record.get_time().timestamp()

                SENSOR_BATTERY.labels(
                    device_id=gateway_id,
                    sensor_id=sensor_id,
                    sensor_name=sensor_name
                ).set(value)

                SENSOR_LAST_SEEN.labels(
                    device_id=gateway_id,
                    sensor_id=sensor_id,
                    sensor_name=sensor_name
                ).set(timestamp)

    except Exception as e:
        # Don't fail metrics endpoint if update fails
        import logging
        logging.getLogger(__name__).error(f"Error updating Prometheus metrics: {e}")
