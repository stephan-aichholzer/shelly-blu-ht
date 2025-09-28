# Shelly BT Temperature Monitoring System

A Docker-based monitoring stack for collecting temperature and humidity data from Shelly BLU H&T sensors via a Shelly Pro 2 Bluetooth gateway.

## Overview

This project creates a complete IoT monitoring solution using:
- **Shelly Pro 2** as Bluetooth gateway
- **Shelly BLU H&T** sensors for temperature/humidity measurement
- **MQTT** for data transport
- **InfluxDB** for time-series data storage
- **Grafana** for visualization
- **Python API** for programmatic access
- **Prometheus metrics** for monitoring integration

## Hardware Requirements

- Shelly Pro 2 (Model: SPSW-202XE12UL)
- Shelly BLU H&T Bluetooth temperature/humidity sensors
- Network connectivity for the Shelly Pro 2

## Current Device Status

**Shelly Pro 2:**
- Model: SPSW-202XE12UL
- Firmware: 1.6.2
- Bluetooth: ✅ Enabled
- MQTT: ⚠️ Not configured

## Quick Start

### Testing with Mockup Sensors (Recommended)
1. Clone this repository
2. Start the complete stack with mockup sensors: `docker-compose --profile mockup up -d`
3. Access API at http://localhost:8001
4. Configure Prometheus to scrape http://localhost:8001/metrics
5. View live sinus wave temperature data in Grafana

### Production with Real Sensors
1. Configure your Shelly Pro 2 MQTT settings (see [REAL_SENSORS_SETUP.md](REAL_SENSORS_SETUP.md))
2. Pair your BLU H&T sensors with the Pro 2
3. Start the monitoring stack: `docker-compose up -d`

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system architecture
- [REAL_SENSORS_SETUP.md](REAL_SENSORS_SETUP.md) - Guide for integrating real BLU H&T sensors
- [README_MOCKUP.md](README_MOCKUP.md) - Mockup sensor documentation
- [TESTING_ENVIRONMENT.md](TESTING_ENVIRONMENT.md) - Development and testing environment setup
- [docs/](docs/) - Additional documentation

## Development Status

✅ **Fully Functional Testing Stack**
- [x] Hardware discovery and analysis
- [x] MQTT broker setup
- [x] Data collection pipeline
- [x] Mockup sensor implementation with sinus wave patterns
- [x] Python API with real-time data
- [x] Prometheus metrics (with live updates)
- [x] Complete Docker stack
- [ ] Grafana dashboards (configured by user)
- [ ] Real BLU H&T sensor integration (pending hardware)

## License

MIT License - see [LICENSE](LICENSE) for details.