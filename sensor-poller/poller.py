#!/usr/bin/env python3
"""
Simple Shelly BLU H&T Sensor Poller
Polls sensors via HTTP and writes directly to InfluxDB
"""

import os
import time
import logging
import requests
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
SHELLY_IP = os.getenv("SHELLY_IP", "192.168.2.12")
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "iot-admin-token-12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor-data")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))  # seconds

# Sensor configuration
SENSORS = [
    {
        "device_id": 200,
        "name": "temp_outdoor",
        "mac": "7c:c6:b6:ab:66:13",
        "battery_sensor_id": 200,
        "humidity_sensor_id": 201,
        "temperature_sensor_id": 202
    },
    {
        "device_id": 201,
        "name": "temp_indoor",
        "mac": "94:b2:16:0b:88:01",
        "battery_sensor_id": 203,
        "humidity_sensor_id": 204,
        "temperature_sensor_id": 205
    }
]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SensorPoller:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 5

        # Connect to InfluxDB
        self.influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        logger.info("Connected to InfluxDB")

    def get_sensor_value(self, sensor_id):
        """Get a sensor value from Shelly"""
        try:
            url = f"http://{SHELLY_IP}/rpc/BTHomeSensor.GetStatus?id={sensor_id}"
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("value")
        except Exception as e:
            logger.error(f"Error reading sensor {sensor_id}: {e}")
            return None

    def get_device_status(self, device_id):
        """Get device status (RSSI, battery) from Shelly"""
        try:
            url = f"http://{SHELLY_IP}/rpc/BTHomeDevice.GetStatus?id={device_id}"
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return {
                "rssi": data.get("rssi"),
                "battery": data.get("battery"),
                "paired": data.get("paired", False)
            }
        except Exception as e:
            logger.error(f"Error reading device {device_id}: {e}")
            return None

    def poll_sensor(self, sensor_config):
        """Poll a single sensor and return data"""
        logger.info(f"Polling sensor: {sensor_config['name']}")

        # Get sensor readings
        temperature = self.get_sensor_value(sensor_config["temperature_sensor_id"])
        humidity = self.get_sensor_value(sensor_config["humidity_sensor_id"])
        battery = self.get_sensor_value(sensor_config["battery_sensor_id"])

        # Get device status
        device_status = self.get_device_status(sensor_config["device_id"])

        if device_status and not device_status["paired"]:
            logger.warning(f"Sensor {sensor_config['name']} is not paired!")
            return None

        sensor_data = {
            "temperature": temperature,
            "humidity": humidity,
            "battery": battery,
            "rssi": device_status.get("rssi") if device_status else None
        }

        logger.info(f"{sensor_config['name']}: Temp={temperature}°C, Humidity={humidity}%, Battery={battery}%")
        return sensor_data

    def write_to_influxdb(self, sensor_config, sensor_data, timestamp):
        """Write sensor data to InfluxDB"""
        points = []
        gateway_id = "shellypro2-8813bfddbfe8"
        sensor_id = sensor_config["mac"]

        # Temperature
        if sensor_data["temperature"] is not None:
            points.append(
                Point("temperature")
                .tag("gateway_id", gateway_id)
                .tag("sensor_id", sensor_id)
                .tag("sensor_type", "bthome")
                .tag("sensor_name", sensor_config["name"])
                .field("value", sensor_data["temperature"])
                .time(timestamp)
            )

        # Humidity
        if sensor_data["humidity"] is not None:
            points.append(
                Point("humidity")
                .tag("gateway_id", gateway_id)
                .tag("sensor_id", sensor_id)
                .tag("sensor_type", "bthome")
                .tag("sensor_name", sensor_config["name"])
                .field("value", float(sensor_data["humidity"]))
                .time(timestamp)
            )

        # Battery
        if sensor_data["battery"] is not None:
            points.append(
                Point("battery")
                .tag("gateway_id", gateway_id)
                .tag("sensor_id", sensor_id)
                .tag("sensor_type", "bthome")
                .tag("sensor_name", sensor_config["name"])
                .field("level", sensor_data["battery"])
                .time(timestamp)
            )

        if points:
            try:
                self.write_api.write(
                    bucket=INFLUXDB_BUCKET,
                    org=INFLUXDB_ORG,
                    record=points
                )
                logger.info(f"Wrote {len(points)} data points for {sensor_config['name']}")
            except Exception as e:
                logger.error(f"Error writing to InfluxDB: {e}")

    def poll_all_sensors(self):
        """Poll all configured sensors"""
        timestamp = datetime.utcnow()

        for sensor_config in SENSORS:
            try:
                sensor_data = self.poll_sensor(sensor_config)
                if sensor_data:
                    self.write_to_influxdb(sensor_config, sensor_data, timestamp)
            except Exception as e:
                logger.error(f"Error processing sensor {sensor_config['name']}: {e}")

    def run(self):
        """Main run loop"""
        logger.info(f"Starting sensor poller (interval: {POLL_INTERVAL}s)")
        logger.info(f"Shelly IP: {SHELLY_IP}")
        logger.info(f"Monitoring {len(SENSORS)} sensors")

        while True:
            try:
                self.poll_all_sensors()
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poller = SensorPoller()
    poller.run()