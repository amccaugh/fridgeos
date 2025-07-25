#%%
import psycopg2
from datetime import datetime, timezone
import time
from fridgeos.statemachine.client import StateMachineClient


state_machine_client = StateMachineClient(base_url='http://statemachine:8001')

def get_temperature_data():
    """Get temperature data from StateMachine client"""
    try:
        temperatures = state_machine_client.get_temperatures()
        # Remove any temperature entries where the value is None
        temperatures = {k: v for k, v in temperatures.items() if v is not None}
        return temperatures
    except Exception as e:
        print(f"Error getting temperature data: {e}")
        return {}

def get_state_data():
    """Get state data from StateMachine client"""
    try:
        state = state_machine_client.get_state()
        return state
    except Exception as e:
        print(f"Error getting state data: {e}")
        return 'unknown'

def upload_temperatures_to_postgres(temperatures):
    """Upload temperature data to postgres temperatures table"""
    if not temperatures:
        print("No temperature data to upload")
        return
    
    try:
        conn = psycopg2.connect(
            host='postgres',
            port=5432,
            user='fridgeosuser',
            password='fridgeos123',
            database='fridgedb',
            connect_timeout=1
        )
        
        with conn.cursor() as cursor:
            timestamp = datetime.now(timezone.utc)
            
            for sensorname, temperature in temperatures.items():
                sql = """INSERT INTO temperatures (time, sensorname, temperature) 
                        VALUES (%s, %s, %s)"""
                cursor.execute(sql, (timestamp, sensorname, temperature))
            
            conn.commit()
            print(f"Successfully uploaded {len(temperatures)} temperature readings")
            
    except Exception as e:
        print(f"Error uploading to database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def upload_state_to_postgres(state):
    """Upload state data to postgres states table"""
    if not state or state == 'unknown':
        print("No state data to upload")
        return
    
    try:
        conn = psycopg2.connect(
            host='postgres',
            port=5432,
            user='fridgeosuser',
            password='fridgeos123',
            database='fridgedb',
            connect_timeout=1
        )
        
        with conn.cursor() as cursor:
            timestamp = datetime.now(timezone.utc)
            
            sql = """INSERT INTO states (time, state) 
                    VALUES (%s, %s)"""
            cursor.execute(sql, (timestamp, state))
            
            conn.commit()
            print(f"Successfully uploaded state: {state}")
            
    except Exception as e:
        print(f"Error uploading state to database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    while True:
        temperatures = get_temperature_data()
        upload_temperatures_to_postgres(temperatures)
        
        state = get_state_data()
        upload_state_to_postgres(state)
        
        time.sleep(1)