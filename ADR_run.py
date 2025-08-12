# -*- coding: utf-8 -*-
"""
Created on Tue Aug 16 06:31:27 2022

@author: jianjie.zhang
"""
from datetime import datetime
import time
import threading
import numpy as np
import os
from HPD_Heat_Switch import Driver as hs
from ADR_Resistor_Box import Driver as rb
#from SRS_SIM9XX_v3 import SIM900, SIM960, SIM921, SIM922, SIM925, SIM970

from ADR_DAQ import ADR_DAQ
import asyncio as aio
daq = ADR_DAQ()

daq_task = aio.create_task(daq.start())

#%
SAFE_RAMP_RATE = 5.6e-3 #Amps/second
V_GAIN = 2 # Kepco V = 2 * SIM960

sim960 = daq.adr_config.sim960
#sim925 = daq.adr_config.sim925

#%% Reinit the FAA thermometer
# Do this whenever we go above 5K.
sim921 = daq.adr_config.sim921
sim921.set_EXCI(3)

#%% Turn off the pulse tube

#daq.adr_config.pt415_interface.performSetValue('turn_off')


#%% Initialize the power supply controller

V960 = sim960.get_OMON() # output voltage
assert np.abs(V960) < 0.004, 'SIM960 output is not zero'

#%%
# hs.performOpen()
# hs.performSetValue('Heat Switch', 'Open')
# hs.performSetValue('Heat Switch', 'Close')

# -- PID controller to manual mode and 0V
sim960.set_MOUT(0) # manual output value, in manual mode, PID disabled
sim960.set_AMAN(0) # manual mode
assert np.abs(V960) < 0.004, 'SIM960 output is not zero'

# -- Toggle Mag Cycle
rb.performSetValue('Relay Position', 'Mag Cycle')

#%% Define Mag ramp
# -- Mag ramp
async def ramp_mag(final_magnet_current=0, time_to_final_voltage=30,
             lead_resistance=1.2):
    # final_magnet_current = 9 # Amp
    # time_to_final_voltage = 30 # min
    # lead_resistance last measured in Aug 2024 by James C.

    V960 = sim960.get_OMON() # output voltage
    Imag = V960 * V_GAIN / lead_resistance
    ramp_irate = np.abs((final_magnet_current - Imag)/(time_to_final_voltage*60))
    assert  ramp_irate <= SAFE_RAMP_RATE, 'Mag-up rate exceeds limit'

    final_kepco_voltage = final_magnet_current * lead_resistance
    print('Ramp from {:.3f} V to {:.3f} V in {:.2f} minutes'.format(
        V960*V_GAIN, final_kepco_voltage, time_to_final_voltage))

    ramp_vstep_960 = 0.01 * np.sign(final_kepco_voltage/V_GAIN - V960) # V
    ramp_tstep = np.abs(ramp_vstep_960 * V_GAIN / lead_resistance / ramp_irate)
    print(ramp_tstep)
    set_points = np.arange(V960, final_kepco_voltage/V_GAIN, ramp_vstep_960)
    if np.abs(final_kepco_voltage/V_GAIN - set_points[-1]) > 0.0005:
        set_points = np.append(set_points, int(final_kepco_voltage/V_GAIN*1000)/1000) # to mV resolution

    t0 = time.time()
    for V960_set in set_points:
        sim960.set_MOUT(V960_set)
        t = time.time()
        print('t = {:.2f} min, V_Kepco = {:.3f} V'.format((t-t0)/60, V960_set*V_GAIN))
        await aio.sleep(ramp_tstep)
        V960 = sim960.get_OMON()
        print(V960_set, V960)
        assert np.abs(V960-V960_set) < 0.005, 'SIM960 output is not tracing set point'
            
    print('Ramp Mag finished')


async def do_mag_cycle(magup_time=30, magsoak_time=60, magdown_time=60, is_first_cycle=False, final_max_current=9, lead_resistance=1.2):
    # All times in args are in minutes.
    
    # Note: the mag ramp code is borrowed from previous ADR user. To-do: rewrite.
    # Have all of the current/voltage info... Why do we not use it?
    
    if is_first_cycle: # Make sure the heat switch is closed
        hs.performSetValue('Heat Switch', 'Open')
        hs.performSetValue('Heat Switch', 'Close')
    
    await ramp_mag(final_magnet_current=final_max_current,time_to_final_voltage=magup_time,lead_resistance=lead_resistance)
    
    # reset the heat switch since the magnet will have put tension on things.
    hs.performSetValue('Heat Switch', 'Open')
    hs.performSetValue('Heat Switch', 'Close')
    
    # Soak the magnet
    comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'Mag Up completed at:\n{comp_time}')
    print(f'Soaking until for {magsoak_time} minutes.')
    #print('Use mag.stop to stop or mag.pause to pause in the terminal.')
    await aio.sleep(magsoak_time*60) # make this into a breakable loop when we put it into a class.
    
    hs.performSetValue('Heat Switch', 'Open')
        
    await ramp_mag(final_magnet_current=0,time_to_final_voltage=magdown_time,lead_resistance=lead_resistance)
    
    comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'Mag Down completed at:\n{comp_time}')
    
    return



#%% Mag cycle

#aio.create_task(do_mag_cycle(is_first_cycle=True))
aio.create_task(do_mag_cycle())


#%% Mag Up

aio.create_task(ramp_mag(final_magnet_current=5, time_to_final_voltage=15))
# Just print the completion time, but soak for at least 20 minutes
comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f'Mag Up completed at:\n{comp_time}')


#%% Demag
# -- Open HS
#hs.performSetValue('Heat Switch', 'Open')
# -- Demag
aio.create_task(ramp_mag(final_magnet_current=0, time_to_final_voltage=30))

comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f'Mag Down completed at:\n{comp_time}')

#%% Close heat switch
hs.performSetValue('Heat Switch', 'Open')
hs.performSetValue('Heat Switch', 'Close')


#%% Temperature regulation
# -- Toggle Regulate

Imag = sim970.get_VOLT(2) # Mag current
Vmag = sim970.get_VOLT(1) # Back EMF
assert np.abs(Imag) < 0.015 and np.abs(Vmag) < 0.002, 'Mag I and V are not 0' # !!! May not be exact 0
rb.performSetValue('Relay Position', 'Regulate')
####
#rb.performSetValue('5 Ohm Resistor', '5 Ohm in')
#rb.performSetValue('10 Ohm Resistor','10 Ohm in')
#rb.performSetValue('25 Ohm Resistor', '25 Ohm in')
#rb.performGetValue('Relay Position')

# -- SIM925
sim925.set_MODE(1)
sim925.set_BPAS(0)
sim925.set_BUFR(0)
sim925.set_CHAN(1) # FAA

# -- SIM921
sim921.set_RANG(6) # 6: 20 kO; 7: 200 kO
sim921.set_MODE(2) # voltage
sim921.set_EXCI(3) # 100 uV
sim921.set_TCON(2) # 3s
sim921.set_ADIS(1) # Autorange display
# sim921.set_CURV(1) # !!! Select Curve

# -- SIM960
gain_P = 16
gain_I = 0.2
sim960.set_INPT(0) # internal setpoint
sim960.set_LLIM(-0.1) # Lower limit
sim960.set_ULIM(10) # Upper limit
sim960.set_GAIN(gain_P) # P
sim960.set_INTG(gain_I) # I
sim960.set_DCTL(0) # D
sim960.set_OCTL(0) # Offset off
sim960.set_RAMP(0) # Setpoint ramp off

# --- Set PID initial setpoint
def manual_to_PID(delta_setpoint=0.005):
    if np.abs(delta_setpoint) > 0.001:
        M960 = sim960.get_MMON()
        assert M960 >= 0, 'SIM960 measurement error'
        Tset = int(M960*1000)/1000 + delta_setpoint # +5 mK
        print(Tset)
        sim960.set_SETP(Tset)
    sim960.set_AMAN(1) # PID mode

manual_to_PID(delta_setpoint=0.005)


# --- Ramp to target temperature
def ramp_setpoint(T_TARGET=0.1, lead_resistance=1.2):
    Tset = sim960.get_SETP()
    # T_TARGET = 0.1
    REGULATE_RATE = 9.44/3600 # In 1 hour, ~125 mV EMF?

    setpoint_step = 0.001 # 1 mK
    ramp_tstep = setpoint_step * gain_P * V_GAIN / lead_resistance / REGULATE_RATE
    print(ramp_tstep)

    print('Ramp from {:.3f} K to {:.3f} K in {:.2f} minutes'.format(
        Tset, T_TARGET, (T_TARGET-Tset)/setpoint_step*ramp_tstep/60))
    t0 = time.time()
    while Tset < T_TARGET:
        M960 = sim960.get_MMON()
        Tset += setpoint_step
        sim960.set_SETP(Tset)
        t = time.time()
        print('t = {:.2f} min, T = {:.3f} K, Tset = {:.3f} K'.format(
            (t-t0)/60, M960, Tset))
        time.sleep(ramp_tstep)

    print('Setpoint ramp is finished')

def PID_to_manual(): # change display too
    V960 = sim960.get_OMON()
    sim960.set_MOUT(V960)
    sim960.set_AMAN(0) # Manual mode


#%% Ramp Temp

#ramp_setpoint(T_TARGET=3.15, lead_resistance=1.2)

# log data if needed
resume_logger(event)
time.sleep(3600)
pause_logger(event)


#%% ReMag

#%% Warm up
PID_to_manual()
ramp_mag(final_magnet_current=0, time_to_final_voltage=30,
             lead_resistance=1.2)

# display

# sim921 = SIM921()
# sim921.set_RANG(6) # 20 kO
# sim921.set_MODE(2) # voltage
# sim921.set_EXCI(3) # 100 uV
# sim921.set_TCON(2) # 3s
# sim921.set_ADIS(1) # Autorange display
# sim921.get_TCON()

    # sim922 = SIM922()
    # sim922.get_VOLT(0) # Channels 1-4
    # sim922.get_VOLT(1) # Channel 1

    # sim925 = SIM925()
    # sim925.get_MODE()
    # # sim925.set_MODE(0) # set mode to need
    # sim925.get_CHAN()
    # sim925.set_CHAN(1)


    # # Close all modules
    # SIM900.close()
