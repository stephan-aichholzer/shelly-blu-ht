# IoT Temperature Monitoring - Session History

## Project Overview
Building a complete IoT monitoring stack for temperature measurement using:
- **Shelly Pro 2** as Bluetooth gateway (192.168.2.12)
- **Shelly BLU H&T** sensors for temperature/humidity measurement
- **Docker-based** monitoring stack with MQTT, InfluxDB, Python API, and Grafana integration

## Session Progress

### Phase 1: Planning & Architecture ✅
- Analyzed Shelly Pro 2 capabilities (Model: SPSW-202XE12UL, FW: 1.6.2)
- Discovered BTHome support for BLU sensor integration
- Designed microservices architecture with MQTT transport
- Created comprehensive documentation (README.md, ARCHITECTURE.md)

### Phase 2: Implementation ✅
- **Docker Compose Stack**: 4 services (MQTT, InfluxDB, Collector, API)
- **MQTT Broker**: Mosquitto with development-friendly config
- **Data Collector**: Python service with BTHome/MQTT parsing
- **REST API**: FastAPI with Prometheus metrics endpoints
- **Time Series DB**: InfluxDB 2.7 with proper organization structure

### Phase 3: Deployment & Integration ✅
- Successfully deployed entire stack via `docker-compose up -d`
- Configured Shelly Pro 2 MQTT connection to local broker
- **VERIFIED**: MQTT connectivity working (`shellypro2-btgateway/online true`)
- API running on port 8001 (health check: ✅ healthy)

## Current Status

### Infrastructure Ready ✅
```
Services Status:
├── MQTT Broker (Mosquitto): port 1883 ✅
├── InfluxDB: port 8086 ✅
├── Data Collector: monitoring MQTT ✅
└── REST API: port 8001 ✅

Network Configuration:
├── Docker Host: 192.168.2.11
├── Shelly Pro 2: 192.168.2.12
└── MQTT Topic: shellypro2-btgateway/#
```

### Git Repository Status
- **Latest Commit**: e847a34 - Stack deployment and MQTT integration complete
- **Release Tag**: v0.1 - Complete IoT monitoring stack with MQTT integration
- **Files**: 16 files, comprehensive implementation

## Next Session Tasks

### Immediate (When BLU H&T Sensors Arrive)
1. **Sensor Pairing**:
   ```bash
   # Add BLU H&T sensors to Shelly Pro 2
   curl -X POST http://192.168.2.12/rpc/BTHome.AddDevice -d '{"config": {...}}'
   ```

2. **Verify Data Flow**:
   ```bash
   # Monitor MQTT topics
   docker exec iot-mosquitto mosquitto_sub -t "shellypro2-btgateway/#" -v

   # Check API endpoints
   curl http://localhost:8001/api/v1/sensors
   curl http://localhost:8001/api/v1/temperature
   ```

3. **Grafana Integration**:
   - Connect external Grafana to InfluxDB (port 8086)
   - Import dashboard from `grafana/dashboards/temperature-monitoring.json`
   - Configure data source: `http://192.168.2.11:8086`

### Configuration Details

#### MQTT Configuration
```yaml
Broker: 192.168.2.11:1883
Client ID: shellypro2-btgateway
Topic Prefix: shellypro2-btgateway
Status: Connected ✅
```

#### InfluxDB Configuration
```yaml
URL: http://192.168.2.11:8086
Organization: iot-org
Bucket: sensor-data
Token: iot-admin-token-12345
```

#### Expected Data Schema
```
Measurements:
├── temperature (field: value, unit: celsius)
├── humidity (field: value, unit: percent)
└── battery (field: level, unit: percent)

Tags:
├── device_id: Gateway identifier
├── sensor_id: Individual BLU sensor ID
└── sensor_type: "bthome"
```

## Troubleshooting Guide

### Common Issues & Solutions

1. **MQTT Connection Lost**:
   ```bash
   # Check Shelly MQTT status
   curl http://192.168.2.12/rpc/Mqtt.GetStatus

   # Restart MQTT broker
   docker-compose restart mosquitto
   ```

2. **No Sensor Data**:
   ```bash
   # Check BTHome status
   curl http://192.168.2.12/rpc/BTHome.GetStatus

   # Monitor collector logs
   docker logs iot-collector -f
   ```

3. **API Issues**:
   ```bash
   # Check API health
   curl http://localhost:8001/health

   # Check InfluxDB connection
   docker logs iot-api -f
   ```

### Debug Commands
```bash
# Full stack status
docker-compose ps

# Service logs
docker logs iot-mosquitto --tail 50
docker logs iot-collector --tail 50
docker logs iot-api --tail 50
docker logs iot-influxdb --tail 50

# MQTT monitoring
docker exec iot-mosquitto mosquitto_sub -t "#" -v

# InfluxDB query test
curl -G http://localhost:8086/api/v2/query \
  --data-urlencode "org=iot-org" \
  --data-urlencode "bucket=sensor-data" \
  --data-urlencode "q=from(bucket:\"sensor-data\")|>range(start:-1h)"
```

## Architecture Decisions Made

### Why This Stack?
- **Mosquitto**: Lightweight, reliable MQTT broker
- **InfluxDB**: Purpose-built for time-series data
- **Python Collector**: Flexible BTHome message parsing
- **FastAPI**: Modern Python API with automatic docs
- **Docker**: Consistent deployment and easy scaling

### Security Considerations
- **Current**: Development mode (no authentication)
- **Production**: Add MQTT auth, TLS, InfluxDB tokens
- **Network**: Consider IoT VLAN isolation

## File Structure
```
shelly_bt_temp/
├── README.md                          # Project overview
├── ARCHITECTURE.md                    # System design
├── SESSION_HISTORY.md                 # This file
├── docker-compose.yml                 # Service orchestration
├── .gitignore                         # Git exclusions
├── mosquitto/
│   └── config/mosquitto.conf          # MQTT broker config
├── collector/
│   ├── Dockerfile
│   ├── main.py                        # Data collection service
│   ├── requirements.txt
│   ├── config.yaml
│   └── health_check.py
├── api/
│   ├── Dockerfile
│   ├── main.py                        # REST API + metrics
│   └── requirements.txt
└── grafana/
    ├── provisioning/                   # Data source configs
    └── dashboards/                     # Dashboard definitions
```

## Contact/Continuation
To continue this project:
1. Reference this SESSION_HISTORY.md for full context
2. Check git log for implementation details
3. Review ARCHITECTURE.md for system understanding
4. Use README.md for quick start instructions

**Repository State**: All implementation complete, tested, and ready for sensor integration.

---
*Session completed: 2025-09-27*
*Next: BLU H&T sensor integration and data validation*