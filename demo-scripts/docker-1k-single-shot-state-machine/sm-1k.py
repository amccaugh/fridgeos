#%%
from fridgeos import HALClient
from fridgeos import MonitorClient
from fridgeos.statemachine.single_shot_1k import Single_shot_1k


# Make a monitor client for the state machine to get metrics
sm_monitor_client = MonitorClient(url=f'http://monitor:8000/', timeout=3)
# Make a HAL client for the state machine to set heater values
sm_hal_client = HALClient(ip='hal', port=5555)
# Make a state machine and input its required params
sm_settings_toml = './config/single_shot_1k_sm_config.toml'
sm = Single_shot_1k(settings_toml = sm_settings_toml, 
             hal_client = sm_hal_client, 
             monitor_client = sm_monitor_client)
sm.non_async__turn_on_state_machine()
