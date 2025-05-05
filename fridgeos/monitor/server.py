import json
import threading 
import time
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import fridgeos.zmqhelper as zmqhelper
from fridgeos import HALClient

class S(BaseHTTPRequestHandler):
    """ Taken from https://gist.github.com/nitaku/10d0662536f37a087e1b """
    def do_GET(self):    
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        sec_last_update = round(time.time() - self.server.json_dict['metadata']['last_update_time'],3)
        self.server.json_dict['metadata']['seconds_since_last_update'] = sec_last_update
        self.wfile.write(json.dumps(self.server.json_dict).encode(encoding='utf_8'))

class SimpleJSONhttpserver:
    def __init__(self, ip_address="localhost", port=8000):
        self.json_dict = {}
        self.httpd = ThreadingHTTPServer((ip_address, port), S)
        self.httpd.json_dict = self.json_dict
        self.thread = threading.Thread(target=self.httpd.serve_forever, args=())
        self.thread.start()

class MetricsServer:
    def __init__(self, cryostat_name, ip_address="localhost", port=8000):
        self.server = SimpleJSONhttpserver(ip_address=ip_address, port=port)
        self.server.json_dict['metadata'] = {'cryostat_name' : cryostat_name,
                                             'seconds_since_last_update' : -1,
                                             'last_update_time' : time.time(),
                                             'last_update_datetime' : str(datetime.datetime.now())}

    def update_time(self):
        self.server.json_dict['metadata']['last_update_time'] = time.time()
        self.server.json_dict['metadata']['last_update_datetime'] = str(datetime.datetime.now())
    
    def update_metric_values(self, metric_name, new_values_dict):
        self.server.json_dict[metric_name] = new_values_dict
        self.update_time()


class MonitorServer:
    def __init__(self,
                 cryostat_name,
                 http_port,
                 hal_ip,
                 hal_port,
                 min_update_period = 1,
        ):
        """ Create an HTTP server on port http_port that displays the metrics of
        the cryostat as a simple JSON. The monitor server will query the HAL
        server every min_update_period seconds for the temperatures/heater
        values/state
        """
        self.metrics_server = MetricsServer(cryostat_name = cryostat_name, 
                                            ip_address="0.0.0.0",
                                            port=http_port)
        self.hal_client = HALClient(ip = hal_ip, port = hal_port)
        self.min_update_period = min_update_period # seconds
        self.run()

    def update(self):
        # Get temperatures from HAL
        temperatures = self.hal_client.get_temperatures()
        self.metrics_server.update_metric_values(metric_name = 'temperatures',
                                                 new_values_dict = temperatures)

        # Get heater values from HAL
        heater_values = self.hal_client.get_heater_values()
        self.metrics_server.update_metric_values(metric_name = 'heaters',
                                                 new_values_dict = heater_values)

        # Get heater max values from HAL
        heater_max_values = self.hal_client.get_heater_max_values()
        self.metrics_server.update_metric_values(metric_name = 'heater_max_values',
                                                 new_values_dict = heater_max_values)

        # FIXME implement state update

    def run(self):
        print('Starting monitor server')
        while True:
            try:
                time_start = time.time()
                self.update()
                while time.time() - time_start < self.min_update_period:
                    time.sleep(0.01)
            except KeyboardInterrupt:
                print('Stopping monitor server')
                break
            except Exception as e:
                print(e)
                time.sleep(1)
