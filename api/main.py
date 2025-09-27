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

# Prometheus metrics
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'API request duration')
SENSOR_TEMPERATURE = Gauge('sensor_temperature_celsius', 'Current temperature', ['device_id', 'sensor_id'])
SENSOR_HUMIDITY = Gauge('sensor_humidity_percent', 'Current humidity', ['device_id', 'sensor_id'])
SENSOR_BATTERY = Gauge('sensor_battery_percent', 'Current battery level', ['device_id', 'sensor_id'])
SENSOR_LAST_SEEN = Gauge('sensor_last_seen_timestamp', 'Last seen timestamp', ['device_id', 'sensor_id'])

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
        "version": "1.0.0",
        "endpoints": {
            "sensors": "/api/v1/sensors",
            "temperature": "/api/v1/temperature",
            "humidity": "/api/v1/humidity",
            "battery": "/api/v1/battery",
            "metrics": "/metrics",
            "health": "/health"
        }
    }

@app.get("/health", response_model=HealthStatus, summary="Health Check")
async def health_check():
    """Health check endpoint"""
    try:
        # Test InfluxDB connection
        buckets = influx_client.buckets_api().find_buckets()
        influxdb_connected = True
    except Exception:
        influxdb_connected = False

    return HealthStatus(
        status="healthy" if influxdb_connected else "unhealthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        influxdb_connected=influxdb_connected
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
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)