# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2025-09-29

### 🚀 Major Architecture Change

**Migrated from MQTT-based architecture to simple HTTP polling.**

This release represents a fundamental shift in system design based on practical experience: for small-scale IoT deployments (2-10 sensors), HTTP polling is simpler, more reliable, and easier to maintain than MQTT.

### Breaking Changes
- ⚠️ **Removed MQTT broker** (Mosquitto service)
- ⚠️ **Removed MQTT collector** service
- ⚠️ **Removed mockup sensors** (replaced with real sensor integration)
- ⚠️ **Changed data collection method** from MQTT subscription to HTTP polling

### Added
- **HTTP Polling Service**: New `sensor-poller` service polls Shelly Pro 2 REST API every 30 seconds
- **Real Sensor Integration**: Full support for Shelly BLU H&T Bluetooth sensors
- **Sensor Health Monitoring**: `check_sensors.sh` script for comprehensive sensor diagnostics
- **Prometheus Labels**: Added `sensor_name` labels to all metrics for human-readable dashboards
- **Live Metrics Updates**: `/metrics` endpoint now refreshes gauges from InfluxDB on each scrape

### Changed
- **Architecture Documentation**: Complete rewrite of ARCHITECTURE.md explaining design decisions
- **README**: Updated to reflect HTTP polling approach with simplified setup
- **Docker Compose**: Reduced from 5 services to 3 (influxdb, api, sensor-poller)
- **Network Configuration**: sensor-poller uses host network mode to access Shelly on local network

### Fixed
- **Sensor Naming**: Corrected indoor/outdoor sensor mapping based on actual temperature readings
- **Humidity Data Type**: Fixed float/integer conflict in InfluxDB writes
- **Metrics Staleness**: Resolved issue where Prometheus metrics showed outdated values
- **Sensor Name Labels**: Added missing sensor_name to all Prometheus metrics

### Removed
- MQTT broker (Mosquitto)
- MQTT collector service
- Mockup sensor simulator
- Shelly JavaScript bridge scripts
- Obsolete documentation (README_MOCKUP.md, REAL_SENSORS_SETUP.md, TESTING_ENVIRONMENT.md)

### Technical Details

**Hardware Integration:**
- Shelly Pro 2 (SPSW-202XE12UL) at 192.168.2.12
- 2x Shelly BLU H&T sensors broadcasting every 1 minute
- Sensor 200 (7c:c6:b6:ab:66:13): temp_outdoor
- Sensor 201 (94:b2:16:0b:88:01): temp_indoor

**Data Flow:**
```
BLU H&T Sensors (BT) → Shelly Pro 2 → HTTP Polling (30s) → InfluxDB → FastAPI + Prometheus → Grafana
```

**Performance:**
- Poll rate: 30 seconds
- Memory usage: ~300MB total (down from ~500MB)
- CPU usage: <1% on Raspberry Pi 4

### Design Philosophy

**Why HTTP Polling Won:**
- ✅ Simpler: No message broker configuration
- ✅ More reliable: Direct HTTP requests, no message queuing
- ✅ Easier debugging: Standard HTTP requests with curl
- ✅ Less infrastructure: 3 services instead of 5
- ✅ Appropriate scale: Perfect for 2-10 sensors

**Why MQTT Was Abandoned:**
- ❌ Over-engineered for 2 sensors
- ❌ Shelly doesn't natively publish sensor data to MQTT
- ❌ Required fragile custom scripting on Shelly
- ❌ Added complexity without benefit
- ❌ Extra service to maintain

### Migration Notes

For users upgrading from v1.x:

1. Stop and remove old services:
   ```bash
   docker-compose down
   docker volume rm shelly_bt_temp_mosquitto-data shelly_bt_temp_mosquitto-log
   ```

2. Update to v2.0:
   ```bash
   git pull
   git checkout v2.0
   ```

3. Configure sensors in `sensor-poller/poller.py`

4. Start new stack:
   ```bash
   docker-compose up -d
   ```

### Lessons Learned

> **"The best architecture is the simplest one that meets your needs."**

For small-scale IoT (< 10 devices), HTTP polling beats MQTT in simplicity, reliability, debuggability, and maintenance burden. Only scale up to MQTT when you have 100+ devices, unreliable networks, or true pub/sub requirements.

---

## [1.0.0] - 2025-09-28

### Added
- Complete mockup sensor system with sinus wave temperature patterns
- Docker-based monitoring stack (MQTT, InfluxDB, API, Collector)
- Real-time Prometheus metrics with live data updates
- Comprehensive API endpoints for sensor data access
- Virtual environment setup for local testing
- Docker profiles for mockup vs. production deployment

### Features
- **Mockup Sensors**: 2 simulated BLU H&T sensors with different temperature patterns
- **Sinus Wave Data**: Temperature ranges from -10°C to +30°C over 1-hour cycles
- **MQTT Integration**: Full BTHome protocol compatibility
- **Data Collection**: Automatic storage in InfluxDB time-series database
- **REST API**: Complete sensor data access at `localhost:8001`
- **Prometheus Metrics**: Live-updating metrics for monitoring integration
- **Documentation**: Comprehensive setup and usage guides

### Technical Details
- **Sensor Patterns**:
  - Sensor 01: 20°C base ± 10°C amplitude
  - Sensor 02: 18°C base ± 8°C amplitude (30min phase shift)
- **Update Frequency**: 30-second intervals
- **Data Format**: BTHome-compatible MQTT messages
- **API Endpoints**: `/api/v1/sensors`, `/api/v1/temperature`, `/api/v1/humidity`, `/api/v1/battery`
- **Metrics**: `/metrics` endpoint with real-time Prometheus gauges

### Fixed
- **Metrics Lag Issue**: Resolved Prometheus metrics not updating in real-time
- **MQTT Topic Patterns**: Fixed invalid subscription filters
- **InfluxDB Connection**: Resolved API compatibility issues with bucket listing

### Documentation
- `README_MOCKUP.md` - Mockup sensor usage guide
- `REAL_SENSORS_SETUP.md` - Real hardware integration guide
- `TESTING_ENVIRONMENT.md` - Development environment setup
- Updated main README with complete usage instructions

### Infrastructure
- Docker Compose with service profiles
- Health checks for all services
- Proper user permissions and security
- Virtual environment for local testing
- Comprehensive error handling and logging

## Deployment

### Mockup Testing
```bash
docker-compose --profile mockup up -d
```

### Production Ready
```bash
docker-compose up -d
```

Ready for real Shelly BLU H&T sensor integration when hardware becomes available.