#%%
#!/usr/bin/env python3
"""
Demo script to generate fake temperature data for Grafana visualization.
Pushes data to TimescaleDB using the fridgeosuser account.
"""

import psycopg2
import random
import time
from datetime import datetime, timedelta
import numpy as np

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'fridgedb',
    'user': 'fridgeosuser',
    'password': 'fridgeos123'
}

def generate_temperature_data(sensorname, start_time, duration_hours=24, interval_seconds=30):
    """Generate realistic temperature data with some noise and trends."""
    data_points = []
    current_time = start_time
    
    # Base temperature varies by sensor type
    base_temps = {
        'stage1': 4.2,      # Liquid helium stage
        'stage2': 77.0,     # Liquid nitrogen stage  
        'stage3': 300.0,    # Room temperature stage
        'magnet': 4.2,      # Magnet temperature
        'shield': 50.0      # Heat shield
    }
    
    base_temp = base_temps.get(sensorname, 4.2)
    
    for i in range(int(duration_hours * 3600 / interval_seconds)):
        # Add some realistic noise and slow drift
        noise = random.gauss(0, 0.05)  # Small random fluctuations
        drift = 0.1 * np.sin(2 * np.pi * i / (3600 / interval_seconds))  # Hourly cycle
        
        temperature = base_temp + noise + drift
        
        data_points.append({
            'time': current_time,
            'sensorname': sensorname,
            'temperature': float(temperature)
        })
        
        current_time += timedelta(seconds=interval_seconds)
    
    return data_points

def insert_data(cursor, data_points):
    """Insert data points into the database."""
    insert_query = """
    INSERT INTO temperatures (time, sensorname, temperature)
    VALUES (%(time)s, %(sensorname)s, %(temperature)s)
    """
    
    cursor.executemany(insert_query, data_points)

def main():
    """Generate and insert demo temperature data."""
    print("Connecting to database...")
    
    conn = None
    cursor = None
    
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Define sensors
        sensors = ['stage1', 'stage2', 'stage3', 'magnet', 'shield']
        
        # Generate data starting from 24 hours ago
        start_time = datetime.now() - timedelta(hours=24)
        
        print(f"Generating temperature data for {len(sensors)} sensors...")
        
        total_points = 0
        for sensor in sensors:
            print(f"  Generating data for {sensor}")
            data_points = generate_temperature_data(sensor, start_time)
            insert_data(cursor, data_points)
            total_points += len(data_points)
        
        # Commit all changes
        conn.commit()
        print(f"Successfully inserted {total_points} temperature data points!")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main()