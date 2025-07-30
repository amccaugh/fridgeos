#!/usr/bin/env python3
"""
Demo script that sets up both HALServer and StateMachineServer using dummy hardware configs.

This script demonstrates how to:
1. Start a HAL server with dummy hardware configuration
2. Create a HAL client to connect to the server  
3. Initialize and start a StateMachine server that uses the HAL client
4. Run both servers concurrently

The script uses the dummy configuration files which simulate hardware without 
requiring actual physical devices.
"""

import threading
import time
import signal
import sys
import uvicorn
from fridgeos.hal import HALServer, HALClient
from fridgeos.statemachine import StateMachineServer

def main():
    print("Starting HAL and StateMachine demo...")
    
    # Configuration paths
    hal_config_path = "../configs/dummy/dummy-hal.toml"
    statemachine_config_path = "../configs/dummy/dummy-statemachine.toml"
    log_path = "./logs/"
    
    # Server configuration
    hal_port = 8001
    statemachine_port = 8000
    
    # Initialize HAL Server
    print(f"Initializing HAL Server on port {hal_port}...")
    hal_server = HALServer(
        port=hal_port,
        hardware_toml_path=hal_config_path,
        log_path=log_path,
        debug=True
    )
    
    # Start HAL Server in a separate thread
    print("Starting HAL Server...")
    def run_hal_server():
        uvicorn.run(hal_server.app, host="0.0.0.0", port=hal_port, log_level="error")
    
    hal_thread = threading.Thread(target=run_hal_server, daemon=True)
    hal_thread.start()
    
    # Give HAL server time to start up
    time.sleep(2)
    
    # Create HAL Client to connect to the server
    print(f"Creating HAL Client to connect to localhost:{hal_port}...")
    hal_client = HALClient(ip='127.0.0.1', port=hal_port)
    
    # Test HAL client connection
    try:
        server_info = hal_client.get_server_info()
        print(f"HAL Server connection successful! Found {len(server_info.get('temperatures', {}))} thermometers and {len(server_info.get('heater_values', {}))} heaters")
    except Exception as e:
        print(f"Failed to connect to HAL Server: {e}")
        return
    
    # Initialize StateMachine Server
    print(f"Initializing StateMachine Server on port {statemachine_port}...")
    statemachine_server = StateMachineServer(
        config_path=statemachine_config_path,
        log_path=log_path,
        hal_client=hal_client,
        debug=True,
        http_port=statemachine_port
    )
    
    # Start StateMachine Server HTTP API in a separate thread
    print("Starting StateMachine Server HTTP API...")
    def run_statemachine_server():
        uvicorn.run(statemachine_server.app, host="0.0.0.0", port=statemachine_port, log_level="error")
    
    sm_thread = threading.Thread(target=run_statemachine_server, daemon=True)
    sm_thread.start()
    
    # Note: State machine loop starts automatically when StateMachineServer is initialized
    
    # Give StateMachine server time to start up
    time.sleep(2)
    
    print("\n" + "="*60)
    print("DEMO SETUP COMPLETE!")
    print("="*60)
    print(f"HAL Server running on: http://localhost:{hal_port}")
    print(f"StateMachine Server running on: http://localhost:{statemachine_port}")
    print("\nAvailable endpoints:")
    print(f"  HAL Server info: http://localhost:{hal_port}/")
    print(f"  Temperatures: http://localhost:{hal_port}/temperatures")
    print(f"  Heater values: http://localhost:{hal_port}/heater_values")
    print(f"  StateMachine status: http://localhost:{statemachine_port}/status")
    print(f"  StateMachine state: http://localhost:{statemachine_port}/state")
    print("\nPress Ctrl+C to stop both servers...")
    print("="*60)
    
    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")

if __name__ == "__main__":
    main()