#%%
import json
import time
import datetime
import threading
from typing import Dict, Any, Optional
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn


class MetricServer:
    def __init__(self, ip_address: str = "localhost", port: int = 8000):
        self.app = FastAPI(title="Metrics Server", version="1.0.0")
        self.ip_address = ip_address
        self.port = port
        self.metrics_data: Dict[str, Any] = {}
        self.server_thread: Optional[threading.Thread] = None
        
        # Initialize metadata
        self.metrics_data['metadata'] = {
            'seconds_since_last_update': -1,
            'last_update_time': time.time(),
            'last_update_datetime': str(datetime.datetime.now())
        }
        
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.get("/")
        async def get_metrics():
            # Update seconds since last update
            current_time = time.time()
            last_update = self.metrics_data['metadata']['last_update_time']
            sec_last_update = round(current_time - last_update, 3)
            self.metrics_data['metadata']['seconds_since_last_update'] = sec_last_update
            
            return JSONResponse(content=self.metrics_data)
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}
    
    def update_time(self):
        """Update the last update timestamp in metadata"""
        self.metrics_data['metadata']['last_update_time'] = time.time()
        self.metrics_data['metadata']['last_update_datetime'] = str(datetime.datetime.now())
    
    def update_metric_values(self, metric_name: str, new_values_dict: Dict[str, Any]):
        """Update metrics with new values"""
        self.metrics_data[metric_name] = new_values_dict
        self.update_time()
    
    def start_server(self):
        """Start the FastAPI server in a separate thread"""
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(
                    self.app, 
                    host=self.ip_address, 
                    port=self.port, 
                    log_level="info"
                )
            )
            self.server_thread.daemon = True
            self.server_thread.start()
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get current metrics dictionary"""
        return self.metrics_data
    
    def handle_query(self, query_params: Dict[str, Any]) -> Optional[str]:
        """Handle custom query parameters (for backward compatibility)"""
        # This method can be extended for custom query handling
        return None


def example_usage():
    """Example script showing how to use the MetricServer"""
    print("=== MetricServer Example Usage ===")
    
    # Create and start the server
    server = MetricServer(ip_address="localhost", port=8001)
    
    # Add some example metrics
    server.update_metric_values('system', {
        'cpu_usage': 75.2,
        'memory_usage': 60.8,
        'disk_usage': 45.1
    })
    
    server.update_metric_values('application', {
        'active_users': 142,
        'requests_per_second': 23.5,
        'error_rate': 0.02
    })
    
    server.update_metric_values('custom_metrics', {
        'processed_items': 1250,
        'queue_size': 15,
        'last_process_time': '2024-01-15 14:30:25'
    })
    
    # Print current metrics
    print("\nCurrent metrics data:")
    print(json.dumps(server.get_metrics_dict(), indent=2))
    
    # Start the server
    print(f"\nStarting server on http://{server.ip_address}:{server.port}")
    server.start_server()
    
    print("\nServer started! You can now:")
    print(f"- View metrics: curl http://{server.ip_address}:{server.port}/")
    print(f"- Check health: curl http://{server.ip_address}:{server.port}/health")
    
    # Keep updating metrics in a loop
    try:
        import random
        counter = 0
        while True:
            time.sleep(5)  # Update every 5 seconds
            counter += 1
            
            # Update some dynamic metrics
            server.update_metric_values('system', {
                'cpu_usage': round(random.uniform(20, 90), 1),
                'memory_usage': round(random.uniform(30, 85), 1),
                'disk_usage': round(random.uniform(40, 80), 1)
            })
            
            server.update_metric_values('application', {
                'active_users': random.randint(100, 200),
                'requests_per_second': round(random.uniform(10, 50), 1),
                'error_rate': round(random.uniform(0, 0.1), 3)
            })
            
            print(f"Updated metrics (iteration {counter})")
            
    except KeyboardInterrupt:
        print("\nShutting down example...")


if __name__ == '__main__':
    example_usage()