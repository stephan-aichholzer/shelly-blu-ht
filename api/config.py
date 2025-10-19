"""
Configuration module
Centralized configuration and environment variables
"""
import os

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "iot-admin-token-12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor-data")

# API Configuration
API_VERSION = "3.0.0"
API_TITLE = "Shelly BT Thermostat Control & Monitoring API"
