from fridgeos.statemachine.server import StateMachineServer
from fridgeos.hal.client import HALClient
from fridgeos.monitor.client import MonitorClient

halclient = HALClient(ip = '127.0.0.1', port = 8000)

print('Attempting to start State Machine server')
server = StateMachineServer(
    config_path = './config/statemachine.toml',
    log_path='./logs/',
    hal_client=halclient,
    debug = True,
    http_port=8001,  # Explicitly set, but matches default
)
