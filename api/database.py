"""
Database module
InfluxDB client initialization and query API
"""
from influxdb_client import InfluxDBClient
from config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG


# InfluxDB client (singleton)
influx_client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)

# Query API
query_api = influx_client.query_api()
