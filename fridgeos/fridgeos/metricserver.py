import json
import threading 
import time
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class S(BaseHTTPRequestHandler):
    """ Taken from https://gist.github.com/nitaku/10d0662536f37a087e1b """
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        sec_last_update = round(time.time() - self.server.json_dict['metadata']['last_update_time'],3)  # type: ignore[attr-defined]
        self.server.json_dict['metadata']['seconds_since_last_update'] = sec_last_update  # type: ignore[attr-defined]
        self.wfile.write(json.dumps(self.server.json_dict).encode(encoding='utf_8'))  # type: ignore[attr-defined]

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Invalid JSON')
            return
        # Call the handler on the MetricServer instance
        result = self.server.metricserver_instance.handle_post(data)
        if result is None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'POST handler returned None')
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(result.encode('utf-8'))

    def handle_post(self, data):
        # Default handler: not implemented
        return "POST handler not implemented"

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
