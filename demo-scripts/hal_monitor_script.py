#%%
    #-----------------------------------------------------------------------------------------------------#
    #     This will start the HALServer, MonitorServer, and LOG to a Data base for Grafana to use         #
    #-----------------------------------------------------------------------------------------------------#
# NOTE: If VSCODE crashes and you gets errors starting this script, run "pkill -9 python" in terminal
# This will kill all python processes and free up the ports
#from fridgeos import MonitorServer, MonitorClient, HALServer, HALClient, crc_gl4
from fridgeos.hal.server import HALServer
from fridgeos.monitor.server import MonitorServer

import threading
import time
import time

# Define server and client IPs and ports
ip = '127.0.0.1'
http_port = 8000
hal_port = 5555
hardware_toml_path = 'hal-toml-config/swarm-1k-hal-configuration.toml'

name = '1K GL4'
# Connect to database
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
# Start threads sequentially
# Make threads for HAL
first_thread_HAL_SERVER = threading.Thread(target=run_hal_server)
first_thread_HAL_SERVER.start()

# when HAl finihes starting, start monitor server
time.sleep(5)
second_thread_MONITOR_SERVER = threading.Thread(target=run_monitor_server)
second_thread_MONITOR_SERVER.start()
# Wait for monitor to load json with sensor data before continuing-0