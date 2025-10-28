# FridgeOS

**Robust, easy-to-use control software for cryostats**

FridgeOS is a modular control system designed for cryogenic refrigeration systems. It allows or temperature sensors and heaters, along with monitoring, data logging, and state machine capabilities.

<img width="2531" height="1460" alt="image" src="https://github.com/user-attachments/assets/717eb5ce-fa33-4d19-be51-fa624c266a1c" />


## Features

- **Real-time Monitoring**: Live Grafana-based temperature and heater monitoring with standardized PostgreSQL database
- **State Machine Control**: Easy-to-configure control sequences for complex refrigeration protocols
- **Docker Support**: Always-on architecture that recovers quickly and easily in the event of a crash
- **Extensible Driver System**: Support for basic thermometer and heating systems (e.g SRS CTC100, SRS SIM921, Lakeshore, etc) and custom hardware is simple to add

## Quickstart

FridgeOS is easiest to use as an all-in-one set of Docker containers that run independently and restart automatically if anything bad happens.  You can even test out its functionality without thermometer/heater hardware using a dummy configuration:

- Clone this repository
- Install Docker (linux recommended)
- Create `fridgeos/fridgeos-docker/config/hal.toml` and  `fridgeos/fridgeos-docker/config/statemachine.toml`
    - Suggested start: Copy dummy configuration files from `fridgeos/fridgeos-docker/config-examples/dummy/`
    - Other example configurations are there as well
- Start fridgeos:

```bash
cd fridgeos-docker
docker-compose up -d
```
- Wait ~1 minute for it to build (only the first time)
- Visit http://localhost:3000/ (Grafana temperature & state plots) and http://localhost:8000/ (state and heater control)
- Logs are available at `fridgeos/fridgeos-docker/logs/`, separated out into informational, error, and debug logs for the HAL (hardware) and statemachine

## Architecture overview

<img width="2918" height="1656" alt="image" src="https://github.com/user-attachments/assets/1fe94384-1503-4c78-91cf-f584f896d60a" />



## Adding New Hardware Drivers

This tutorial shows how to add support for a new hardware device (e.g., SRS SIM923 temperature controller) to FridgeOS.

### Step 1: Create the Hardware Driver

Create a new driver file in `fridgeos/hal/drivers/`. For example, `srs_sim923.py`:

```python
import serial
import time

class SIM923:
    def __init__(self, address, slot, **kwargs):
        self.address = address
        self.slot = slot
        self.serial = serial.Serial(address, baudrate=9600, timeout=1)
        
    def get_temperature(self):
        """Read temperature from the SIM923"""
        command = f"TVAL? {self.slot}\n"
        self.serial.write(command.encode())
        response = self.serial.readline().decode().strip()
        return float(response)
        
    def close(self):
        self.serial.close()
```

### Step 2: Create the HAL Wrapper

Add a wrapper class to `fridgeos/hal/drivers/haldrivers.py`:

```python
# Add import at the top
from .srs_sim923 import SIM923

# Add wrapper class
class SIM923Thermometer:
    def __init__(self):
        self.device = None
        
    def setup(self, address, slot, **kwargs):
        self.device = SIM923(address=address, slot=slot, **kwargs)
        
    def get_temperature(self):
        if self.device is None:
            raise RuntimeError("Device not set up")
        return self.device.get_temperature()
```

### Step 3: Register the Driver

Add your driver to the `hal_classes` dictionary in `haldrivers.py`:

```python
hal_classes = {
    # ... existing drivers
    'srs-sim923': SIM923Thermometer,
}
```

### Step 4: Use in Configuration

Add the new driver to your TOML configuration:

```toml
[[thermometers]]
name = "sample_thermometer"
hardware = "srs-sim923"
setup.address = "/dev/ttyUSB0"
setup.slot = 3
```

### Step 5: Test Your Driver

Test the new driver:

```python
from fridgeos.hal import HALClient

client = HALClient()
temp = client.get_temperature("sample_thermometer")
print(f"Temperature: {temp} K")
```

## Driver Interface Requirements

### Thermometer Drivers

All thermometer wrapper classes must implement:

```python
def setup(self, **kwargs):
    """Initialize the device with configuration parameters"""
    pass
    
def get_temperature(self):
    """Return temperature reading as float"""
    pass
```

### Heater Drivers

All heater wrapper classes must implement:

```python
def setup(self, **kwargs):
    """Initialize the device with configuration parameters"""
    pass
    
def set_heater_value(self, value):
    """Set heater output value"""
    pass
    
def get_heater_value(self):
    """Get current heater output value"""
    pass
```

## Thermometer calibration & conversion

Any thermometer can use the `conversion_csv` property to convert raw sensor readings (voltage, resistance) to temperature:

```toml
[[thermometers]]
name = "1K"
hardware = "swarm_diode"
conversion_csv = "/app/fridgeos-src/fridgeos/calibration-curves/DC-2014.csv"
setup.address = "/dev/ttyUSB0"
```

The CSV file should have two columns: `temperature, raw_value`. Pre-configured curves are available in `fridgeos/fridgeos/calibration-curves/`.

## License

This project is licensed under GPLv3. See LICENSE for details.

## Authors

- Adam McCaughan (adam.mccaughan@nist.gov)
- Ryan Morgenstern (ryan.morgenstern@nist.gov)
- Krister Shalm (krister.shalm@nist.gov)
