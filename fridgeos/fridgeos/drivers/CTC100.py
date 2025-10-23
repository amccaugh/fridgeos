#%% #-*- coding: utf-8 -*-
# Adapted for FridgeOS by Daniel Sorensen, August 2025

import serial
import time
import sys


class CTC(object):
    def __init__(self, address, channelname):
        self.params = {}
        self.params["address"] = address
        self.params["baud_rate"] = 9600
        self.params["time_out"] = 1
        self.serial = serial.Serial(self.params['address'],
              baudrate=9600, timeout=1, rtscts=True)
        self.channelname = channelname
        
    def write(self, msg):        
        '''Write a message to the temperature controller and return response'''
        self.serial.write((msg+'\r\n').encode())
        msgout = self.serial.readline().strip(str.encode('\r\n'))
        return msgout
        
    def read(self):
        '''Returns a message from the temperature controller'''
        return self.serial.readline().strip('\r\n'.encode())

    def set_out(self, val):
        '''Sets the value of the output of an OUT channel such as HP or Out2'''
        ch_name = self.channelname.lower()
        msg = '%s.value = %.3f'%(ch_name, val)
        self.write(msg)
        
    def get_val(self):
        msg = '%s.value?'%self.channelname
        return float(self.write(msg))
    

# #%%
# heater = CTC("/dev/serial/by-id/usb-uClinux_2.6.12-uc0_with_isp1161a1-dcd_SRS_PTC_10_0-if00", "HP")
# heater.set_out(1.3)