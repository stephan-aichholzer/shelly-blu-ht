#!/bin/bash
# Sensor Health Check Script
# Checks if BLU H&T sensors are updating and in range

SHELLY_IP="${SHELLY_IP:-192.168.2.12}"
ALERT_THRESHOLD_MINUTES=5  # Alert if no update in 5 minutes

echo "=== Shelly BLU H&T Sensor Health Check ==="
echo "Time: $(date)"
echo "Shelly IP: $SHELLY_IP"
echo ""

# Function to check a sensor
check_sensor() {
    local sensor_id=$1
    local sensor_name=$2

    echo "Checking: $sensor_name (ID: $sensor_id)"

    # Get sensor status
    response=$(curl -s "http://${SHELLY_IP}/rpc/BTHomeDevice.GetStatus?id=${sensor_id}")

    # Parse device status values
    last_updated=$(echo "$response" | jq -r '.last_updated_ts')
    rssi=$(echo "$response" | jq -r '.rssi')
    battery=$(echo "$response" | jq -r '.battery')
    paired=$(echo "$response" | jq -r '.paired')

    # Get sensor values based on sensor ID mapping
    # Device 200: temp=202, humidity=201, battery=200
    # Device 201: temp=205, humidity=204, battery=203
    if [ "$sensor_id" = "200" ]; then
        temp_sensor_id=202
        humidity_sensor_id=201
    else
        temp_sensor_id=205
        humidity_sensor_id=204
    fi

    # Get temperature
    temp=$(curl -s "http://${SHELLY_IP}/rpc/BTHomeSensor.GetStatus?id=${temp_sensor_id}" | jq -r '.value // "N/A"')

    # Get humidity
    humidity=$(curl -s "http://${SHELLY_IP}/rpc/BTHomeSensor.GetStatus?id=${humidity_sensor_id}" | jq -r '.value // "N/A"')

    # Current time
    current_time=$(date +%s)
    age_seconds=$((current_time - last_updated))
    age_minutes=$((age_seconds / 60))

    # Format last update time
    if command -v date >/dev/null 2>&1; then
        last_update_readable=$(date -d @${last_updated} "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date -r ${last_updated} "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "N/A")
    else
        last_update_readable="timestamp: $last_updated"
    fi

    echo "  Paired: $paired"
    echo "  Temperature: ${temp}°C"
    echo "  Humidity: ${humidity}%"
    echo "  Battery: ${battery}%"
    echo "  RSSI: ${rssi} dBm"
    echo "  Last Update: $last_update_readable"
    echo "  Age: ${age_minutes} minutes ago"

    # Signal strength interpretation
    if [ "$rssi" -gt -50 ]; then
        signal="Excellent"
    elif [ "$rssi" -gt -60 ]; then
        signal="Good"
    elif [ "$rssi" -gt -70 ]; then
        signal="Fair"
    else
        signal="Poor"
    fi
    echo "  Signal: $signal"

    # Health check
    if [ "$age_minutes" -lt "$ALERT_THRESHOLD_MINUTES" ]; then
        echo "  Status: ✅ HEALTHY"
    else
        echo "  Status: ⚠️  WARNING - No update in $age_minutes minutes!"
        echo "           (Expected update every 1 minute)"
    fi

    echo ""
}

# Check both sensors
check_sensor 200 "temp_outdoor"
check_sensor 201 "temp_indoor"

echo "=== Notes ==="
echo "- BLU H&T sensors broadcast every 1 minute"
echo "- Excellent RSSI: > -50 dBm"
echo "- Good RSSI: -50 to -60 dBm"
echo "- Fair RSSI: -60 to -70 dBm"
echo "- Poor RSSI: < -70 dBm"
echo ""
echo "If sensors aren't updating:"
echo "1. Check if they're in Bluetooth range (typically 10-30m)"
echo "2. Check battery level"
echo "3. Try moving sensors closer to Shelly Pro 2"