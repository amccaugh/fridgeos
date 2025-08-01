#%%
import psycopg2
from datetime import datetime, timezone
import time
from fridgeos.statemachine import StateMachineClient


state_machine_client = StateMachineClient(base_url='http://statemachine:8000')

# Keep track of last seen update_num to avoid duplicate uploads
last_update_num = -1

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

def get_info_data():
    """Get all info data from StateMachine client"""
    try:
        info = state_machine_client.get_info()
        return info
    except Exception as e:
        print(f"Error getting info data: {e}")
        return None

def get_heater_data():
    """Get heater data from StateMachine client"""
    try:
        # Get the root endpoint which includes current_heater_values
        heater_values = state_machine_client.get_heaters()
        # Remove any heater entries where the value is None
        heater_values = {k: v for k, v in heater_values.items() if v is not None}
        return heater_values
    except Exception as e:
        print(f"Error getting heater data: {e}")
        return {}

def is_data_new(info_data):
    """Check if the info data is new based on update_num"""
    global last_update_num
    if info_data is None:
        return False
    
    current_update_num = info_data.get('update_num', 0)
    if current_update_num > last_update_num:
        last_update_num = current_update_num
        return True
    return False

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

def upload_heaters_to_postgres(heaters):
    """Upload heater data to postgres heaters table"""
    if not heaters:
        print("No heater data to upload")
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
            
            for heatername, value in heaters.items():
                sql = """INSERT INTO heaters (time, heatername, value) 
                        VALUES (%s, %s, %s)"""
                cursor.execute(sql, (timestamp, heatername, value))
            
            conn.commit()
            print(f"Successfully uploaded {len(heaters)} heater readings")
            
    except Exception as e:
        print(f"Error uploading heaters to database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    while True:
        # Get info data to check if update is new
        info_data = get_info_data()
        
        if is_data_new(info_data):
            print(f"New data detected (update_num: {info_data.get('update_num', 'unknown')})")
            
            # Extract data from info response
            temperatures = info_data.get('current_temperatures', {})
            # Remove any temperature entries where the value is None
            temperatures = {k: v for k, v in temperatures.items() if v is not None}
            upload_temperatures_to_postgres(temperatures)
            
            # Extract state from info response
            state = info_data.get('current_state', 'unknown')
            upload_state_to_postgres(state)
            
            # Extract heater values from info response
            heaters = info_data.get('current_heater_values', {})
            # Remove any heater entries where the value is None
            heaters = {k: v for k, v in heaters.items() if v is not None}
            upload_heaters_to_postgres(heaters)
        else:
            print("No new data, skipping upload")
        
        time.sleep(1)