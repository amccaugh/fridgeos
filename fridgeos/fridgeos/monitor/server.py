#%%
import time
import random
from fridgeos.logger import FridgeLogger
from fridgeos.metricserver import MetricServer

class MonitorServer(MetricServer):
    def __init__(self,
                 http_port,
                 hal_client,
                 statemachine_client,
                 min_update_period = 1,
        ):
        """ Create an HTTP server on port http_port that displays the metrics of
        the cryostat as a simple JSON. The monitor server will query the HAL
        client every min_update_period seconds for the temperatures/heater
        values/state
        """
        self.logger = FridgeLogger(log_path="logs", debug=True, logger_name="Monitor").logger
        super().__init__(ip_address="0.0.0.0", port=http_port)
        self.hal_client = hal_client
        self.statemachine_client = statemachine_client
        self.min_update_period = min_update_period # seconds
        self.logger.info(f"MonitorServer started on port {http_port}")

    def update(self):
        # Get temperatures from HAL
        self.logger.info('1111')
        temperatures = self.hal_client.get_temperatures()
        self.logger.info('2222')
        self.update_metric_values(metric_name = 'temperatures',
                                   new_values_dict = temperatures)
        self.logger.debug(f'Updated temperatures: {list(temperatures.keys())}')

        # Get heater values from HAL
        heater_values = self.hal_client.get_heater_values()
        self.update_metric_values(metric_name = 'heaters',
                                   new_values_dict = heater_values)
        self.logger.debug(f'Updated heaters: {list(heater_values.keys())}')

        # Get heater max values from HAL
        heater_max_values = self.hal_client.get_heater_max_values()
        self.update_metric_values(metric_name = 'heater_max_values',
                                   new_values_dict = heater_max_values)

        # Get state from StateMachine
        try:
            state_response = self.statemachine_client.get_state()
            if isinstance(state_response, dict) and 'state' in state_response:
                state = state_response['state']
            else:
                state = str(state_response)
            self.update_metric_values(metric_name = 'state',
                                       new_values_dict = state)
            self.logger.debug(f'Updated state: {state}')
        except Exception as e:
            self.logger.warning(f'Failed to get state from StateMachine: {e}')
            self.update_metric_values(metric_name = 'state',
                                       new_values_dict = 'unknown')

    def run(self):
        self.logger.info('Starting monitor server loop')
        while True:
            try:
                self.logger.debug('Updating metrics')
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

if __name__ == '__main__':
    # Dummy HALClient
    class DummyHALClient:
        def get_temperatures(self):
            return {'T1': 1.23 + random.uniform(-0.1, 0.1), 'T2': 4.56 + random.uniform(-0.1, 0.1)}
        def get_heater_values(self):
            return {'H1': 0.1 + random.uniform(-0.1, 0.1), 'H2': 0.2 + random.uniform(-0.1, 0.1)}
        def get_heater_max_values(self):
            return {'H1': 1.0, 'H2': 1.0}

    # Dummy StateMachineClient
    class DummyStateMachineClient:
        def get_state(self):
            if random.random() < 0.5:
                return {'state': 'cold'}
            else:
                return {'state': 'warm'}

    hal_client = DummyHALClient()
    statemachine_client = DummyStateMachineClient()
    server = MonitorServer(
        http_port=8005,
        hal_client=hal_client,
        statemachine_client=statemachine_client,
        min_update_period=2
    )
    server.run()
    