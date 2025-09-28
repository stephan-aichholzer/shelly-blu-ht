# Testing Environment Setup

## Overview

This document describes the testing environment setup for the Shelly BT Temperature Monitoring System, including mockup sensors for testing without real hardware.

## Environment Structure

```
shelly_bt_temp/
├── venv/                       # Python virtual environment for testing
├── mockup-sensors/             # Mockup sensor implementation
│   ├── sensor_simulator.py     # Main sensor simulation code
│   └── Dockerfile             # Docker container for sensors
├── collector/                  # Data collector service
├── api/                       # REST API service
├── test_mockup_sensors.py     # Test script for local testing
└── docker-compose.yml         # Full stack orchestration
```

## Virtual Environment

The project uses a Python virtual environment for local testing:

```bash
# Created with:
python3 -m venv venv

# Activate:
source venv/bin/activate

# Dependencies installed:
pip install paho-mqtt
```

## Testing Options

### 1. Local Testing (Recommended for Development)

Test sensors locally with MQTT broker in Docker:

```bash
# Start MQTT broker only
docker-compose up -d mosquitto

# Activate virtual environment
source venv/bin/activate

# Run test sensors
python test_mockup_sensors.py
```

### 2. Full Docker Stack Testing

Test complete integration with all services:

```bash
# Start full stack with mockup sensors
docker-compose --profile mockup up -d

# Start full stack without mockup sensors (for real hardware)
docker-compose up -d
```

## Mockup Sensor Features

- **2 simulated BLU H&T sensors** with different patterns
- **Sinus wave temperature**: -10°C to +30°C over 1-hour cycles
- **Correlated humidity**: 30-70% range with temperature inverse correlation
- **Battery simulation**: Slowly draining from 100% to 0%
- **Realistic timing**: 30-second publish intervals (configurable)
- **Proper MQTT format**: Matches real Shelly Pro 2 BTHome events

## Data Flow

```
Mockup Sensors → MQTT → Data Collector → InfluxDB → Grafana/API
```

## Service Endpoints

- **MQTT Broker**: localhost:1883
- **InfluxDB**: localhost:8086
- **API**: localhost:8001
- **Grafana**: (not yet configured)

## Docker Profiles

The `docker-compose.yml` uses profiles to control which services start:

- **Default profile**: Core services (MQTT, InfluxDB, Collector, API)
- **Mockup profile**: Adds mockup sensors for testing

## Monitoring Commands

```bash
# View sensor logs
docker logs iot-mockup-sensors --tail 20

# View collector logs
docker logs iot-collector --tail 20

# Monitor MQTT messages (requires mosquitto-clients)
docker exec iot-mosquitto mosquitto_sub -h localhost -t "shellypro2-mockup01/events/rpc"

# Check container status
docker-compose ps
```

## Environment Variables

Key environment variables for testing:

```bash
# MQTT Configuration
MQTT_BROKER=mosquitto
MQTT_PORT=1883

# InfluxDB Configuration
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=iot-admin-token-12345
INFLUXDB_ORG=iot-org
INFLUXDB_BUCKET=sensor-data
```

## Sensor Data Format

The mockup sensors publish BTHome events in this format:

```json
{
  "src": "shellypro2",
  "dst": "user_1",
  "method": "NotifyEvent",
  "params": {
    "ts": 1699123456.789,
    "events": [
      {
        "component": "bthomesensor",
        "id": "mockup-sensor-01",
        "event": "data",
        "data": {
          "temperature": 25.3,
          "humidity": 45.2,
          "battery": 98,
          "rssi": -55
        }
      }
    ]
  }
}
```

## Troubleshooting

### Common Issues

1. **MQTT Connection Failed**: Ensure mosquitto container is running
2. **Permission Denied**: Check virtual environment activation
3. **InfluxDB Connection**: Wait for InfluxDB to fully initialize (30-60 seconds)
4. **Port Conflicts**: Ensure ports 1883, 8086, 8001 are available

### Useful Commands

```bash
# Restart specific service
docker-compose restart collector

# View all logs
docker-compose logs -f

# Clean rebuild
docker-compose down && docker-compose --profile mockup up --build -d

# Test MQTT connectivity
source venv/bin/activate && python -c "import paho.mqtt.client as mqtt; c = mqtt.Client(); c.connect('localhost', 1883, 60); print('MQTT OK')"
```