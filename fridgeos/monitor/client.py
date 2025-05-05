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
        response = requests.get(self.url, timeout = self.timeout)
        metrics_dict = json.loads(response.text)
        if name is not None:
            return metrics_dict[name]
        else:
            return metrics_dict