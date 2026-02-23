#%% #-*- coding: utf-8 -*-
# Adapted for FridgeOS by Daniel Sorensen, August 2025

import serial
import time
import sys


class CTC100Channel(object):
    def __init__(self, address, channelname):
        self.serial = serial.Serial(self.params['address'], baudrate=9600, timeout=1, rtscts=True)
        self.channelname = channelname
        
    def write(self, msg):        
        '''Write a message to the temperature controller and return response'''
        self.serial.write((msg+'\r\n').encode())
        msgout = self.serial.readline().strip(str.encode('\r\n'))
        return msgout
        
    def read(self):
        '''Returns a message from the temperature controller'''
        return self.serial.readline().strip('\r\n'.encode())

    def set_value(self, val):
        '''Sets the value of the output of an OUT channel such as HP or Out2'''
        ch_name = self.channelname.lower()
        msg = f'{ch_name}.value = {val:.3f}'
        self.write(msg)
        
    def get_value(self):
        msg = f'{self.channelname}.value?'
        value = float(self.write(msg))
        if value != value:  # NaN check (nan != nan is True)
            value = None
        return value
    

# #%%
# heater = CTC100Channel("/dev/serial/by-id/usb-uClinux_2.6.12-uc0_with_isp1161a1-dcd_SRS_PTC_10_0-if00", "HP")
# heater.set_value(1.3)