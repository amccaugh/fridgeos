#%%
#from fridgeos import MonitorServer, MonitorClient, HALServer, HALClient, crc_gl4
from fridgeos import HALClient
from fridgeos import MonitorClient
from fridgeos.single_shot_1k import Single_shot_1k

# Define server and client IPs and ports
ip = '127.0.0.1'
http_port = 8000
hal_port = 5555


# Make a monitor client for the state machine to get metrics
sm_monitor_client = MonitorClient(url=f'http://localhost:{http_port}/', timeout=3)
# Make a HAL client for the state machine to set heater values
sm_hal_client = HALClient(ip=ip, port=hal_port)
# Make a state machine and input its required params
sm_settings_toml = './config/single_shot_1k_sm_config.toml'
sm = Single_shot_1k(settings_toml = sm_settings_toml, 
             hal_client = sm_hal_client, 
             monitor_client = sm_monitor_client)
sm.non_async__turn_on_state_machine()
