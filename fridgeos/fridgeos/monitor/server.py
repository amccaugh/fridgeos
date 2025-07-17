import time
from fridgeos.hal.client  import HALClient
from fridgeos.statemachine.client import StateMachineClient
from fridgeos.logger import FridgeLogger
from fridgeos.metricserver import MetricServer

class MonitorServer:
    def __init__(self,
                 http_port,
                 hal_ip,
                 hal_port,
                 statemachine_ip,
                 statemachine_port,
                 min_update_period = 1,
        ):
        """ Create an HTTP server on port http_port that displays the metrics of
        the cryostat as a simple JSON. The monitor server will query the HAL
        server every min_update_period seconds for the temperatures/heater
        values/state
        """
        self.logger = FridgeLogger(log_path="logs", debug=True, logger_name="Monitor").logger
        self.metrics_server = MetricServer(ip_address="0.0.0.0", port=http_port)
        self.hal_client = HALClient(ip = hal_ip, port = hal_port)
        self.statemachine_client = StateMachineClient(ip = statemachine_ip, port = statemachine_port)
        self.min_update_period = min_update_period # seconds
        self.logger.info(f"MonitorServer started on port {http_port}")
        self.run()

    def update(self):
        # Get temperatures from HAL
        temperatures = self.hal_client.get_temperatures()
        self.metrics_server.update_metric_values(metric_name = 'temperatures',
                                                 new_values_dict = temperatures)
        self.logger.debug(f'Updated temperatures: {list(temperatures.keys())}')

        # Get heater values from HAL
        heater_values = self.hal_client.get_heater_values()
        self.metrics_server.update_metric_values(metric_name = 'heaters',
                                                 new_values_dict = heater_values)
        self.logger.debug(f'Updated heaters: {list(heater_values.keys())}')

        # Get heater max values from HAL
        heater_max_values = self.hal_client.get_heater_max_values()
        self.metrics_server.update_metric_values(metric_name = 'heater_max_values',
                                                 new_values_dict = heater_max_values)

        # Get state from StateMachine
        try:
            state_response = self.statemachine_client.get_state()
            if isinstance(state_response, dict) and 'state' in state_response:
                state = state_response['state']
            else:
                state = str(state_response)
            self.metrics_server.update_metric_values(metric_name = 'state',
                                                     new_values_dict = state)
            self.logger.debug(f'Updated state: {state}')
        except Exception as e:
            self.logger.warning(f'Failed to get state from StateMachine: {e}')
            self.metrics_server.update_metric_values(metric_name = 'state',
                                                     new_values_dict = 'unknown')

    def run(self):
        self.logger.info('Starting monitor server loop')
        while True:
            try:
                time_start = time.time()
                self.update()
                while time.time() - time_start < self.min_update_period:
                    time.sleep(0.01)
            except KeyboardInterrupt:
                self.logger.info('Stopping monitor server')
                break
            except Exception as e:
                self.logger.error(f'Exception in monitor server: {e}', exc_info=True)
                time.sleep(1)
