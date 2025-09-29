# Shelly BT Temperature Monitoring System

A simple, efficient Docker-based monitoring stack for collecting temperature and humidity data from Shelly BLU H&T sensors via HTTP polling.

## Overview

This project creates a lightweight IoT monitoring solution using:
- **Shelly Pro 2** as Bluetooth gateway
- **Shelly BLU H&T** sensors for temperature/humidity measurement
- **HTTP Polling** for simple, reliable data collection (no MQTT complexity!)
- **InfluxDB** for time-series data storage
- **FastAPI** for REST API and Prometheus metrics
- **Grafana** for visualization (user-configured)

## Architecture

```
Shelly BLU H&T Sensors (Bluetooth)
         ↓
    Shelly Pro 2 (BT Gateway)
         ↓
  HTTP Polling (every 30s)
         ↓
   Sensor Poller Service
         ↓
      InfluxDB
         ↓
    FastAPI + Prometheus
         ↓
       Grafana
```

**Simple and reliable:** No message brokers, no complex MQTT configurations, just straightforward HTTP polling.

## Hardware Requirements

- **Shelly Pro 2** (Model: SPSW-202XE12UL) - Firmware 1.6.2+
- **Shelly BLU H&T** Bluetooth temperature/humidity sensors (1 or more)
- Network connectivity for the Shelly Pro 2

## Quick Start

### 1. Pair Your Sensors

1. Pair your Shelly BLU H&T sensors with the Shelly Pro 2 using the Shelly app or web interface
2. Verify sensors are detected and named (e.g., "temp_outdoor", "temp_indoor")

### 2. Configure the Poller

Edit `sensor-poller/poller.py` to match your sensor configuration:

```python
SENSORS = [
    {
        "device_id": 200,  # Your sensor's device ID from Shelly
        "name": "temp_outdoor",
        "mac": "7c:c6:b6:ab:66:13",  # MAC address from Shelly
        # ... sensor IDs
    }
]
```

Use `./check_sensors.sh` to discover your sensor IDs and MAC addresses.

### 3. Start the Stack

```bash
# Set your Shelly IP in docker-compose.yml (default: 192.168.2.12)
docker-compose up -d
```

### 4. Verify Operation

```bash
# Check sensor health
./check_sensors.sh

# View sensor data
curl http://localhost:8001/api/v1/sensors

# Check Prometheus metrics
curl http://localhost:8001/metrics | grep sensor_temperature
```

### 5. Configure Grafana

Point Prometheus at `http://localhost:8001/metrics` and use queries like:

```promql
sensor_temperature_celsius{sensor_name="temp_outdoor"}
sensor_temperature_celsius{sensor_name="temp_indoor"}
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **sensor-poller** | - | Polls Shelly Pro 2 for sensor data every 30s |
| **influxdb** | 8086 | Time-series database |
| **api** | 8001 | REST API + Prometheus metrics |

## Configuration

### Environment Variables

Edit `docker-compose.yml` to configure:

- `SHELLY_IP`: IP address of your Shelly Pro 2 (default: 192.168.2.12)
- `POLL_INTERVAL`: Seconds between polls (default: 30)
- `INFLUXDB_*`: InfluxDB connection settings

### Sensor Configuration

Update `sensor-poller/poller.py` with your actual sensor details:
- Device IDs from Shelly
- MAC addresses
- Sensor names
- BTHome sensor component IDs

Run `./check_sensors.sh` to discover your configuration.

## Monitoring

**Check sensor health:**
```bash
./check_sensors.sh
```

Shows:
- Current temperature and humidity readings
- Battery levels
- Signal strength (RSSI)
- Last update time
- Connection status

**View logs:**
```bash
docker logs iot-sensor-poller --tail 20
docker logs iot-api --tail 20
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/sensors` - List all sensors
- `GET /api/v1/temperature` - Temperature readings
- `GET /api/v1/humidity` - Humidity readings
- `GET /api/v1/battery` - Battery levels
- `GET /metrics` - Prometheus metrics

## Troubleshooting

**Sensors not updating:**
1. Check Bluetooth range (10-30m typical)
2. Run `./check_sensors.sh` to verify connectivity
3. Check sensor batteries
4. Press sensor button to wake up

**No data in InfluxDB:**
1. Check poller logs: `docker logs iot-sensor-poller`
2. Verify Shelly IP is correct in docker-compose.yml
3. Ensure sensors are paired with Shelly Pro 2

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture and design decisions
- [check_sensors.sh](check_sensors.sh) - Sensor health check tool
- [CHANGELOG.md](CHANGELOG.md) - Version history

## Development Status

✅ **Production Ready (v2.0)**
- [x] HTTP polling implementation
- [x] Real BLU H&T sensor integration
- [x] InfluxDB time-series storage
- [x] FastAPI with Prometheus metrics
- [x] Sensor health monitoring
- [x] Complete Docker deployment
- [ ] Grafana dashboards (user-configured)

## Design Philosophy

**v2.0** adopts a **simple HTTP polling architecture** instead of MQTT:

- ✅ **Simpler**: No message broker configuration
- ✅ **More reliable**: Direct HTTP requests, no message queuing
- ✅ **Easier debugging**: Standard HTTP requests and responses
- ✅ **Less infrastructure**: Fewer services to manage

While MQTT sounds modern and scalable, for a small-scale IoT deployment with a handful of sensors, **simple HTTP polling is the pragmatic choice**.

## License

MIT License - see [LICENSE](LICENSE) for details.