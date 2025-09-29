FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    influxdb-client==1.38.0 \
    requests==2.31.0

# Copy poller script
COPY poller.py /app/

# Create non-root user
RUN useradd -r -s /bin/false polleruser && \
    chown -R polleruser:polleruser /app

USER polleruser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-u", "poller.py"]