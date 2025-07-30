# FridgeOS

**Simple, easy-to-use control software for cryostats**

FridgeOS is a modular control system designed for cryogenic refrigeration systems. It provides a hardware abstraction layer (HAL) for temperature sensors and heaters, along with monitoring, data logging, and state machine capabilities.

## Features

- **Hardware Abstraction Layer (HAL)**: Unified interface for temperature sensors and heaters
- **Modular Architecture**: Separate servers for hardware control, monitoring, and state management
- **Real-time Monitoring**: Live temperature and heater monitoring with database logging
- **State Machine Control**: Automated control sequences for complex refrigeration protocols
- **Docker Support**: Containerized deployment with Grafana dashboards
- **Extensible Driver System**: Support for various hardware devices

## Architecture

FridgeOS consists of several independent components:

- **HAL Server** (`fridgeos.hal`): Hardware abstraction and device control
- **Monitor Server** (`fridgeos.monitor`): Data logging and real-time monitoring
- **State Machine Server** (`fridgeos.statemachine`): Automated control sequences
- **Scraper Service** (`fridgeos.scraper`): Database data collection

## Installation

### Development Installation

Navigate to the project directory and install in development mode:

```bash
pip install -e .
```

After editing the code, restart Python to load your changes.

### Docker Installation

Use the provided Docker configuration for production deployment:

```bash
cd fridgeos-docker
docker-compose up -d
```

## Quick Start

### 1. Configure Hardware

Create a TOML configuration file defining your hardware:

```toml
[[thermometers]]
name = "mixing_chamber"
hardware = "srs-sim921"
setup.address = "/dev/ttyUSB0"
setup.slot = 1

[[heaters]]
name = "mixing_chamber_heater"
hardware = "korad-kd3005p"
max_value = 25.0
setup.address = "/dev/ttyUSB1"
```

### 2. Start the HAL Server

```python
from fridgeos.hal import HALServer

server = HALServer(config_file="your-config.toml")
server.start()
```

### 3. Connect a Client

```python
from fridgeos.hal import HALClient

client = HALClient()
temp = client.get_temperature("mixing_chamber")
client.set_heater_value("mixing_chamber_heater", 10.0)
```

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your driver following the tutorial above
4. Test thoroughly with real hardware
5. Submit a pull request

## License

This project is licensed under GPLv3. See LICENSE for details.

## Authors

- Adam McCaughan (adam.mccaughan@nist.gov)
- Ryan Morgenstern (ryan.morgenstern@nist.gov)
- Krister Shalm (krister.shalm@nist.gov)