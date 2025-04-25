# -*- coding: utf-8 -*-
"""
Created on Fri Jan  6 21:08:42 2023

@author: detector-group
"""
import pt415_interface
com_port = 'COM4'
baudrate = 115200

#pt415_status = pt415_interface.readPT415Status_Serial(port=com_port, baudrate = baudrate)
#print(pt415_interface.readPT415Status_Serial_simple())
print(len(pt415_interface.pt415_names))

if 0:
   value = pt415_interface.performSetValue('turn_on', port=com_port, baudrate=baudrate, errfile='pt415.log')
if 0:
   value = pt415_interface.performSetValue('turn_off', port=com_port, baudrate=baudrate, errfile='pt415.log')
