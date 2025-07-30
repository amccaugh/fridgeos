import uvicorn
from fridgeos.statemachine.server import StateMachineServer
from fridgeos.hal import HALClient

halclient = HALClient(ip='hal', port=8000)

print('Attempting to start State Machine server')
server = StateMachineServer(
    config_path='./config/statemachine.toml',
    log_path='./logs/',
    hal_client=halclient,
    debug=True,
    http_port=8001
)

print('Starting StateMachine server on port 8001...')
uvicorn.run(server.app, host="0.0.0.0", port=8001, log_level="info")
