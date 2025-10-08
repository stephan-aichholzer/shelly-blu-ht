# Shelly BT Temperature Monitoring & Thermostat Control System

A simple, efficient Docker-based monitoring stack with intelligent thermostat control for Shelly BLU H&T sensors via HTTP polling.

## Overview

This project creates a complete IoT solution featuring:
- **Shelly Pro 2** as Bluetooth gateway and switch controller
- **Shelly BLU H&T** sensors for temperature/humidity measurement
- **Intelligent Thermostat** with temperature averaging and timing control
- **HTTP Polling** for simple, reliable data collection (no MQTT complexity!)
- **InfluxDB** for time-series data storage
- **FastAPI** for REST API and Prometheus metrics
- **Grafana** for visualization (user-configured)

## Architecture

```
Shelly BLU H&T Sensors (Bluetooth)
         ↓
    Shelly Pro 2 (BT Gateway + Switch Controller)
         ↓
  HTTP Polling (every 30s)
         ↓
   Sensor Poller Service
         ↓
      InfluxDB ←──────────┐
         ↓                 │
    FastAPI + Thermostat  │
         ↓                 │
      Temperature Averaging (configurable samples)
         ↓                 │
    Control Logic ─────────┘
         ↓
   Switch Control (Shelly Pro 2)
         ↓
    Heating/Cooling Device
```

**Simple and reliable:** No message brokers, no complex MQTT configurations, just straightforward HTTP polling with intelligent control.

## Hardware Requirements

- **Shelly Pro 2** (Model: SPSW-202XE12UL) - Firmware 1.6.2+
  - Acts as Bluetooth gateway for sensors
  - Controls heating/cooling via built-in relay switches
- **Shelly BLU H&T** Bluetooth temperature/humidity sensors (1 or more)
  - At least one sensor required for thermostat control
  - Indoor sensor used for temperature control
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

## Features

### 🌡️ Temperature Monitoring
- Real-time temperature and humidity data from multiple sensors
- Prometheus metrics export for Grafana dashboards
- InfluxDB storage for historical analysis
- REST API for easy integration

### 🎛️ Intelligent Thermostat Control (v3.0)
- **4 Operating Modes:**
  - `AUTO` - Normal temperature control with target setpoint
  - `ECO` - Energy-saving mode with lower target temperature
  - `ON` - Manual override (force heating ON)
  - `OFF` - Manual override (force heating OFF)

- **Smart Temperature Control:**
  - Configurable temperature averaging (reduces noise from slow-responding systems)
  - Symmetric hysteresis prevents oscillation (turn on/off thresholds)
  - Minimum ON/OFF time constraints prevent rapid cycling
  - Ideal for underfloor heating, radiators, or any slow thermal mass system

- **Safety & Reliability:**
  - Automatic health monitoring and container restart
  - Persistent configuration survives restarts
  - Human-readable JSON config file on host
  - Real-time logging of all control decisions

- **Monitoring:**
  - Live control loop monitoring scripts
  - Historical decision review
  - Comprehensive logging with log rotation
  - API endpoint for current status

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **sensor-poller** | - | Polls Shelly Pro 2 for sensor data every 30s |
| **influxdb** | 8086 | Time-series database |
| **api** | 8001 | REST API + Prometheus metrics + Thermostat control |

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

## Thermostat Quick Start

### 1. Configure Thermostat

```bash
# View current configuration
curl http://localhost:8001/api/v1/thermostat/config

# Set target temperature to 22°C in AUTO mode
curl -X POST http://localhost:8001/api/v1/thermostat/config \
  -H "Content-Type: application/json" \
  -d '{
    "target_temp": 22.0,
    "eco_temp": 18.0,
    "mode": "AUTO",
    "hysteresis": 0.5,
    "min_on_time": 30,
    "min_off_time": 10,
    "temp_sample_count": 3,
    "control_interval": 180
  }'
```

### 2. Monitor Control Loop

```bash
# Watch real-time control decisions
./watch_thermostat.sh

# View historical decisions
./show_thermostat_history.sh

# Check current status
curl http://localhost:8001/api/v1/thermostat/status
```

### 3. Configuration File

Settings are persisted in `./data/thermostat_config.json` and can be edited directly:

```json
{
  "config": {
    "target_temp": 22.0,
    "eco_temp": 18.0,
    "mode": "AUTO",
    "hysteresis": 0.5,
    "min_on_time": 30,
    "min_off_time": 10,
    "temp_sample_count": 3,
    "control_interval": 180
  }
}
```

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

**Monitor thermostat control:**
```bash
# Live monitoring
./watch_thermostat.sh

# Historical review
./show_thermostat_history.sh
```

**View logs:**
```bash
docker logs iot-sensor-poller --tail 20
docker logs iot-api --tail 20
docker logs -f iot-api  # Follow live
```

## API Endpoints

### Monitoring
- `GET /health` - Health check (includes thermostat status)
- `GET /api/v1/sensors` - List all sensors
- `GET /api/v1/temperature` - Temperature readings
- `GET /api/v1/humidity` - Humidity readings
- `GET /api/v1/battery` - Battery levels
- `GET /metrics` - Prometheus metrics (includes thermostat metrics)

**Thermostat Prometheus Metrics:**
- `thermostat_switch_state` - Switch state (1=ON/heating, 0=OFF)
- `thermostat_target_temperature_celsius` - Target temperature setpoint
- `thermostat_current_temperature_celsius` - Current averaged indoor temperature

### Thermostat Control (v3.0)
- `GET /api/v1/thermostat/config` - Get thermostat configuration
- `POST /api/v1/thermostat/config` - Update thermostat settings
- `GET /api/v1/thermostat/status` - Get current status and control decision
- `POST /api/v1/thermostat/switch` - Manual switch control

Full OpenAPI documentation at `http://localhost:8001/docs`

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

## System Requirements & Longevity

**Storage (128GB SD Card on Raspberry Pi 5):**
- InfluxDB data: ~450 MB max (180-day retention)
- Docker logs: ~60 MB max (30MB per container with rotation)
- Total steady state: ~510 MB (0.4% of capacity)
- **Years to fill**: 50+ years at current rate

**SD Card Longevity:**
- Daily writes: ~2.5 MB/day (sensor data + logs)
- All containers have log rotation (10MB × 3 files)
- State writes only on changes (optimized for SD card wear)
- Expected lifespan: Decades on quality SD cards
- No maintenance required for typical home deployment

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture and design decisions
- [README_MONITORING.md](README_MONITORING.md) - Thermostat monitoring guide
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [check_sensors.sh](check_sensors.sh) - Sensor health check tool
- [watch_thermostat.sh](watch_thermostat.sh) - Live control loop monitoring
- [show_thermostat_history.sh](show_thermostat_history.sh) - Historical review

## Development Status

✅ **Production Ready (v3.0)**
- [x] HTTP polling implementation
- [x] Real BLU H&T sensor integration
- [x] InfluxDB time-series storage
- [x] FastAPI with Prometheus metrics
- [x] Sensor health monitoring
- [x] Complete Docker deployment
- [x] **Intelligent thermostat control**
- [x] **Temperature averaging for slow systems**
- [x] **Automatic health monitoring & restart**
- [x] **Persistent configuration**
- [x] **Real-time control loop logging**
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