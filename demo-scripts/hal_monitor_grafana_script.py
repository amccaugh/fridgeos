#%%
    #-----------------------------------------------------------------------------------------------------#
    #     This will start the HALServer, MonitorServer, and LOG to a Data base for Grafana to use         #
    #-----------------------------------------------------------------------------------------------------#
# NOTE: If VSCODE crashes and you gets errors starting this script, run "pkill -9 python" in terminal
# This will kill all python processes and free up the ports
#from fridgeos import MonitorServer, MonitorClient, HALServer, HALClient, crc_gl4
from fridgeos.hal.server import HALServer
from fridgeos.hal.client import HALClient
from fridgeos.monitor.server import MonitorServer
from fridgeos.monitor.client import MonitorClient
from fridgeos.statemachine.crc_gl4 import crc_gl4

import threading
import time
import asyncio
import time
import psycopg2
from datetime import datetime, timezone

# Define server and client IPs and ports
ip = '127.0.0.1'
http_port = 8000
hal_port = 5555
hardware_toml_path = 'hal-toml-config/swarm-1k-hal-configuration.toml'

name = '1K GL4'
# Connect to database
conn = psycopg2.connect(
host = "example.com",
user = "myuser",
port = 5432,
password = "mypass",
database = "qittlab",)
ip = '127.0.0.1'
http_port = 8000

# Function to run HALServer
def run_hal_server():
    server = HALServer(port=hal_port,
                       hardware_toml_path=f'{hardware_toml_path}',
                       log_path='./logs/')
# Function to run MonitorServer
def run_monitor_server():
    monitor_server = MonitorServer(cryostat_name=f'{name}',
                                   http_port=http_port,
                                   hal_ip=ip,
                                   hal_port=hal_port,
                                   min_update_period=1)
# Function to log data to grafana
def grafana_log(am_running=True):
    scraper = MonitorClient(url=f'http://localhost:{http_port}/', timeout=3)
    while am_running:
        try:
            data_dict, success = scraper.get_metrics()
            cur = conn.cursor()
            timestamp = datetime.now(timezone.utc)
            sql = (f"INSERT INTO cryostats"
                    "(time, name, sensor, value) "
                    "VALUES (%(time)s, %(name)s, %(sensor)s, %(value)s)")
            try:
                for sensor,temperature in data_dict['temperatures'].items():
                    data = {
                        'time': timestamp,
                        'name': '1K_GL4_3341',
                        'sensor': sensor,
                        'value': temperature,
                        }
                    cur.execute(sql, data)
            except Exception as e:
                print(f'Thermometer grafana Error: {e}')
                pass
            try:
                for key, value in data_dict['heaters'].items():
                    if key == '4SWITCH':
                        data = {
                            'time': timestamp,
                            'name': '1K_GL4_3341',
                            'sensor': f'{key}_heater',
                            'value': value
                            }
                        cur.execute(sql, data)

                    elif key == '4PUMP':
                        for sub_key,value in data_dict['heaters'][f'{key}'].items():
                            data = {
                                'time': timestamp,
                                'name': '1K_GL4_3341',
                                'sensor': f'{key}_{sub_key}',
                                'value': value
                                }
                            cur.execute(sql, data)
            except Exception as e:
                print(f'Heater grafana Error: {e}') 
                pass
            conn.commit()
            time.sleep(5)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f'Error: {e}')
            time.sleep(5)
            pass
# Start threads sequentially
# Make threads for HAL
first_thread_HAL_SERVER = threading.Thread(target=run_hal_server)
first_thread_HAL_SERVER.start()

# when HAl finihes starting, start monitor server
time.sleep(5)
second_thread_MONITOR_SERVER = threading.Thread(target=run_monitor_server)
second_thread_MONITOR_SERVER.start()
# Wait for monitor to load json with sensor data before continuing-0
time.sleep(5)
third_thread_grafana_logger = threading.Thread(target=grafana_log)
third_thread_grafana_logger.start()