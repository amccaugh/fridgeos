# FridgeOS

**Robust, easy-to-use control software for cryostats**

FridgeOS is a modular control system designed for cryogenic refrigeration systems. It allows or temperature sensors and heaters, along with monitoring, data logging, and state machine capabilities.

## Features

- **Real-time Monitoring**: Live Grafana-based temperature and heater monitoring with standardized PostgreSQL database
- **State Machine Control**: Easy-to-configure control sequences for complex refrigeration protocols
- **Docker Support**: Always-on architecture that recovers quickly and easily in the event of a crash
- **Extensible Driver System**: Support for basic thermometer and heating systems (e.g SRS CTC100, SRS SIM921, Lakeshore, etc) and custom hardware is simple to add

## Quickstart

- Clone this repository
- Install Docker (linux recommended)
- Create `fridgeos/fridgeos-docker/config/hal.toml` and  `fridgeos/fridgeos-docker/config/statemachine.toml
    - Suggested start: Copy dummy configuration files from `fridgeos/fridgeos-docker/config-examples/dummy/`
    - Other example configurations are there as well
- Start fridgeos:

```bash
cd fridgeos-docker
docker-compose up -d
```
- Wait ~1 minute for it to build (only the first time)
- Visit http://localhost:3000/ (Grafana temperature & state plots) and http://localhost:8000/ (state and heater control)

### Development Installation

Navigate to the project directory and install in development mode:

```bash
pip install -e .
```

After editing the code, restart Python to load your changes.


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

## Configuration Examples

Example configurations are provided in `demo-scripts/hal-toml-config/`:

- `dummy-configuration.toml`: Testing with simulated devices
- `hpd-1k-hal-config.toml`: Real hardware configuration
- `swarm-1k-hal-configuration.toml`: Multi-channel configuration

## License

This project is licensed under GPLv3. See LICENSE for details.

## Authors

- Adam McCaughan (adam.mccaughan@nist.gov)
- Ryan Morgenstern (ryan.morgenstern@nist.gov)
- Krister Shalm (krister.shalm@nist.gov)
