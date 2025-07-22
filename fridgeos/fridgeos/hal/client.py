import requests
import time
import json
from typing import Dict, Any, Optional


class HALClient:
    def __init__(self, ip: str, port: int):
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to HAL server with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()  # Raises exception for HTTP error codes
            return response.json()
        
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Could not connect to HAL server at {self.base_url}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HAL server returned error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise RuntimeError("HAL server returned invalid JSON response")
    
    def get_temperatures(self) -> Dict[str, float]:
        """Get all temperature readings"""
        return self._make_request('GET', '/temperatures')
    
    def get_temperature(self, name: str) -> Dict[str, float]:
        """Get temperature reading for a specific thermometer"""
        return self._make_request('GET', f'/temperature/{name}')
    
    def set_heater_value(self, name: str, value: float) -> Dict[str, float]:
        """Set heater value for a specific heater"""
        return self._make_request('PUT', f'/heater/{name}/value', {'value': value})
    
    def get_heater_values(self) -> Dict[str, float]:
        """Get all heater values"""
        return self._make_request('GET', '/heaters/values')
    
    def get_heater_value(self, name: str) -> Dict[str, float]:
        """Get heater value for a specific heater"""
        return self._make_request('GET', f'/heater/{name}/value')
    
    def get_heater_max_values(self) -> Dict[str, float]:
        """Get maximum values for all heaters"""
        return self._make_request('GET', '/heaters/max_values')
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and all current values"""
        return self._make_request('GET', '/')
    
    def health_check(self) -> Dict[str, Any]:
        """Check if HAL server is healthy"""
        return self._make_request('GET', '/health')


def example_usage():
    """Example script showing how to use the HTTP-based HALClient"""
    print("=== HTTP HALClient Example Usage ===")
    
    try:
        # Connect to HAL server
        client = HALClient(ip='127.0.0.1', port=8000)
        
        print("1. Health check:")
        health = client.health_check()
        print(f"   Status: {health['status']}")
        
        print("\n2. Server info:")
        info = client.get_server_info()
        print(f"   Service: {info['service']}")
        print(f"   Current temperatures: {info['temperatures']}")
        print(f"   Current heater values: {info['heater_values']}")
        
        print("\n3. Get all temperatures:")
        temps = client.get_temperatures()
        print(f"   {temps}")
        
        print("\n4. Get single temperature:")
        temp = client.get_temperature('4K')
        print(f"   4K temperature: {temp}")
        
        print("\n5. Get all heater values:")
        heaters = client.get_heater_values()
        print(f"   {heaters}")
        
        print("\n6. Set heater value:")
        result = client.set_heater_value('PUMPHEATER', 5.0)
        print(f"   Set PUMPHEATER to 5.0: {result}")
        
        print("\n7. Get heater max values:")
        max_values = client.get_heater_max_values()
        print(f"   Max values: {max_values}")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    example_usage()