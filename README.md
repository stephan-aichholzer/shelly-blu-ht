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

1. Clone this repository
2. Configure your Shelly Pro 2 MQTT settings
3. Pair your BLU H&T sensors with the Pro 2
4. Start the monitoring stack: `docker-compose up -d`

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system architecture
- [docs/](docs/) - Additional documentation

## Development Status

🚧 **Proof of Concept Phase**
- [x] Hardware discovery and analysis
- [ ] MQTT broker setup
- [ ] Data collection pipeline
- [ ] Grafana dashboards
- [ ] Python API
- [ ] Prometheus metrics

## License

MIT License - see [LICENSE](LICENSE) for details.