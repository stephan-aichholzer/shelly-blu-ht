# System Architecture

## Overview

This system implements a complete IoT monitoring pipeline for temperature and humidity measurement using Shelly devices and a Docker-based data stack.

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Shelly BLU H&T  │    │   Shelly Pro 2   │    │  MQTT Broker    │
│   (Sensors)     │───▶│  (BT Gateway)    │───▶│   (Mosquitto)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              │                          ▼
                              │                 ┌─────────────────┐
                              │                 │ Data Collector  │
                              │                 │   (Python)      │
                              │                 └─────────────────┘
                              │                          │
                              │                          ▼
                              │                 ┌─────────────────┐
                              │                 │    InfluxDB     │
                              │                 │ (Time Series)   │
                              │                 └─────────────────┘
                              │                          │
                              │                          │
                              │                 ┌─────────────────┐    ┌─────────────────┐
                              │                 │   Python API    │    │    Grafana      │
                              └─────────────────│ + Prometheus    │◀───│   Dashboard     │
                                                │    Metrics      │    └─────────────────┘
                                                └─────────────────┘
```

## Components

### 1. Data Collection Layer

#### Shelly BLU H&T Sensors
- **Function**: Temperature and humidity measurement
- **Communication**: Bluetooth Low Energy (BLE) advertising
- **Data**: Temperature, humidity, battery level
- **Update Frequency**: ~1 minute intervals

#### Shelly Pro 2 (BT Gateway)
- **Model**: SPSW-202XE12UL
- **IP**: <DEVICE_IP>
- **Function**: BLE to MQTT bridge
- **Current Status**:
  - Firmware: 1.6.2
  - BLE: Enabled ✅
  - MQTT: Needs configuration ⚠️

### 2. Message Transport

#### MQTT Broker (Mosquitto)
- **Function**: Message routing and buffering
- **Topics**: `shellypro2-<DEVICE_ID>/events/rpc` (estimated)
- **QoS**: Level 1 (at least once delivery)
- **Retention**: Configurable

### 3. Data Storage

#### InfluxDB
- **Type**: Time-series database
- **Schema**:
  - Measurement: `temperature`, `humidity`
  - Tags: `sensor_id`, `location`
  - Fields: `value`, `battery_level`
  - Timestamp: UTC

### 4. Data Access & Visualization

#### Python API
- **Framework**: FastAPI
- **Endpoints**:
  - `/api/v1/sensors` - List sensors
  - `/api/v1/data/{sensor_id}` - Get sensor data
  - `/api/v1/metrics` - Prometheus metrics
- **Functions**: Direct database queries, data export

#### Grafana Dashboard
- **Data Source**: InfluxDB
- **Panels**:
  - Real-time temperature graphs
  - Humidity trends
  - Battery level monitoring
  - Sensor status overview

#### Prometheus Metrics
- **Metrics**:
  - `shelly_temperature_celsius`
  - `shelly_humidity_percent`
  - `shelly_battery_level`
  - `shelly_sensor_last_seen`

## Data Flow

1. **Collection**: BLU H&T sensors broadcast data via BLE advertising
2. **Gateway**: Shelly Pro 2 receives BLE data and publishes to MQTT
3. **Transport**: MQTT broker routes messages to subscribers
4. **Processing**: Data collector consumes MQTT messages and writes to InfluxDB
5. **Access**:
   - Grafana queries InfluxDB for visualization
   - Python API provides programmatic access
   - Prometheus scrapes metrics endpoint

## Network Configuration

### Current Network
- Subnet: <LOCAL_SUBNET>
- Shelly Pro 2: <DEVICE_IP>
- Docker Host: <HOST_IP>

### Port Allocation
- MQTT: 1883 (internal), 1883 (external)
- InfluxDB: 8086 (internal), 8086 (external)
- Grafana: 3000 (internal), 3000 (external)
- Python API: 8000 (internal), 8000 (external)
- Prometheus: 9090 (internal), 9090 (external)

## Security Considerations

### Phase 1 (Proof of Concept)
- No authentication on MQTT broker
- Default credentials for databases
- HTTP only (no SSL/TLS)

### Production Recommendations
- MQTT authentication with username/password
- SSL/TLS encryption for all services
- Grafana authentication
- InfluxDB token-based authentication
- Network segmentation (IoT VLAN)

## Deployment

### Docker Compose Services
```yaml
services:
  mosquitto:    # MQTT broker
  influxdb:     # Time series database
  grafana:      # Visualization
  collector:    # Data collection service
  api:          # Python API + Prometheus metrics
```

### Volume Mounts
- InfluxDB data: persistent storage
- Grafana config: dashboards and data sources
- Mosquitto config: broker settings

## Monitoring & Maintenance

### Health Checks
- MQTT broker connectivity
- InfluxDB write success
- Sensor data freshness
- Container health status

### Logging
- Centralized logging for all services
- Log levels: INFO for normal operation, DEBUG for troubleshooting
- Log rotation and retention policies

## Future Enhancements

1. **Multi-sensor Support**: Scale to multiple BLU H&T sensors
2. **Alerting**: Notification for temperature thresholds
3. **Data Retention**: Automated data lifecycle management
4. **High Availability**: Multiple MQTT brokers, database clustering
5. **Mobile App**: React Native app for mobile access
6. **Edge Processing**: Local analytics and preprocessing

## Configuration Files

- `docker-compose.yml` - Service orchestration
- `mosquitto/mosquitto.conf` - MQTT broker config
- `grafana/provisioning/` - Dashboard and data source definitions
- `influxdb/init.sh` - Database initialization
- `collector/config.yaml` - Data collection settings