# Mockup Sensor Testing

This directory contains mockup sensors that simulate Shelly BLU H&T temperature/humidity sensors for testing purposes.

## Features

The mockup sensors generate:
- **Temperature**: Sinus wave pattern from 10°C to 30°C (configurable amplitude and base)
- **Humidity**: Correlated humidity data (30-70% range)
- **Battery**: Slowly draining battery simulation (100% → 0% over time)
- **MQTT**: Publishes data in the same format as real Shelly Pro 2 BTHome events
- **Real-time Updates**: Live Prometheus metrics that update every 30 seconds
- **Grafana Compatible**: Ready for dashboard visualization

## Quick Test

1. Start MQTT broker:
   ```bash
   docker-compose up mosquitto
   ```

2. Install dependencies (if testing outside Docker):
   ```bash
   pip install paho-mqtt
   ```

3. Run the test script:
   ```bash
   python test_mockup_sensors.py
   ```

## Docker Usage

Start the full stack with mockup sensors:
```bash
# Start with mockup sensors
docker-compose --profile mockup up -d

# Or start just the core stack (without mockup sensors)
docker-compose up -d
```

## Data Format

The sensors publish BTHome events that match the real Shelly format:

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

## Sensor Configuration

Each sensor can be configured with:
- `base_temp`: Base temperature (default: 20°C)
- `temp_amplitude`: Temperature swing amplitude (default: ±10°C)
- `base_humidity`: Base humidity (default: 50%)
- `publish_interval`: How often to publish data (default: 30 seconds)

## MQTT Topics

Sensors publish to: `shellypro2-{gateway_id}/events/rpc`

Examples:
- `shellypro2-mockup01/events/rpc`
- `shellypro2-mockup02/events/rpc`

## Monitoring

You can monitor the MQTT messages using:
```bash
# Subscribe to all sensor topics
mosquitto_sub -h localhost -t "shellypro2-+/events/rpc"

# Or monitor specific sensor
mosquitto_sub -h localhost -t "shellypro2-mockup01/events/rpc"
```