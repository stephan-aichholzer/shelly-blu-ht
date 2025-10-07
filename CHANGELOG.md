# Changelog

All notable changes to this project will be documented in this file.

## [3.0.0] - 2025-10-07

### 🌡️ Intelligent Thermostat Control System

**Version 3.0 transforms the system from passive monitoring to active environmental control.**

This release adds comprehensive thermostat capabilities while maintaining the simplicity principle established in v2.0. The system now intelligently controls heating/cooling via the Shelly Pro 2 relay based on temperature sensor readings.

### Added

#### Core Thermostat Features
- **Temperature Averaging**: Configurable moving average (1-10 samples, default: 3) reduces noise for slow-responding heating systems (underfloor heating, large radiators)
- **Symmetric Hysteresis Control**: Prevents oscillation with deadband zone (configurable 0.1-2.0°C, default: 0.5°C)
  - Turn ON when: temp < target - hysteresis
  - Turn OFF when: temp ≥ target + hysteresis
  - Deadband: Maintain current state
- **Timing Constraints**: Minimum ON/OFF time limits prevent rapid cycling
  - `min_on_time`: 1-120 minutes (default: 30 min)
  - `min_off_time`: 1-120 minutes (default: 10 min)
- **Four Operating Modes**:
  - `AUTO` - Normal temperature control with target setpoint
  - `ECO` - Energy-saving mode with lower temperature (vacation/away mode)
  - `ON` - Manual override (force heating ON)
  - `OFF` - Manual override (force heating OFF)
- **Persistent Configuration**: JSON file storage (`./data/thermostat_config.json`) survives container restarts
- **Background Control Loop**: Async task in FastAPI (configurable 60-600s interval, default: 180s)

#### New API Endpoints
- `GET /api/v1/thermostat/config` - Get thermostat configuration
- `POST /api/v1/thermostat/config` - Update thermostat settings (validated with Pydantic)
- `GET /api/v1/thermostat/status` - Get current status, temperatures, and control decision
- `POST /api/v1/thermostat/switch` - Manual switch control override

#### Health Monitoring & Auto-Recovery
- **Extended Health Checks**: InfluxDB connection, Shelly connection, control loop status, error state
- **Docker Healthcheck**: Automatic container restart on failure (3 retries × 30s intervals)
- **Error Recovery**: Exponential backoff retry logic with critical warnings after 5 consecutive failures
- **Health Endpoint**: Extended `/health` endpoint with thermostat status and last control loop execution time

#### Monitoring & Observability
- **Structured Logging**: All control decisions logged with reasoning, temperature samples, and timing status
- **Log Rotation**: JSON file driver with 10MB × 3 files limit (~30MB max total)
- **Live Monitoring Script**: `watch_thermostat.sh` for real-time control loop viewing with colored output
- **Historical Review Script**: `show_thermostat_history.sh` displays last N decisions with current status
- **Monitoring Guide**: `README_MONITORING.md` with comprehensive examples and troubleshooting

#### New Files
- `api/thermostat.py` - Core thermostat logic module with all control algorithms
- `data/thermostat_config.json` - Persistent configuration and state storage
- `watch_thermostat.sh` - Live control loop monitoring script
- `show_thermostat_history.sh` - Historical decision review script with colored output
- `README_MONITORING.md` - Complete monitoring and troubleshooting guide
- `ARCHITECTURE.md` - Comprehensive v3.0 architecture documentation (6000+ words)

### Changed

#### Network Configuration (Fixed v2.0 Grafana Issue)
- **Restored bridge network** with explicit port mapping `8001:8000` (Grafana compatibility)
- **Added `extra_hosts`**: `host.docker.internal:host-gateway` to access Shelly on LAN from container
- This fixes the issue where switching to host network mode broke Grafana metrics scraping

#### API Service
- Modified `api/main.py` to add 4 thermostat endpoints and async background control loop
- Enhanced `/health` endpoint with thermostat status (control loop running, last execution time)
- Added thermostat imports and manager initialization

#### Docker Configuration
- Updated `docker-compose.yml` with logging configuration:
  ```yaml
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  ```
- Added volume mount for persistent config: `./data:/data`
- Fixed network mode for Grafana compatibility while maintaining Shelly access

#### Dependencies
- Added `requests==2.31.0` to `api/requirements.txt` for Shelly HTTP RPC calls
- Updated `api/Dockerfile` to install `curl` for Docker healthcheck
- Added `gcc` to Dockerfile for building Python dependencies

#### Documentation
- **README.md**: Comprehensive update with v3.0 features section, thermostat quick start, monitoring commands
- **ARCHITECTURE.md**: Complete rewrite (6000+ words) covering:
  - System architecture with control layer
  - Design decisions (temperature averaging, control loop, hysteresis, modes)
  - Network architecture evolution
  - Performance characteristics
  - Design trade-offs (HTTP vs MQTT, background task vs service, JSON vs database)
  - Comparison with v2.0
- Added cross-references between all documentation files

### Performance

- **Memory Usage**: ~10 MB increase (API container: ~200 MB → ~210 MB)
- **Control Loop Overhead**: ~100ms per cycle (InfluxDB query + calculation + Shelly RPC)
- **API Response Times**: No measurable impact (control loop runs independently)
- **Disk Usage**: ~30 MB max for logs (with rotation), <1 KB for config
- **No Additional Services**: Maintains 3-container architecture from v2.0

### Comparison with v2.0

| Feature | v2.0 | v3.0 |
|---------|------|------|
| **Purpose** | Monitoring Only | Monitoring + Intelligent Control |
| **Services** | 3 (sensor-poller, influxdb, api) | 3 (same) |
| **Shelly Role** | Read-only (sensors) | Read sensors + Control switch |
| **Control Loop** | None | Async background task in API |
| **Modes** | N/A | AUTO, ECO, ON, OFF |
| **Temperature Sampling** | Single sample | Moving average (configurable) |
| **Safety Features** | N/A | Hysteresis + timing constraints |
| **Health Check** | Basic API ping | Extended (InfluxDB, Shelly, control loop) |
| **Logging** | Standard | Structured + rotation (10MB × 3) |
| **Configuration** | Environment vars | JSON file + ENV |
| **Persistence** | None | Config + state with timestamps |
| **API Endpoints** | 6 | 10 (added 4 thermostat endpoints) |
| **Grafana Port** | 8001 | 8001 (fixed network issue) |

### Design Principles

v3.0 maintains the simplicity philosophy established in v2.0:
- ✅ **Simple**: Single additional module (`thermostat.py`), no new services
- ✅ **Reliable**: Health checks + automatic restart on failure
- ✅ **Safe**: Multiple protection mechanisms (hysteresis, timing, error recovery)
- ✅ **Observable**: Comprehensive logging with structured decisions
- ✅ **Maintainable**: Human-readable JSON configuration
- ✅ **Performant**: Minimal overhead (~10MB memory, 100ms/cycle)

### Why These Design Choices?

**Why Not MQTT for Control?**
- ❌ Requires message broker, async message handling, potential message loss
- ✅ HTTP RPC: Direct request-response, immediate error feedback, easy debugging with curl

**Why Background Task Instead of Separate Service?**
- ❌ Separate service: Another container, inter-service communication, duplicate monitoring
- ✅ Background task: Single container, shared InfluxDB client, integrated logging

**Why JSON File Instead of Database?**
- ❌ Database: Need container, schema migrations, connection management, backup complexity
- ✅ JSON file: Human-readable, easy to edit, simple backup (file copy), version control friendly

### Migration from v2.0

**No Breaking Changes**. Existing v2.0 installations continue to work as monitoring-only systems.

To enable thermostat features:

1. **Update docker-compose.yml** (network config and logging):
   ```bash
   git pull
   docker-compose down
   docker-compose up -d
   ```

2. **Create data directory** for persistent config:
   ```bash
   mkdir -p ./data
   ```

3. **Configure thermostat** via API:
   ```bash
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

4. **Monitor control loop**:
   ```bash
   ./watch_thermostat.sh
   ```

### Hardware Requirements

- **Shelly Pro 2** (firmware 1.6.2+) - Acts as Bluetooth gateway AND relay switch controller
- **Shelly BLU H&T** sensor(s) - At least one sensor required (indoor sensor used for control)
- Network connectivity for Shelly Pro 2

### Use Cases

Perfect for:
- Underfloor heating systems (slow thermal response)
- Large radiator systems (high thermal mass)
- Heat pumps (minimum runtime requirements)
- Vacation homes (ECO mode for minimum temperature maintenance)
- Any slow-responding heating system requiring stable control

### Known Limitations

- **Single Zone**: Only one temperature setpoint (multi-zone support planned for v3.1)
- **No Scheduling**: Mode changes require manual API calls (schedule feature planned)
- **No UI**: HTML5 interface deferred to future release (backend complete and ready)
- **No PID Control**: Simple hysteresis control only (PID option planned for v3.1)

### Troubleshooting

**Control loop not running?**
```bash
curl -s http://localhost:8001/health | grep control_loop_running
```

**See control decisions in real-time:**
```bash
./watch_thermostat.sh
```

**Review historical decisions:**
```bash
./show_thermostat_history.sh 50
```

**Check for errors:**
```bash
docker logs iot-api 2>&1 | grep -E 'ERROR|CRITICAL'
```

### Future Enhancements (Planned for v3.1+)

- PID control algorithm option
- Schedule-based mode switching (daily/weekly programs)
- Weather-based eco mode (outdoor temperature integration)
- Multiple zone support
- Energy usage tracking and reporting
- Grafana dashboard templates
- HTML5 UI for configuration and monitoring
- Mobile app integration

---

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