#!/usr/bin/env python3
"""
IoT Data Collector Service
Collects sensor data from MQTT and stores in InfluxDB
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt
import yaml
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from pythonjsonlogger import jsonlogger
from tenacity import retry, stop_after_attempt, wait_exponential


class DataCollector:
    def __init__(self, config_path: str = "/app/config.yaml"):
        self.config = self._load_config(config_path)
        self.setup_logging()
        self.logger = logging.getLogger(__name__)

        self.mqtt_client = None
        self.influx_client = None
        self.write_api = None
        self.running = True

        # Statistics
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_failed": 0,
            "last_message_time": None
        }

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            # Fallback to environment variables
            return {
                "mqtt": {
                    "broker": os.getenv("MQTT_BROKER", "mosquitto"),
                    "port": int(os.getenv("MQTT_PORT", "1883")),
                    "topics": ["shellypro2-+/events/rpc"],
                    "qos": 1
                },
                "influxdb": {
                    "url": os.getenv("INFLUXDB_URL", "http://influxdb:8086"),
                    "token": os.getenv("INFLUXDB_TOKEN", "iot-admin-token-12345"),
                    "org": os.getenv("INFLUXDB_ORG", "iot-org"),
                    "bucket": os.getenv("INFLUXDB_BUCKET", "sensor-data")
                },
                "logging": {"level": "INFO"}
            }

    def setup_logging(self):
        """Configure structured logging"""
        log_level = self.config.get("logging", {}).get("level", "INFO")

        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_level))

        handler = logging.StreamHandler(sys.stdout)

        if self.config.get("logging", {}).get("format") == "json":
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def connect_influxdb(self):
        """Connect to InfluxDB with retry logic"""
        self.logger.info("Connecting to InfluxDB...")

        influx_config = self.config["influxdb"]
        self.influx_client = InfluxDBClient(
            url=influx_config["url"],
            token=influx_config["token"],
            org=influx_config["org"],
            timeout=influx_config.get("timeout", 10) * 1000  # Convert to milliseconds
        )

        # Test connection
        try:
            # Simple ping to test connection
            health = self.influx_client.ping()
            self.logger.info(f"Connected to InfluxDB successfully, health: {health}")
        except Exception as e:
            self.logger.error(f"InfluxDB connection test failed: {e}")
            raise

        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            # Subscribe to topics
            for topic in self.config["mqtt"]["topics"]:
                try:
                    self.logger.info(f"Attempting to subscribe to topic: '{topic}'")
                    result = client.subscribe(topic, self.config["mqtt"]["qos"])
                    self.logger.info(f"Subscribed to topic: {topic}, result: {result}")
                except Exception as e:
                    self.logger.error(f"Failed to subscribe to topic '{topic}': {e}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = datetime.utcnow()

            topic = msg.topic
            payload = msg.payload.decode('utf-8')

            self.logger.debug(f"Received message on topic {topic}: {payload}")

            # Parse and process the message
            self.process_message(topic, payload)

            self.stats["messages_processed"] += 1

        except Exception as e:
            self.stats["messages_failed"] += 1
            self.logger.error(f"Error processing message: {e}", extra={
                "topic": msg.topic,
                "payload": msg.payload.decode('utf-8', errors='ignore')
            })

    def process_message(self, topic: str, payload: str):
        """Process and store sensor data"""
        try:
            data = json.loads(payload)

            # Extract device ID from topic
            device_id = self.extract_device_id(topic)
            if not device_id:
                self.logger.warning(f"Could not extract device ID from topic: {topic}")
                return

            # Process different message types
            if "events/rpc" in topic:
                self.process_rpc_event(device_id, data)
            elif "online" in topic:
                self.process_status_event(device_id, data)
            elif "info" in topic:
                self.process_sensor_data(device_id, data)

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def extract_device_id(self, topic: str) -> Optional[str]:
        """Extract device ID from MQTT topic"""
        parts = topic.split('/')
        if len(parts) >= 1:
            return parts[0]  # e.g., "shellypro2-8813bfddbfe8"
        return None

    def process_rpc_event(self, device_id: str, data: Dict[str, Any]):
        """Process RPC events (BTHome sensor data)"""
        if "params" in data:
            params = data["params"]
            if "events" in params:
                for event in params["events"]:
                    if event.get("component") == "bthomesensor":
                        self.store_bthome_data(device_id, event)

    def process_sensor_data(self, device_id: str, data: Dict[str, Any]):
        """Process direct sensor data"""
        # Handle Shelly BLU H&T sensor data
        timestamp = datetime.utcnow()

        points = []

        # Temperature
        if "temperature:0" in data:
            temp_data = data["temperature:0"]
            if "tC" in temp_data:
                points.append(
                    Point("temperature")
                    .tag("device_id", device_id)
                    .tag("sensor_type", "blu_ht")
                    .field("value", temp_data["tC"])
                    .time(timestamp)
                )

        # Humidity
        if "humidity:0" in data:
            hum_data = data["humidity:0"]
            if "rh" in hum_data:
                points.append(
                    Point("humidity")
                    .tag("device_id", device_id)
                    .tag("sensor_type", "blu_ht")
                    .field("value", hum_data["rh"])
                    .time(timestamp)
                )

        # Battery
        if "devicepower:0" in data:
            bat_data = data["devicepower:0"]
            if "battery" in bat_data:
                points.append(
                    Point("battery")
                    .tag("device_id", device_id)
                    .tag("sensor_type", "blu_ht")
                    .field("level", bat_data["battery"]["percent"])
                    .field("voltage", bat_data["battery"]["V"])
                    .time(timestamp)
                )

        if points:
            self.write_points(points)

    def store_bthome_data(self, gateway_id: str, event: Dict[str, Any]):
        """Store BTHome sensor data to InfluxDB"""
        try:
            sensor_id = event.get("id", "unknown")
            data = event.get("data", {})
            timestamp = datetime.utcnow()

            points = []

            # Temperature
            if "temperature" in data:
                points.append(
                    Point("temperature")
                    .tag("gateway_id", gateway_id)
                    .tag("sensor_id", sensor_id)
                    .tag("sensor_type", "bthome")
                    .field("value", data["temperature"])
                    .time(timestamp)
                )

            # Humidity
            if "humidity" in data:
                points.append(
                    Point("humidity")
                    .tag("gateway_id", gateway_id)
                    .tag("sensor_id", sensor_id)
                    .tag("sensor_type", "bthome")
                    .field("value", data["humidity"])
                    .time(timestamp)
                )

            # Battery
            if "battery" in data:
                points.append(
                    Point("battery")
                    .tag("gateway_id", gateway_id)
                    .tag("sensor_id", sensor_id)
                    .tag("sensor_type", "bthome")
                    .field("level", data["battery"])
                    .time(timestamp)
                )

            if points:
                self.write_points(points)
                self.logger.info(f"Stored {len(points)} data points for sensor {sensor_id}")

        except Exception as e:
            self.logger.error(f"Error storing BTHome data: {e}")

    def process_status_event(self, device_id: str, data: Dict[str, Any]):
        """Process device status events"""
        timestamp = datetime.utcnow()

        point = (
            Point("device_status")
            .tag("device_id", device_id)
            .field("online", data.get("online", False))
            .time(timestamp)
        )

        self.write_points([point])

    def write_points(self, points: list):
        """Write data points to InfluxDB"""
        try:
            self.write_api.write(
                bucket=self.config["influxdb"]["bucket"],
                org=self.config["influxdb"]["org"],
                record=points
            )
        except Exception as e:
            self.logger.error(f"Error writing to InfluxDB: {e}")
            raise

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        self.logger.info("Connecting to MQTT broker...")

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        mqtt_config = self.config["mqtt"]
        self.mqtt_client.connect(
            mqtt_config["broker"],
            mqtt_config["port"],
            mqtt_config.get("keepalive", 60)
        )

    def run(self):
        """Main run loop"""
        self.logger.info("Starting IoT Data Collector...")

        try:
            # Connect to services
            self.connect_influxdb()
            self.connect_mqtt()

            # Start MQTT loop
            self.mqtt_client.loop_start()

            # Statistics logging
            last_stats_time = time.time()

            while self.running:
                time.sleep(1)

                # Log statistics every minute
                if time.time() - last_stats_time > 60:
                    self.logger.info("Statistics", extra=self.stats)
                    last_stats_time = time.time()

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Shutting down...")
        self.running = False

        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

        if self.influx_client:
            self.influx_client.close()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}")
        self.running = False


def main():
    collector = DataCollector()

    # Setup signal handlers
    signal.signal(signal.SIGTERM, collector.signal_handler)
    signal.signal(signal.SIGINT, collector.signal_handler)

    collector.run()


if __name__ == "__main__":
    main()