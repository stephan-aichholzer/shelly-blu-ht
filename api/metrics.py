"""
Prometheus metrics module
All metric definitions for monitoring and observability
"""
from prometheus_client import Counter, Histogram, Gauge


# API Request Metrics
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint']
)

REQUEST_DURATION = Histogram(
    'api_request_duration_seconds',
    'API request duration'
)

# Sensor Metrics
SENSOR_TEMPERATURE = Gauge(
    'sensor_temperature_celsius',
    'Current temperature',
    ['device_id', 'sensor_id', 'sensor_name']
)

SENSOR_HUMIDITY = Gauge(
    'sensor_humidity_percent',
    'Current humidity',
    ['device_id', 'sensor_id', 'sensor_name']
)

SENSOR_BATTERY = Gauge(
    'sensor_battery_percent',
    'Current battery level',
    ['device_id', 'sensor_id', 'sensor_name']
)

SENSOR_LAST_SEEN = Gauge(
    'sensor_last_seen_timestamp',
    'Last seen timestamp',
    ['device_id', 'sensor_id', 'sensor_name']
)

# Thermostat Metrics
THERMOSTAT_SWITCH_STATE = Gauge(
    'thermostat_switch_state',
    'Thermostat switch state (1=ON, 0=OFF)'
)

THERMOSTAT_TARGET_TEMP = Gauge(
    'thermostat_target_temperature_celsius',
    'Thermostat target temperature'
)

THERMOSTAT_CURRENT_TEMP = Gauge(
    'thermostat_current_temperature_celsius',
    'Current indoor temperature used for control'
)
