#%%
#from fridgeos import MonitorServer, MonitorClient, HALServer, HALClient, crc_gl4
from fridgeos import HALServer
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
    scraper = MonitorClient(url=f'http://localhost:{http_port}/', timeout=0.1)
    while am_running:
        try:
            data_dict = scraper.get_metrics()
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
            except:
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
            except: 
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

'''
async def start_grafana_logger():
    asyncio.create_task(grafana_log(grafana_scraper, am_running=True))
async def stop_grafana_logger():
    asyncio.create_task(grafana_log(grafana_scraper, am_running=False))
    
asyncio.run(start_grafana_logger()) 
'''


# %%

#---------------------------------------------------------------------------------------------------#
 # %%
# Make a monitor client for the state machine to get metrics
sm_monitor_client = MonitorClient(url=f'http://localhost:{http_port}/', timeout=3)
# Make a HAL client for the state machine to set heater values
sm_hal_client = HALClient(ip=ip, port=hal_port)
# Make a state machine and input it srequired params
sm_settings_toml = '../fridgeos/statemachine/crc_gl4_sm_config.toml'
sm = crc_gl4(settings_toml = sm_settings_toml, 
             hal_client = sm_hal_client, 
             monitor_client = sm_monitor_client)
sm.non_async__turn_on_state_machine()
'''
# Start the state machine
# To communicate with the SM while it is running, we msut use asyncio
async def start_state_machine():
    asyncio.create_task(sm.turn_on_state_machine())
async def stop_state_machine():
    asyncio.create_task(sm.turn_off_state_machine())

# asyncio.run doesn't work with jupyter because jupyter has its own event loop
#asyncio.run(main()) 

await start_state_machine()
'''
#await stop_state_machine()

#%%

import csv
import pandas as pd
import asyncio

logging_monitor_client = MonitorClient(url=f'http://localhost:{http_port}/', timeout=0.1)
logging_monitor_client.get_metrics()

async def log_metrics_to_csv():
    with open('metrics_log_sm.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp', 'temperatures', 'heaters'])
        while True:
            metrics = logging_monitor_client.get_metrics()
            timestamp = time.time()
            temperatures = metrics.get('temperatures', {})
            heaters = metrics.get('heaters', {})
            writer.writerow([timestamp, temperatures, heaters])
            await asyncio.sleep(1)

# Function to start logging metrics to CSV
async def start_logging():
    global logging_task
    logging_task = asyncio.create_task(log_metrics_to_csv())

# Function to stop logging metrics to CSV
async def stop_logging():            print(f'{data}')

    logging_task.cancel()
    try:
        await logging_task
    except asyncio.CancelledError:
        pass

# Start logging metrics to CSV
await start_logging()

# To stop logging, call await stop_logging()

# %%
import matplotlib.pyplot as plt

# Read the CSV file into a DataFrame
df = pd.read_csv('metrics_log.csv')

# Convert the 'timestamp' column to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

# Function to plot subkeys in a column on the same plot
def plot_subkeys(column_name):
    # Drop rows with NaN values in the specified column
    df_filtered = df.dropna(subset=[column_name])
    
    # Extract subkeys from the JSON-like strings in the specified column
    subkeys = df_filtered[column_name].apply(eval).apply(pd.Series)
    
    # Plot each subkey on the same plot
    plt.figure()
    for subkey in subkeys.columns:
        plt.plot(df_filtered['timestamp'], subkeys[subkey], label=subkey)
    plt.xlabel('Timestamp')
    plt.ylabel(column_name)
    plt.title(f'{column_name} Subkeys')
    plt.legend()
    plt.show()

# Plot subkeys in the 'temperatures' column
plot_subkeys('temperatures')

# Plot subkeys in the 'heaters' column

# Plot subkeys in the 'heaters' column
# %%

from simple_pid import PID
class ElapsedTime:
    def __init__(self, threshold_seconds=None):
        """
        Initialize the ElapsedTime object.
    

        Parameters:
        - threshold_seconds (float, optional): The time threshold in seconds.
          If None, threshold checks will not be performed.
        """
        self.threshold_seconds = threshold_seconds
        self.start_time = time.time()

    def reset(self):
        """
        Reset the timer.
        """
        self.start_time = time.time()

    def __call__(self):
        """
        Check if the elapsed time exceeds the optional threshold and return elapsed time.

        Returns:
        - (bool or None, float): A tuple containing:
            - bool: True if elapsed time exceeds the threshold, False otherwise. 
                    If no threshold is provided, this is None.
            - float: Elapsed time in seconds since the timer was started.
        """
        elapsed_time = time.time() - self.start_time

        # Check if threshold_seconds is provided
        if self.threshold_seconds is None:
            return None, elapsed_time
        
        return elapsed_time >= self.threshold_seconds, elapsed_time

    def time_remaining(self):
        """
        Get the remaining time until the threshold is reached.

        Returns:
        - float or None: Time remaining in seconds. 
                         If the threshold is exceeded, returns 0.
                         If no threshold is set, returns None.
        """
        if self.threshold_seconds is None:
            return None

        elapsed = time.time() - self.start_time
        return max(0, self.threshold_seconds - elapsed)

sm_monitor_client = MonitorClient(url=f'http://localhost:{http_port}/', timeout=3)
sm_hal_client = HALClient(ip=ip, port=hal_port)
test_fridge_time = ElapsedTime()
metrics = sm_monitor_client.get_metrics()
sensor = '4PUMP'
set_point_S = 0
max_value = metrics['heater_max_values'][sensor]
p = PID(Kp = 10, Ki=1, output_limits = (0, max_value),sample_time=None)


while True:
    # Get the temperature of the switch
    metrics = sm_monitor_client.get_metrics()
    fridge_dt = test_fridge_time()[1]
    test_fridge_time.reset()

    switch_temp  = metrics['temperatures'][sensor]
    # Temperature goal
    p.setpoint = set_point_S
    # Get the new heater value from the PID controller
    heater_value = p(switch_temp, dt = fridge_dt)
    sm_hal_client.set_heater_value(sensor, heater_value)
    print(f'Switch temp: {switch_temp}, Heater value: {heater_value}, dt: {fridge_dt}')
    time.sleep(2)




# %%
