#!/bin/bash
# Watch thermostat control loop in real-time
# Shows: temperature averaging, control decisions, and switch actions

echo "========================================"
echo "  Thermostat Control Loop Monitor"
echo "========================================"
echo "Monitoring control loop decisions..."
echo "Press Ctrl+C to stop"
echo ""

docker logs -f --tail 20 --timestamps iot-api 2>&1 | grep --line-buffered -E 'Averaging|Control decision|Changing switch|Turning|ERROR|CRITICAL'
