#!/usr/bin/env python3
"""
Test script for mockup sensors
Run this to test the sensor simulation before using Docker
"""

import sys
import os

# Add the mockup-sensors directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'mockup-sensors'))

from sensor_simulator import SensorSimulator

def main():
    print("Testing Mockup BLU H&T Sensors")
    print("===============================")
    print("This will publish sensor data to MQTT broker on localhost:1883")
    print("Make sure your MQTT broker is running (e.g., 'docker-compose up mosquitto')")
    print("Press Ctrl+C to stop\n")

    # Create two test sensors
    sensor1 = SensorSimulator("test-sensor-01", "shellypro2-test01")
    sensor2 = SensorSimulator("test-sensor-02", "shellypro2-test02")

    # Configure different patterns
    sensor1.publish_interval = 10  # Faster publishing for testing
    sensor2.publish_interval = 15
    sensor2.base_temp = 22.0  # Different base temperature
    sensor2.temp_amplitude = 5.0  # Smaller amplitude

    import threading

    # Run sensors in separate threads
    thread1 = threading.Thread(target=sensor1.run, name="TestSensor1")
    thread2 = threading.Thread(target=sensor2.run, name="TestSensor2")

    try:
        print("Starting test sensors...")
        thread1.start()
        thread2.start()

        # Wait for both threads
        thread1.join()
        thread2.join()

    except KeyboardInterrupt:
        print("\n\nStopping test sensors...")
        sensor1.running = False
        sensor2.running = False

        thread1.join(timeout=5)
        thread2.join(timeout=5)
        print("Test complete!")

if __name__ == "__main__":
    main()