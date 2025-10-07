# Thermostat Control Loop Monitoring

This guide shows you how to monitor the thermostat control loop in real-time and review historical decisions.

## Quick Commands

### 1. Live Monitoring (Rolling Logs)
Watch control loop decisions in real-time:
```bash
./watch_thermostat.sh
```

Or manually:
```bash
docker logs -f iot-api 2>&1 | grep --line-buffered -E 'Averaging|Control decision|Changing switch|ERROR'
```

**What you'll see:**
- Temperature sample averaging (every 2 minutes with default config)
- Control decisions (heating needed, deadband, locked)
- Switch state changes (ON/OFF)
- Errors and warnings

### 2. Historical Review
Show last 50 control decisions:
```bash
./show_thermostat_history.sh
```

Show last N decisions:
```bash
./show_thermostat_history.sh 100
```

### 3. All API Logs
View all API logs (including HTTP requests):
```bash
docker logs iot-api
```

Recent logs only:
```bash
docker logs --tail 100 iot-api
```

Follow live:
```bash
docker logs -f iot-api
```

### 4. Sensor Poller Logs
Monitor sensor data collection:
```bash
docker logs -f iot-sensor-poller
```

## Log Rotation

Logs are automatically rotated to prevent disk space issues:
- **Max log size:** 10 MB per file
- **Max files:** 3 files kept
- **Total max:** ~30 MB of logs retained

Logs are stored in: `/var/lib/docker/containers/<container-id>/`

## Log Format

### Temperature Averaging
```
INFO:main:Averaging 5 temperature samples: ['22.1', '22.1', '22.1', '22.1', '22.1'] -> 22.10°C
```

### Control Decisions

**With Timing Information (shows runtime/idle time and remaining lock time):**

```
INFO:main:Control decision: Heating: 21.7°C < 21.8°C (already ON, running 5/30min)
INFO:main:Control decision: Target reached: 22.5°C >= 22.2°C (already OFF, idle 12/10min)
INFO:main:Control decision: Temperature 21.9°C in deadband [21.8°C - 22.2°C], maintaining ON (running 20/30min)
INFO:main:Control decision: Temperature 21.9°C in deadband [21.8°C - 22.2°C], maintaining OFF (idle 8/10min)
INFO:main:Control decision: Turning ON: 21.7°C < 21.8°C (OFF for 12min >= 10min)
INFO:main:Control decision: Turning OFF: 22.5°C >= 22.2°C (ON for 35min >= 30min)
INFO:main:Control decision: Heating needed but locked OFF (idle 5/10min, 5min remaining)
INFO:main:Control decision: Target reached but locked ON (running 15/30min, 15min remaining)
```

**Format:**
- `(running X/Ymin)` = Switch ON for X minutes, minimum ON time is Y minutes
- `(idle X/Ymin)` = Switch OFF for X minutes, minimum OFF time is Y minutes
- `(X/Ymin, Zmin remaining)` = When locked, shows remaining time until action allowed
```

### Switch Actions
```
INFO:main:Changing switch state: False -> True
INFO:main:Switch successfully set to ON
```

### Errors
```
ERROR:main:Error in control loop: Cannot reach Shelly device
WARNING:main:No indoor temperature data available
CRITICAL:main:Control loop has failed 5 times consecutively!
```

## Monitoring via API

Get current status programmatically:
```bash
curl -s http://localhost:8001/api/v1/thermostat/status | python3 -m json.tool
```

Check health:
```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```

View Prometheus metrics (includes thermostat switch state):
```bash
curl -s http://localhost:8001/metrics | grep thermostat
```

**Thermostat Metrics:**
- `thermostat_switch_state` - 1=ON (heating), 0=OFF
- `thermostat_target_temperature_celsius` - Current target setpoint
- `thermostat_current_temperature_celsius` - Current averaged indoor temperature

## Grafana Dashboard Integration

You can create a Grafana dashboard showing control loop activity by:
1. Adding a logs panel connected to Loki (if installed)
2. Or using Prometheus metrics to track switch state changes

## Troubleshooting

**No logs showing?**
```bash
# Check if container is running
docker ps | grep iot-api

# Check if control loop is running
curl -s http://localhost:8001/health | grep control_loop_running
```

**Control loop not making decisions?**
```bash
# Check last control loop run time
curl -s http://localhost:8001/health | grep last_control_loop_run

# Should be within last 3-5 minutes (depending on control_interval setting)
```

**See errors in logs?**
```bash
# Filter for errors only
docker logs iot-api 2>&1 | grep -E 'ERROR|CRITICAL'
```

## Log Retention

Docker manages log rotation automatically with the configured limits. To manually clean old logs:

```bash
# Stop container
docker-compose stop api

# Remove log file (will be recreated)
sudo rm /var/lib/docker/containers/$(docker inspect --format='{{.Id}}' iot-api)/*.log

# Restart
docker-compose up -d api
```

## Example Session

```bash
$ ./show_thermostat_history.sh 5

========================================
  Thermostat Control History
  (Last 5 control decisions)
========================================

INFO:main:Averaging 5 temperature samples: ['21.8', '21.9', '21.9', '22.0', '22.0'] -> 21.92°C
INFO:main:Control decision: Temperature 21.9°C in deadband [21.5°C - 22.5°C], maintaining current state
INFO:main:Averaging 5 temperature samples: ['21.7', '21.8', '21.8', '21.9', '21.9'] -> 21.82°C
INFO:main:Control decision: Temperature 21.8°C in deadband [21.5°C - 22.5°C], maintaining current state

========================================
Current Status:
  Mode: AUTO
  Target: 22.0°C
  Current: 21.9°C
  Switch: OFF
  Decision: Temperature in deadband, maintaining current state
========================================
```
