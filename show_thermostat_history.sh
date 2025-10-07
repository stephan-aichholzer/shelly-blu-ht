#!/bin/bash
# Show thermostat control history from logs
# Usage: ./show_thermostat_history.sh [lines]

LINES=${1:-50}

echo "========================================"
echo "  Thermostat Control History"
echo "  (Last $LINES control decisions)"
echo "========================================"
echo ""

docker logs --tail 500 iot-api 2>&1 | \
  grep -E 'Averaging|Control decision|Changing switch|Turned|ERROR' | \
  tail -n "$LINES" | \
  while IFS= read -r line; do
    # Add timestamp formatting and color coding
    if echo "$line" | grep -q "Averaging"; then
      echo -e "\033[0;36m$line\033[0m"  # Cyan for averaging
    elif echo "$line" | grep -q "Changing switch"; then
      echo -e "\033[1;33m$line\033[0m"  # Yellow/bold for switch changes
    elif echo "$line" | grep -q "ERROR"; then
      echo -e "\033[0;31m$line\033[0m"  # Red for errors
    else
      echo "$line"
    fi
  done

echo ""
echo "========================================"
echo "Current Status:"
curl -s http://localhost:8001/api/v1/thermostat/status | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(f\"  Mode: {d['config']['mode']}\")
    print(f\"  Target: {d['active_target']}°C\")
    print(f\"  Current: {d['current_temp']}°C\")
    print(f\"  Switch: {'ON' if d['switch_state'] else 'OFF'}\")
    print(f\"  Decision: {d['reason']}\")
except:
    print('  (Unable to fetch current status)')
"
echo "========================================"
