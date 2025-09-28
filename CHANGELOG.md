# Changelog

All notable changes to this project will be documented in this file.

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