import json
import threading 
import time
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class S(BaseHTTPRequestHandler):
    """ Taken from https://gist.github.com/nitaku/10d0662536f37a087e1b """
    def do_GET(self):
        # Parse URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Check if MetricServer instance has a handle_query method
        if hasattr(self.server, 'metricserver_instance') and hasattr(self.server.metricserver_instance, 'handle_query'):
            result = self.server.metricserver_instance.handle_query(query_params)
            if result is not None:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(result.encode('utf-8'))
                return
        
        # Default behavior: return JSON metrics
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        sec_last_update = round(time.time() - self.server.json_dict['metadata']['last_update_time'],3)  # type: ignore[attr-defined]
        self.server.json_dict['metadata']['seconds_since_last_update'] = sec_last_update  # type: ignore[attr-defined]
        self.wfile.write(json.dumps(self.server.json_dict).encode(encoding='utf_8'))  # type: ignore[attr-defined]


class SimpleJSONhttpserver:
    def __init__(self, ip_address="localhost", port=8000):
        self.json_dict = {}
        self.httpd = ThreadingHTTPServer((ip_address, port), S)
        self.httpd.json_dict = self.json_dict  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, args=())
        self.thread.start()

class MetricServer:
    def __init__(self, ip_address="localhost", port=8000):
        self.server = SimpleJSONhttpserver(ip_address=ip_address, port=port)
        self.server.httpd.metricserver_instance = self  # Pass reference to self
        self.server.json_dict['metadata'] = {'seconds_since_last_update' : -1,
                                             'last_update_time' : time.time(),
                                             'last_update_datetime' : str(datetime.datetime.now())}

    def update_time(self):
        self.server.json_dict['metadata']['last_update_time'] = time.time()
        self.server.json_dict['metadata']['last_update_datetime'] = str(datetime.datetime.now())
    
    def update_metric_values(self, metric_name, new_values_dict):
        self.server.json_dict[metric_name] = new_values_dict
        self.update_time()
