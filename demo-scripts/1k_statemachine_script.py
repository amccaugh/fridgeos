    #-----------------------------------------------------------------------------------------------------#
    #     This will start the HALClient, MonitorClient, and State machine                                 #
    #-----------------------------------------------------------------------------------------------------#
    # Non-async version is blocking but can see print statements4Head is starting to warm up > 1K, Will begin recycle

    # Async version is non-blocking but can't see print statements
    #-----------------------------------------------------------------------------------------------------#
from fridgeos.hal.client import HALClient
from fridgeos.monitor.client import MonitorClient
from fridgeos.statemachine.crc_gl4 import crc_gl4

# Define server and client IPs and ports
ip = '127.0.0.1'
http_port = 8000
hal_port = 5555
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

# Start the state machine
# To communicate with the SM while it is running, we msut use asyncio
#async def start_state_machine():
#    asyncio.create_task(sm.turn_on_state_machine())
#async def stop_state_machine():
#    asyncio.create_task(sm.turn_off_state_machine())

# asyncio.run doesn't work with jupyter because jupyter has its own event loop
#asyncio.run(main()) 

#await start_state_machine()

#await stop_state_machine()