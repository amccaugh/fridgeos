from fridgeos import HALServer
print('Attempting to start HAL server')
server = HALServer(port='5555',
                   hardware_toml_path='./config/hal.toml',
                   log_path = './logs/')