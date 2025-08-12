# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 09:54:22 2025

@author: detector-group


Put misc functions here for now. We can move these around later.
"""


def SIM970_pressure_curve(Vin):
    
    p_torr = 10**((Vin-5.500)/0.5) # From the micro ion plus manual.

    return p_torr    