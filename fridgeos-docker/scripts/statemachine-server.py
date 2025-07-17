from fridgeos import StateMachineServer
from fridgeos import HALClient
from fridgeos import MonitorClient

monitor_client = MonitorClient(url = 'http://monitor:8000/', timeout = 0.1)
halclient = HALClient(ip = '127.0.0.1', port = 5555)

print('Attempting to start State Machine server')
server = StateMachineServer(
    config_path = './config/statemachine.toml',
    log_path='./logs/',
    monitor_client=monitor_client,
    hal_client=halclient,
    debug = True,
    http_port=8001,  # Explicitly set, but matches default
)
