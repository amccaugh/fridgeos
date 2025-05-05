Adding USB devices to the HAL

To use the HAL, you need to add your USB devices to the hal.toml configuration file.
This requires to address the USB devices as a persistent device. 
Get the device id of your USB devices by `ls` command in the following directory for your linux machine: `cd /dev/serial/by-id/`
Place the device id in the hal.toml file in the following format:
For example (for a MicroPython board):
`setup.address = "/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_df611cf78f4e3f30-if00"`
For example (general USB device):
`setup.address = "/dev/serial/by-id/<long_device_id_name>"`

Adding calibration files to the HAL

Place any calibration files in the following directory: `./config` (This docker container's config directory)
When specifing the calibration files in the hal.toml file, use the following format: `/app/config/<filename>`
For example:
`setup.calibration_file = "/app/config/calibration_file.csv"`

Run the docker container:

`docker compose build --no-cache`

