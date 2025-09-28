# Real Sensors Setup Guide

This guide explains how to transition from mockup sensors to real Shelly BLU H&T sensors, or run both simultaneously.

## Overview

When you get your real Shelly BLU H&T sensors, you have two options for integrating them with your monitoring stack.

## Option 1: Replace Mockup Sensors (Recommended)

**Stop mockup sensors and use only real ones:**

```bash
# Stop the full stack
docker-compose down

# Start without mockup profile (no simulated sensors)
docker-compose up -d
```

The real sensors will automatically be detected when:
1. Your Shelly Pro 2 has MQTT configured to point to your broker
2. The sensors are paired with your Shelly Pro 2
3. The Shelly Pro 2 publishes BTHome events

## Option 2: Run Both Side-by-Side

**Keep both mockup and real sensors running:**

```bash
# Keep the full stack with mockup sensors running
docker-compose --profile mockup up -d
```

Your real sensors will appear **alongside** the mockup ones. You'll see data from both:
- `mockup-sensor-01`, `mockup-sensor-02` (simulated)
- `your-real-sensor-id-123`, `your-real-sensor-id-456` (real)

## Configuration Required

### 1. Shelly Pro 2 MQTT Settings

Configure your Shelly Pro 2 to publish to your MQTT broker:

```bash
# Check current MQTT status
curl -s http://192.168.2.12/rpc/Mqtt.GetStatus

# Configure MQTT (replace with your setup)
curl -X POST http://192.168.2.12/rpc/Mqtt.SetConfig -d '{
  "config": {
    "enable": true,
    "server": "your-computer-ip:1883",
    "client_id": "shellypro2-yourdevice"
  }
}'
```

**Replace `your-computer-ip` with your actual computer's IP address where the MQTT broker is running.**

### 2. Pair BLU H&T Sensors

Follow the Shelly documentation to pair your BLU H&T sensors with the Shelly Pro 2:

1. Put BLU H&T sensors in pairing mode
2. Use Shelly Pro 2 web interface to scan and pair sensors
3. Verify sensors appear in the Pro 2's device list

### 3. Verify MQTT Topics

The collector automatically handles real sensor data. No code changes needed!

**MQTT Topic Pattern**: `+/events/rpc`
- Catches: `shellypro2-yourdevice/events/rpc`
- Processes: BTHome sensor events from paired BLU H&T sensors

## Sensor Identification

### Mockup Sensors
- IDs: `mockup-sensor-01`, `mockup-sensor-02`
- Gateway: `shellypro2-mockup01`, `shellypro2-mockup02`

### Real Sensors
- IDs: `SBHT-003C-39F4`, `SBHT-003C-4A1B` (examples)
- Gateway: `shellypro2-8813bfddbfe8` (your actual device ID)

## Data Storage

Both real and mockup sensors store data in the same InfluxDB format:

```json
{
  "measurement": "temperature",
  "tags": {
    "gateway_id": "shellypro2-yourdevice",
    "sensor_id": "SBHT-003C-39F4",
    "sensor_type": "bthome"
  },
  "fields": {
    "value": 23.5
  }
}
```

## Quick Reference Commands

### Switching Between Modes

```bash
# Testing with mockup sensors
docker-compose --profile mockup up -d

# Production with real sensors only
docker-compose down
docker-compose up -d

# View all running services
docker-compose ps
```

### Monitoring

```bash
# View sensor data processing
docker logs iot-collector | grep "Stored.*data points"

# Monitor MQTT messages
docker exec iot-mosquitto mosquitto_sub -h localhost -t "+/events/rpc" -v

# Check collector status
docker logs iot-collector --tail 20
```

### Data Queries

```sql
-- View all sensors
SELECT * FROM temperature WHERE time > now() - 1h

-- View only real sensors (exclude mockup)
SELECT * FROM temperature WHERE sensor_id !~ /mockup/ AND time > now() - 1h

-- View only mockup sensors
SELECT * FROM temperature WHERE sensor_id =~ /mockup/ AND time > now() - 1h

-- View by gateway
SELECT * FROM temperature WHERE gateway_id = 'shellypro2-yourdevice' AND time > now() - 1h
```

## Troubleshooting

### Real Sensors Not Appearing

1. **Check Shelly Pro 2 MQTT config:**
   ```bash
   curl -s http://192.168.2.12/rpc/Mqtt.GetStatus
   ```

2. **Verify sensors are paired:**
   - Check Shelly Pro 2 web interface
   - Look for BLU H&T devices in device list

3. **Monitor MQTT traffic:**
   ```bash
   docker exec iot-mosquitto mosquitto_sub -h localhost -t "#" -v
   ```

4. **Check collector logs:**
   ```bash
   docker logs iot-collector --tail 50
   ```

### Common Issues

- **Wrong IP address**: Update MQTT server config with correct computer IP
- **Network connectivity**: Ensure Shelly Pro 2 can reach your computer
- **Sensor pairing**: Verify BLU H&T sensors are properly paired
- **MQTT authentication**: Check if your MQTT broker requires credentials

## Data Format Comparison

### Mockup Sensor Data
```json
{
  "src": "shellypro2",
  "method": "NotifyEvent",
  "params": {
    "events": [{
      "component": "bthomesensor",
      "id": "mockup-sensor-01",
      "data": {
        "temperature": 25.3,
        "humidity": 45.2,
        "battery": 98,
        "rssi": -55
      }
    }]
  }
}
```

### Real Sensor Data
```json
{
  "src": "shellypro2",
  "method": "NotifyEvent",
  "params": {
    "events": [{
      "component": "bthomesensor",
      "id": "SBHT-003C-39F4",
      "data": {
        "temperature": 24.1,
        "humidity": 52.7,
        "battery": 95,
        "rssi": -62
      }
    }]
  }
}
```

## Integration Complete

Once configured, real sensors will:
- ✅ Automatically appear in InfluxDB
- ✅ Be accessible via the API at `localhost:8001`
- ✅ Work with existing Grafana dashboards (when configured)
- ✅ Generate Prometheus metrics

No code changes required! The existing collector at `collector/main.py:175-183` handles both mockup and real sensor data seamlessly.