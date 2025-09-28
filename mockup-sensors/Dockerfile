FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN pip install --no-cache-dir paho-mqtt

# Copy the simulator script
COPY sensor_simulator.py /app/

# Create a non-root user
RUN useradd -r -s /bin/false mockuser && \
    chown -R mockuser:mockuser /app

USER mockuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import paho.mqtt.client as mqtt; c = mqtt.Client(); c.connect('mosquitto', 1883, 60); c.disconnect()" || exit 1

CMD ["python", "sensor_simulator.py"]