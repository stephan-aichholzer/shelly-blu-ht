"""
Monitor routes
WebSocket live log streaming and monitoring web interface
"""
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import logging

from websocket import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/thermostat/logs")
async def websocket_thermostat_logs(websocket: WebSocket):
    """
    WebSocket endpoint for streaming live thermostat control loop logs

    Same output as watch_thermostat.sh but accessible via web browser.
    Broadcasts control decisions, mode changes, temperature readings, and errors in real-time.
    """
    await ws_manager.connect(websocket)  # This sends history to client
    try:
        # Note: Connection message is sent by ws_manager.connect() along with history
        # No need to send it here again

        # Keep connection alive and wait for broadcasts
        while True:
            # Just keep the connection open - actual logs are broadcast from control loop
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


@router.get("/monitor", response_class=HTMLResponse,
            summary="Live Thermostat Monitor",
            description="Simple web page for monitoring live thermostat control loop logs via WebSocket")
async def monitor_page():
    """Serve simple HTML page for live log monitoring"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Thermostat Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Courier New', monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #4ec9b0;
            margin-bottom: 10px;
        }
        #status {
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 4px;
            font-weight: bold;
        }
        #status.connected {
            background-color: #1e5128;
            color: #4ec9b0;
        }
        #status.disconnected {
            background-color: #5c1f1f;
            color: #f48771;
        }
        #logs {
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 15px;
            height: 70vh;
            overflow-y: auto;
            font-size: 13px;
            line-height: 1.6;
        }
        .log-line {
            margin: 2px 0;
            padding: 2px 0;
        }
        .log-line.info {
            color: #d4d4d4;
        }
        .log-line.mode {
            color: #4ec9b0;
            font-weight: bold;
        }
        .log-line.decision {
            color: #dcdcaa;
        }
        .log-line.switch {
            color: #ce9178;
            font-weight: bold;
        }
        .log-line.error {
            color: #f48771;
            font-weight: bold;
        }
        .timestamp {
            color: #858585;
        }
        button {
            background-color: #0e639c;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
            font-size: 14px;
        }
        button:hover {
            background-color: #1177bb;
        }
        button:disabled {
            background-color: #3e3e42;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <h1>🌡️ Thermostat Monitor</h1>
    <div id="status" class="disconnected">● Connecting...</div>
    <button id="clearBtn" onclick="clearLogs()">Clear Logs</button>
    <button id="reconnectBtn" onclick="reconnect()" style="display:none">Reconnect</button>
    <div id="logs"></div>

    <script>
        let ws;
        const logsDiv = document.getElementById('logs');
        const statusDiv = document.getElementById('status');
        const reconnectBtn = document.getElementById('reconnectBtn');
        const maxLines = 500;  // Keep last 500 lines

        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/thermostat/logs`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                statusDiv.textContent = '● Connected';
                statusDiv.className = 'connected';
                reconnectBtn.style.display = 'none';
            };

            ws.onmessage = function(event) {
                const line = document.createElement('div');
                line.className = 'log-line';

                // Classify log type for styling
                if (event.data.includes('Mode changed') || event.data.includes('Mode=')) {
                    line.className += ' mode';
                } else if (event.data.includes('Control decision:') || event.data.includes('Averaging')) {
                    line.className += ' decision';
                } else if (event.data.includes('Changing switch') || event.data.includes('Switch successfully')) {
                    line.className += ' switch';
                } else if (event.data.includes('ERROR') || event.data.includes('Error')) {
                    line.className += ' error';
                } else {
                    line.className += ' info';
                }

                line.textContent = event.data;
                logsDiv.appendChild(line);

                // Auto-scroll to bottom
                logsDiv.scrollTop = logsDiv.scrollHeight;

                // Limit number of lines
                while (logsDiv.children.length > maxLines) {
                    logsDiv.removeChild(logsDiv.firstChild);
                }
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };

            ws.onclose = function() {
                statusDiv.textContent = '● Disconnected';
                statusDiv.className = 'disconnected';
                reconnectBtn.style.display = 'inline-block';

                // Try to reconnect after 5 seconds
                setTimeout(function() {
                    if (ws.readyState === WebSocket.CLOSED) {
                        addLogLine('Attempting to reconnect...', 'info');
                        connect();
                    }
                }, 5000);
            };
        }

        function addLogLine(text, type) {
            const line = document.createElement('div');
            line.className = 'log-line ' + type;
            line.textContent = text;
            logsDiv.appendChild(line);
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }

        function clearLogs() {
            logsDiv.innerHTML = '';
        }

        function reconnect() {
            if (ws) {
                ws.close();
            }
            connect();
        }

        // Connect on page load
        connect();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
