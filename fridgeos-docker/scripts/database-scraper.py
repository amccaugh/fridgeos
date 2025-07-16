#%%
from fridgeos import MonitorClient
import psycopg2
from datetime import datetime, timezone
import time

monitor_client = MonitorClient(url = 'http://localhost:8000/', timeout = 0.1)

def get_temperature_data():
    """Get temperature data from monitor client"""
    try:
        all_metrics = monitor_client.get_metrics()
        temperatures = all_metrics.get('temperatures', {})
        metadata = all_metrics.get('metadata', {})
        fridgename = metadata.get('cryostat_name', 'unknown')
        return temperatures, fridgename
    except Exception as e:
        print(f"Error getting temperature data: {e}")
        return {}, 'unknown'

def upload_temperatures_to_postgres(temperatures, fridgename):
    """Upload temperature data to postgres temperatures table"""
    if not temperatures:
        print("No temperature data to upload")
        return
    
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='fridgeosuser',
            password='fridgeos123',
            database='fridgedb',
            connect_timeout=1
        )
        
        with conn.cursor() as cursor:
            timestamp = datetime.now(timezone.utc)
            
            for sensorname, temperature in temperatures.items():
                sql = """INSERT INTO temperatures (time, fridgename, sensorname, temperature) 
                        VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (timestamp, fridgename, sensorname, temperature))
            
            conn.commit()
            print(f"Successfully uploaded {len(temperatures)} temperature readings")
            
    except Exception as e:
        print(f"Error uploading to database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    while True:
        temperatures, fridgename = get_temperature_data()
        upload_temperatures_to_postgres(temperatures, fridgename)
        time.sleep(1)