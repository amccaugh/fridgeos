from fridgeos.hal.server import HALServer
print('Attempting to start HAL server')
server = HALServer(port=8000,
                   hardware_toml_path='../fridgeos/config/hardware.toml',
                   log_path = './logs/')