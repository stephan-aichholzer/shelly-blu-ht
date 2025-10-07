# Architecture v3.0 - Thermostat Control System

## Overview

Version 3.0 extends the v2.0 HTTP polling architecture with intelligent thermostat control capabilities, transforming the system from a passive monitoring solution into an active environmental control system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hardware Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│  Shelly BLU H&T Sensors (BT)  →  Shelly Pro 2 (Gateway+Switch)  │
│  • temp_outdoor (200)                                            │
│  • temp_indoor (201) ← Used for control                         │
│  • temp_buffer (202)                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP/RPC
┌─────────────────────────────────────────────────────────────────┐
│                   Data Collection Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  Sensor Poller (every 30s)                                      │
│  • Polls Shelly BTHomeDevice.GetStatus                          │
│  • Writes to InfluxDB (temp, humidity, battery)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│  InfluxDB                                                        │
│  • Time-series sensor data                                      │
│  • Historical analysis                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓ Query
┌─────────────────────────────────────────────────────────────────┐
│                   Control Layer (NEW in v3.0)                    │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI + Thermostat Control Loop (every 60-600s configurable) │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Query InfluxDB for last N temperature samples         │  │
│  │ 2. Calculate moving average                              │  │
│  │ 3. Apply control logic:                                  │  │
│  │    - Hysteresis (symmetric deadband)                     │  │
│  │    - Minimum ON/OFF time constraints                     │  │
│  │    - Mode-based decisions (AUTO/ECO/ON/OFF)             │  │
│  │ 4. Execute switch control via Shelly RPC                 │  │
│  │ 5. Log decision and update state                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP/RPC
┌─────────────────────────────────────────────────────────────────┐
│                    Output Layer                                  │
├─────────────────────────────────────────────────────────────────┤
│  • Shelly Pro 2 Switch Control                                  │
│  • Prometheus Metrics (/metrics)                                │
│  • REST API (thermostat config/status)                          │
│  • OpenAPI Documentation (/docs)                                │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Temperature Averaging (NEW)

**Problem:** Slow-responding heating systems (underfloor heating, large radiators) require stable temperature readings to avoid oscillation.

**Solution:** Configurable moving average of last N samples.

```python
# Query last N samples from InfluxDB
samples = query_temperature(sensor="temp_indoor", limit=N)

# Calculate average
avg_temp = sum(samples) / len(samples)

# Use averaged temperature for control decisions
```

**Benefits:**
- Reduces noise from sensor variations
- Prevents rapid on/off cycling
- Configurable sample count (1-10, default: 3)
- Adapts to system thermal response time

### 2. Control Loop Architecture

**Background Task:** Async control loop runs continuously as FastAPI background task.

```python
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(thermostat_control_loop())

async def thermostat_control_loop():
    while True:
        execute_control_logic()
        await asyncio.sleep(control_interval)  # Default: 180s
```

**Why Background Task:**
- ✅ Runs independently of API requests
- ✅ No external scheduler needed (cron, etc.)
- ✅ Survives API restarts automatically
- ✅ Easy to monitor and health-check
- ✅ Logs integrated with main API logs

### 3. Control Logic

**Hysteresis Control (Symmetric Deadband):**

```
Temperature Zones:

     │<────── Hysteresis ──────>│<────── Hysteresis ──────>│
     │                                                        │
 ────┴────────────────────────┬───────────────────────────┴────

     Turn ON               Deadband              Turn OFF
  (< target - h)      (maintain state)       (>= target + h)
```

**Example with target=22°C, hysteresis=0.5°C:**
- Turn ON when: temp < 21.5°C (and timing allows)
- Turn OFF when: temp >= 22.5°C (and timing allows)
- Deadband (21.5-22.5°C): Maintain current state

**Timing Constraints:**
- `min_on_time`: Minimum minutes to keep switch ON (prevents short heating bursts)
- `min_off_time`: Minimum minutes to keep switch OFF (prevents rapid cycling)

**Control Decision Logic:**

```python
def calculate_control_decision(temp, target, hysteresis,
                               current_state, last_change_time,
                               min_on_time, min_off_time):

    turn_on_threshold = target - hysteresis
    turn_off_threshold = target + hysteresis
    time_since_change = now - last_change_time

    # In deadband - maintain current state
    if turn_on_threshold <= temp < turn_off_threshold:
        return current_state

    # Below threshold - want to turn ON
    if temp < turn_on_threshold:
        if current_state == ON:
            return ON  # Already on
        else:
            # Check minimum OFF time elapsed
            if time_since_change >= min_off_time:
                return ON  # Can turn on now
            else:
                return OFF  # Still locked off

    # Above threshold - want to turn OFF
    if temp >= turn_off_threshold:
        if current_state == OFF:
            return OFF  # Already off
        else:
            # Check minimum ON time elapsed
            if time_since_change >= min_on_time:
                return OFF  # Can turn off now
            else:
                return ON  # Still locked on
```

### 4. Operating Modes

**AUTO Mode:**
- Uses `target_temp` setpoint
- Full control logic active
- Typical use: Normal operation

**ECO Mode:**
- Uses `eco_temp` setpoint (typically lower, e.g., 18°C)
- Full control logic active
- Typical use: Away from home, vacation mode

**ON Mode:**
- Forces switch permanently ON
- Ignores temperature readings
- Manual override
- Typical use: Emergency heating, testing

**OFF Mode:**
- Forces switch permanently OFF
- Ignores temperature readings
- Manual override
- Typical use: Summer, maintenance

### 5. Persistent State Management

**Configuration Storage:**
```
Host: ./data/thermostat_config.json
Container: /data/thermostat_config.json
```

**Structure:**
```json
{
  "config": {
    "target_temp": 22.0,
    "eco_temp": 18.0,
    "mode": "AUTO",
    "hysteresis": 0.5,
    "min_on_time": 30,
    "min_off_time": 10,
    "temp_sample_count": 3,
    "control_interval": 180
  },
  "state": {
    "switch_on": false,
    "last_switch_change": "2025-10-07T18:00:00Z",
    "last_control_decision": "..."
  }
}
```

**Why JSON File:**
- ✅ Human-readable and editable
- ✅ Survives container restarts
- ✅ Can be edited directly on host
- ✅ No database complexity
- ✅ Easily backed up
- ✅ Version control friendly

### 6. Health Monitoring & Auto-Recovery

**Docker Healthcheck:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health | grep -q '"status":"healthy"'
```

**Health Checks:**
1. **InfluxDB Connection:** Can query sensor data?
2. **Shelly Connection:** Can reach switch controller?
3. **Control Loop:** Running and recent execution?
4. **Error State:** No consecutive failures?

**Auto-Recovery:**
```
Health Check Fails × 3 (90 seconds)
         ↓
Docker marks container unhealthy
         ↓
Docker restarts container (restart: unless-stopped)
         ↓
Container starts with persisted config
         ↓
Control loop resumes automatically
```

### 7. Logging & Observability

**Log Levels:**
```python
INFO  - Normal operations (every cycle)
DEBUG - Detailed state information
WARN  - Recoverable issues (sensor offline)
ERROR - Control loop errors (retries)
CRITICAL - Multiple consecutive failures (needs attention)
```

**Log Rotation:**
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

**What Gets Logged:**
1. Temperature sample averaging
2. Control decisions with reasoning
3. Switch state changes
4. Timing lock status
5. Errors and recovery attempts

**Example Log Sequence:**
```
INFO:main:Averaging 3 temperature samples: ['21.8', '21.9', '22.0'] -> 21.90°C
INFO:main:Control decision: Turning ON: 21.9°C < 21.5°C (OFF for 15min >= 10min)
INFO:main:Changing switch state: False -> True
INFO:main:Switch successfully set to ON
```

## Network Architecture

**v2.0 Limitation:** Used host network mode to access Shelly, broke Grafana compatibility.

**v3.0 Solution:** Bridge network with `extra_hosts`:

```yaml
api:
  ports:
    - "8001:8000"  # Grafana-compatible
  extra_hosts:
    - "host.docker.internal:host-gateway"  # Access Shelly on LAN
```

**Benefits:**
- ✅ Standard port mapping (8001:8000)
- ✅ Grafana can scrape metrics
- ✅ Can still reach Shelly on host network
- ✅ Better Docker isolation

## API Architecture

**RESTful Design:**

```
/api/v1/
├── sensors              GET     List all sensors
├── temperature          GET     Temperature history
├── humidity             GET     Humidity history
├── battery              GET     Battery levels
├── latest               GET     Latest readings
└── thermostat/
    ├── config           GET     Current configuration
    │                    POST    Update configuration
    ├── status           GET     Current status + decision
    └── switch           POST    Manual switch control

/metrics                 GET     Prometheus metrics
/health                  GET     Health status (extended)
/docs                    GET     OpenAPI documentation
```

**Configuration Endpoint:**
- GET: Returns current config from JSON file
- POST: Validates, saves to JSON file, returns updated config
- Pydantic validation ensures safe values

**Status Endpoint:**
Returns comprehensive state:
- Current configuration
- All sensor temperatures (outdoor, indoor, buffer)
- Switch state (ON/OFF)
- Active target temperature (based on mode)
- Control decision (heating needed?)
- Reason for decision (human-readable)
- Switch lock status (remaining time)

## Comparison with v2.0

| Feature | v2.0 | v3.0 |
|---------|------|------|
| **Purpose** | Monitoring | Monitoring + Control |
| **Services** | 3 (sensor-poller, influxdb, api) | 3 (same) |
| **Shelly** | Read-only (sensors) | Read sensors + Control switch |
| **Control Loop** | None | Async background task |
| **Modes** | N/A | AUTO, ECO, ON, OFF |
| **Temperature** | Single sample | Moving average (configurable) |
| **Safety** | N/A | Hysteresis + timing constraints |
| **Health Check** | Basic | Extended (includes control loop) |
| **Logging** | Standard | Structured + rotation |
| **Config** | Environment vars | JSON file + ENV |
| **Persistence** | None | Config + state |
| **API Endpoints** | 6 | 10 (added 4 thermostat) |
| **Grafana Port** | 8001 | 8001 (fixed in v3.0) |

## Performance Characteristics

**Control Loop Overhead:**
- Runs every 180s by default (configurable 60-600s)
- ~100ms per cycle (query InfluxDB + calculate + call Shelly)
- Negligible impact on API response times

**Memory Usage:**
- v2.0: ~200 MB (API container)
- v3.0: ~210 MB (API container with thermostat)
- Increase: ~10 MB (control loop state + JSON config)

**Disk Usage:**
- Logs: ~30 MB max (10MB × 3 files with rotation)
- Config: <1 KB
- No additional database storage needed

## Design Trade-offs

### Why Not MQTT for Control?

❌ **MQTT Approach:**
- Requires message broker
- Async message handling
- Potential message loss
- More complex error handling
- Need QoS management

✅ **HTTP RPC Approach:**
- Direct request-response
- Immediate error feedback
- Simple retry logic
- Easy to debug with curl
- No additional infrastructure

### Why Background Task vs. Separate Service?

❌ **Separate Service:**
- Another container to manage
- Inter-service communication
- Duplicate health monitoring
- More complex deployment

✅ **Background Task in API:**
- Single container
- Shared InfluxDB client
- Integrated logging
- Simpler health checks
- Easier to maintain

### Why JSON File vs. Database?

❌ **Database Storage:**
- Need database container
- Schema migrations
- Connection management
- Backup complexity

✅ **JSON File:**
- Human-readable
- Easy to edit
- Simple backup (file copy)
- Version control friendly
- No dependencies

## Future Enhancements

Possible v3.1 features:
- PID control algorithm option
- Schedule-based mode switching
- Weather-based eco mode
- Multiple zone support
- Energy usage tracking
- Grafana dashboard templates

## Conclusion

Version 3.0 transforms the system from passive monitoring to active control while maintaining the simplicity principle established in v2.0. The architecture prioritizes:

1. **Simplicity:** Single additional file, no new services
2. **Reliability:** Health checks + auto-restart
3. **Safety:** Multiple protection mechanisms
4. **Observability:** Comprehensive logging
5. **Maintainability:** Human-readable configuration
6. **Performance:** Minimal overhead

The result is a production-ready thermostat system that's simple enough for a home deployment yet robust enough for reliable operation.
