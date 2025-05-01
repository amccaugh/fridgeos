from fridgeos import HALServer
print('Attempting to start HAL server')
server = HALServer(port='5555',
                   hardware_toml_path='./hal-toml-config/hpd-1k-hal-config.toml',
                   log_path = './logs/')
