import requests
import json

class MonitorClient:
    def __init__(self, url, timeout = 0.1):
        self.url = url
        self.timeout = timeout

    def get_metrics(self, name = None):
        """ Get the metrics from the monitor server as a dictionary.
        Optionally, specify which subset of metrics (e.g. temperatures,
        heater_max_values) by specifying `name """
        try:
            response = requests.get(self.url, timeout = self.timeout)
            metrics_dict = json.loads(response.text)
            if name is not None:
                return metrics_dict[name], True
            else:
                return metrics_dict, True
        except requests.exceptions.ReadTimeout:
            print(f"Request to {self.url} timed out after {self.timeout} seconds")
            return None, False
        except Exception as e:
            print(f"An error occurred: {e}")
            return None, False