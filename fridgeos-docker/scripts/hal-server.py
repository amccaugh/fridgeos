import uvicorn
from fridgeos.hal import HALServer

print('Attempting to start HAL server')
server = HALServer(port=8001,
                   hardware_toml_path='./config/hal.toml',
                   log_path='./logs/')

print('Starting HAL server on port 8001...')
uvicorn.run(server.app, host="0.0.0.0", port=8001, log_level="info")