"""
Data models module
All Pydantic models for API request/response validation
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


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
