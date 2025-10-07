# Architecture Documentation

## System Overview

The Shelly BT Temperature Monitoring System is a lightweight IoT solution for collecting and visualizing temperature and humidity data from Shelly BLU H&T Bluetooth sensors.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Physical Layer                            │
│  Shelly BLU H&T Sensors (Bluetooth Low Energy)              │
│  - temp_outdoor: 7c:c6:b6:ab:66:13                          │
│  - temp_indoor:  94:b2:16:0b:88:01                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ Bluetooth (1-minute broadcasts)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                   Gateway Layer                              │
│  Shelly Pro 2 (SPSW-202XE12UL)                              │
│  - Receives BT broadcasts from sensors                       │
│  - Exposes sensor data via HTTP REST API                     │
│  - IP: 192.168.2.12                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP polling (every 30 seconds)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              Data Collection Layer                           │
│  Sensor Poller (Python)                                      │
│  - Polls Shelly REST API: /rpc/BTHomeSensor.GetStatus       │
│  - Polls Shelly REST API: /rpc/BTHomeDevice.GetStatus       │
│  - Collects: temperature, humidity, battery, RSSI            │
│  - Enriches data with sensor names                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ Direct write
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  Storage Layer                               │
│  InfluxDB 2.7 (Time-Series Database)                         │
│  - Bucket: sensor-data                                       │
│  - Retention: 30 days                                        │
│  - Tags: gateway_id, sensor_id, sensor_name, sensor_type    │
│  - Fields: temperature, humidity, battery                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ Query
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                 API Layer                                    │
│  FastAPI + Prometheus                                        │
│  - REST API: /api/v1/sensors, /temperature, /humidity       │
│  - Prometheus metrics: /metrics                              │
│  - Real-time metric updates on scrape                        │
│  - Port: 8001                                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP scraping
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              Visualization Layer                             │
│  Prometheus + Grafana (User-configured)                      │
│  - Scrapes /metrics endpoint                                 │
│  - Dashboards with sensor_name labels                        │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### v2.0: HTTP Polling Architecture

**Decision:** Use simple HTTP polling instead of MQTT message broker.

**Rationale:**

#### Why We Chose HTTP Polling

1. **Simplicity**
   - No message broker (Mosquitto) to configure
   - No complex topic patterns or subscriptions
   - Standard HTTP requests that everyone understands
   - Fewer moving parts = fewer failure points

2. **Reliability**
   - Direct request-response pattern
   - Immediate error feedback
   - No message queue overflow issues
   - No "lost message" scenarios

3. **Easier Debugging**
   - Can test with `curl` or browser
   - Standard HTTP status codes
   - Clear request/response logs
   - No message broker logs to correlate

4. **Less Infrastructure**
   - 3 services instead of 5
   - ~200MB less memory usage
   - Simpler docker-compose configuration
   - Fewer ports to expose

5. **Appropriate Scale**
   - 2 sensors updating every 30 seconds
   - ~60 HTTP requests per hour
   - No need for pub/sub scalability
   - Perfect for small-scale IoT

#### Why We Initially Considered MQTT

- Sounds modern and "IoT-appropriate"
- Good for large-scale sensor networks (100+ devices)
- Efficient for unreliable networks
- Push-based updates feel more "real-time"

#### Why We Abandoned MQTT

- **Over-engineering** for 2 sensors
- Shelly Pro 2 doesn't natively publish sensor data to MQTT
- Would require custom scripting on Shelly (complex, fragile)
- Added significant complexity without benefit
- MQTT broker = additional service to maintain

### Key Architecture Principles

1. **Keep It Simple**: Choose the simplest solution that works
2. **Pragmatic Over Clever**: HTTP polling is boring, but it works
3. **Less Infrastructure**: Fewer services = easier maintenance
4. **Standard Protocols**: HTTP is universal and well-understood
5. **Direct Data Flow**: Minimize hops between source and storage

## Component Details

### Sensor Poller

**Technology:** Python 3.11

**Responsibilities:**
- Poll Shelly Pro 2 HTTP API every 30 seconds
- Query sensor values for each paired BLU H&T device
- Enrich data with human-readable sensor names
- Write directly to InfluxDB

**Key Features:**
- Configurable poll interval
- Automatic sensor discovery via configuration
- Error handling and retry logic
- Structured logging

**Configuration:**
```python
SENSORS = [
    {
        "device_id": 200,              # Shelly device ID
        "name": "temp_outdoor",        # Human-readable name
        "mac": "7c:c6:b6:ab:66:13",   # MAC address (for tagging)
        "temperature_sensor_id": 202,  # BTHomeSensor component ID
        "humidity_sensor_id": 201,     # BTHomeSensor component ID
        "battery_sensor_id": 200       # BTHomeSensor component ID
    }
]
```

### InfluxDB

**Version:** 2.7

**Configuration:**
- **Bucket:** sensor-data
- **Retention:** 30 days
- **Org:** iot-org

**Schema:**
```
Measurement: temperature
  Tags:
    - gateway_id: shellypro2-8813bfddbfe8
    - sensor_id: 7c:c6:b6:ab:66:13
    - sensor_name: temp_outdoor
    - sensor_type: bthome
  Fields:
    - value: 9.6 (float)
  Timestamp: 2025-09-29T19:42:00Z

Measurement: humidity
  [same tags]
  Fields:
    - value: 72.0 (float)

Measurement: battery
  [same tags]
  Fields:
    - level: 100 (integer)
```

### FastAPI Service

**Technology:** Python 3.11 + FastAPI + prometheus_client

**Endpoints:**

**REST API:**
- `GET /health` - Service health check
- `GET /api/v1/sensors` - List all sensors with metadata
- `GET /api/v1/temperature?sensor_id=...&limit=...` - Temperature data
- `GET /api/v1/humidity?sensor_id=...&limit=...` - Humidity data
- `GET /api/v1/battery?sensor_id=...&limit=...` - Battery levels

**Prometheus Metrics:**
- `GET /metrics` - Prometheus exposition format

**Metrics Exposed:**
```
sensor_temperature_celsius{device_id, sensor_id, sensor_name}
sensor_humidity_percent{device_id, sensor_id, sensor_name}
sensor_battery_percent{device_id, sensor_id, sensor_name}
```

**Key Feature:** Metrics are refreshed from InfluxDB on each scrape, ensuring Grafana always sees current values.

## Data Flow

### Normal Operation

1. **Sensor Broadcast** (every 1 minute)
   - BLU H&T sensor broadcasts BTHome packet via Bluetooth
   - Shelly Pro 2 receives and stores latest values

2. **HTTP Polling** (every 30 seconds)
   - Poller queries `/rpc/BTHomeSensor.GetStatus?id=202` (temperature)
   - Poller queries `/rpc/BTHomeSensor.GetStatus?id=201` (humidity)
   - Poller queries `/rpc/BTHomeDevice.GetStatus?id=200` (device info)

3. **Data Enrichment**
   - Poller adds sensor_name tag
   - Poller adds gateway_id tag
   - Formats data as InfluxDB Line Protocol

4. **Storage**
   - Write to InfluxDB bucket with tags and timestamp
   - Data persisted with 30-day retention

5. **Metrics Export**
   - Prometheus scrapes `/metrics` endpoint (typically every 15s)
   - API queries InfluxDB for latest values
   - API updates Prometheus gauges
   - Metrics returned to Prometheus

6. **Visualization**
   - Grafana queries Prometheus
   - User creates dashboards with PromQL
   - Real-time graphs display sensor data

## Deployment

### Docker Services

```yaml
services:
  influxdb:      # Time-series database
  api:           # REST API + Prometheus metrics
  sensor-poller: # HTTP polling service (host network)
```

### Network Configuration

- **sensor-poller**: Uses `host` network mode to access Shelly on local network
- **influxdb**: Internal Docker network + exposed port 8086
- **api**: Internal Docker network + exposed port 8001

### Environment Variables

**sensor-poller:**
- `SHELLY_IP`: IP of Shelly Pro 2 gateway
- `POLL_INTERVAL`: Seconds between polls
- `INFLUXDB_URL`: InfluxDB connection URL
- `INFLUXDB_TOKEN`: Authentication token

**api:**
- `INFLUXDB_URL`: InfluxDB connection URL
- `INFLUXDB_TOKEN`: Authentication token

## Monitoring & Operations

### Health Checks

**Automated:**
- Docker health checks on all services
- API health endpoint: `/health`

**Manual:**
- `check_sensors.sh` - Comprehensive sensor health check
- Shows: temperature, humidity, battery, RSSI, last update time

### Logging

- **sensor-poller**: Structured logs to stdout (captured by Docker)
- **api**: Uvicorn access logs + application logs
- **influxdb**: InfluxDB logs to stdout

### Troubleshooting

**Common Issues:**

1. **Sensors not updating**
   - Check Bluetooth range (10-30m)
   - Run `check_sensors.sh` to verify connectivity
   - Check `last_updated_ts` in Shelly API

2. **No data in InfluxDB**
   - Check poller logs: `docker logs iot-sensor-poller`
   - Verify Shelly IP in docker-compose.yml
   - Test Shelly API manually with curl

3. **Stale Prometheus metrics**
   - Verify Prometheus is scraping endpoint
   - Check API logs for errors
   - Ensure InfluxDB connection is healthy

## Performance Characteristics

- **Poll Rate**: Every 30 seconds
- **Data Points**: ~2 sensors × 3 metrics × 2 polls/min = 6 writes/min
- **Storage**: ~250KB per day per sensor
- **Memory Usage**: ~300MB total (all services)
- **CPU Usage**: <1% on Raspberry Pi 4

## Security Considerations

- No authentication on Shelly API (local network only)
- InfluxDB token-based authentication
- API exposed on localhost only (reverse proxy recommended for remote access)
- No sensitive data in environment variables (except InfluxDB token)

## Future Enhancements

- [ ] Alerting on sensor offline
- [ ] Alerting on temperature thresholds
- [ ] Multi-gateway support
- [ ] Automatic sensor discovery
- [ ] Built-in Grafana dashboards
- [ ] Historical data export

## Lessons Learned

### What Worked Well

✅ **HTTP polling** - Simple, reliable, easy to debug
✅ **Direct InfluxDB writes** - No intermediate layers
✅ **Prometheus metrics with sensor_name** - Human-readable dashboards
✅ **Docker Compose** - Easy deployment and updates
✅ **check_sensors.sh** - Invaluable for troubleshooting

### What Didn't Work

❌ **MQTT approach** - Over-engineered for this scale
❌ **Shelly scripting** - Too fragile, hard to maintain
❌ **Message broker** - Unnecessary complexity

### Key Takeaways

> **"The best architecture is the simplest one that meets your needs."**

For small-scale IoT (< 10 devices), **HTTP polling beats MQTT** in:
- Simplicity
- Reliability
- Debuggability
- Maintenance burden

Only scale up to MQTT when you have:
- 100+ devices
- Unreliable networks
- Need for pub/sub patterns
- Bandwidth constraints

## References

- [Shelly Pro 2 API Documentation](https://shelly-api-docs.shelly.cloud/)
- [Shelly BLU H&T Specifications](https://kb.shelly.cloud/knowledge-base/shelly-blu-h-t)
- [InfluxDB 2.x Documentation](https://docs.influxdata.com/influxdb/v2.7/)
- [Prometheus Exposition Format](https://prometheus.io/docs/instrumenting/exposition_formats/)