#!/usr/bin/env python3
"""
Mockup BLU H&T Sensor Simulator
Generates realistic temperature/humidity data and publishes via MQTT
"""

import json
import logging
import math
import time
import random
from datetime import datetime
from typing import Dict, Any
import os

import paho.mqtt.client as mqtt


class SensorSimulator:
    def __init__(self, sensor_id: str, gateway_id: str = "shellypro2-mockup"):
        self.sensor_id = sensor_id
        self.gateway_id = gateway_id
        self.mqtt_client = None
        self.running = True

        # MQTT Configuration
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

        # Sensor parameters
        self.base_temp = 20.0  # Base temperature (20°C)
        self.temp_amplitude = 10.0  # Temperature swing (-10 to +10°C)
        self.base_humidity = 50.0  # Base humidity (50%)
        self.humidity_amplitude = 20.0  # Humidity swing (30-70%)

        # Battery simulation
        self.battery_level = 100.0
        self.battery_drain_rate = 0.01  # % per hour

        # Timing
        self.start_time = time.time()
        self.publish_interval = 30  # seconds

        self.setup_logging()

    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"MockSensor-{self.sensor_id}")

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        self.logger.info(f"Connecting to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect

        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT: {e}")
            return False

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.logger.info("Disconnected from MQTT broker")

    def generate_temperature(self) -> float:
        """Generate sinus wave temperature data (-10 to +10°C per hour)"""
        elapsed_hours = (time.time() - self.start_time) / 3600.0

        # Main sinus wave (1 cycle per hour)
        temp_wave = math.sin(2 * math.pi * elapsed_hours)

        # Add some noise
        noise = random.uniform(-0.5, 0.5)

        # Calculate final temperature
        temperature = self.base_temp + (self.temp_amplitude * temp_wave) + noise

        return round(temperature, 1)

    def generate_humidity(self, temperature: float) -> float:
        """Generate humidity data with slight correlation to temperature"""
        elapsed_hours = (time.time() - self.start_time) / 3600.0

        # Humidity tends to be inversely related to temperature
        # Use a different phase for humidity
        humidity_wave = math.sin(2 * math.pi * elapsed_hours + math.pi/3)

        # Slight inverse correlation with temperature
        temp_influence = (temperature - self.base_temp) * -0.5

        # Add some noise
        noise = random.uniform(-2, 2)

        # Calculate final humidity
        humidity = self.base_humidity + (self.humidity_amplitude * humidity_wave) + temp_influence + noise

        # Clamp to realistic range
        humidity = max(10.0, min(90.0, humidity))

        return round(humidity, 1)

    def update_battery(self):
        """Update battery level (slowly draining)"""
        elapsed_hours = (time.time() - self.start_time) / 3600.0
        self.battery_level = max(0.0, 100.0 - (elapsed_hours * self.battery_drain_rate))

    def create_bthome_message(self) -> Dict[str, Any]:
        """Create BTHome message in the format expected by the collector"""
        temperature = self.generate_temperature()
        humidity = self.generate_humidity(temperature)
        self.update_battery()

        # Create message in the same format as real Shelly Pro 2 BTHome events
        message = {
            "src": "shellypro2",
            "dst": "user_1",
            "method": "NotifyEvent",
            "params": {
                "ts": time.time(),
                "events": [
                    {
                        "component": "bthomesensor",
                        "id": self.sensor_id,
                        "event": "data",
                        "data": {
                            "temperature": temperature,
                            "humidity": humidity,
                            "battery": int(self.battery_level),
                            "rssi": random.randint(-70, -40)  # Signal strength
                        }
                    }
                ]
            }
        }

        return message

    def publish_data(self):
        """Publish sensor data to MQTT"""
        if not self.mqtt_client:
            return

        try:
            message = self.create_bthome_message()
            topic = f"{self.gateway_id}/events/rpc"

            payload = json.dumps(message)
            result = self.mqtt_client.publish(topic, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                temp = message["params"]["events"][0]["data"]["temperature"]
                humidity = message["params"]["events"][0]["data"]["humidity"]
                battery = message["params"]["events"][0]["data"]["battery"]

                self.logger.info(f"Published data - Temp: {temp}°C, Humidity: {humidity}%, Battery: {battery}%")
            else:
                self.logger.error(f"Failed to publish message, return code: {result.rc}")

        except Exception as e:
            self.logger.error(f"Error publishing data: {e}")

    def run(self):
        """Main simulation loop"""
        self.logger.info(f"Starting sensor simulation for {self.sensor_id}")

        if not self.connect_mqtt():
            return

        try:
            while self.running:
                self.publish_data()
                time.sleep(self.publish_interval)

        except KeyboardInterrupt:
            self.logger.info("Simulation stopped by user")
        except Exception as e:
            self.logger.error(f"Simulation error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.logger.info("Simulation cleanup complete")


def main():
    """Run two mockup sensors"""
    import threading

    # Create two sensor simulators
    sensor1 = SensorSimulator("mockup-sensor-01", "shellypro2-mockup01")
    sensor2 = SensorSimulator("mockup-sensor-02", "shellypro2-mockup02")

    # Different temperature patterns for each sensor
    sensor2.base_temp = 18.0  # Slightly cooler base temperature
    sensor2.temp_amplitude = 8.0  # Smaller temperature swing
    sensor2.start_time = time.time() + 1800  # 30 minute phase shift

    # Run sensors in separate threads
    thread1 = threading.Thread(target=sensor1.run, name="Sensor1")
    thread2 = threading.Thread(target=sensor2.run, name="Sensor2")

    try:
        thread1.start()
        thread2.start()

        # Wait for both threads
        thread1.join()
        thread2.join()

    except KeyboardInterrupt:
        print("\nShutting down sensors...")
        sensor1.running = False
        sensor2.running = False

        thread1.join(timeout=5)
        thread2.join(timeout=5)


if __name__ == "__main__":
    main()