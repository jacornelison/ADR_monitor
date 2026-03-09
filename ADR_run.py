# -*- coding: utf-8 -*-
"""
Cells that initialize and control the ADR DAQ and Magnet
"""
import os
from HPD_Heat_Switch import Driver as hs
from ADR_Resistor_Box import Driver as rb
import asyncio as aio
from ADR_DAQ import ADR_DAQ

# Start DAQ
daq = ADR_DAQ()
daq_task = aio.create_task(daq.start())

# Init Heat Switch
hs = hs()

#%%
from ADR_Magnet_Control import ADRMagController
# Init Mag Controller
mag = ADRMagController(
    daq=daq,
    sim960=daq.adr_config.sim960,
    hs=hs,
)

#%% Reinit the FAA thermometer
# Do this to reset the FAA thermometer
# daq.adr_config.sim921.set_EXCI(3)


#%% Turn off the pulse tube

# hs.SwitchClose() # Ensure heat switch is closed?
# daq.adr_config.pt415_interface.performSetValue('turn_off')


#%% Cycle the fridge

cycle_task = aio.create_task(mag.do_mag_cycle(
        magup_time=30, # minutes
        magsoak_time=0.1,
        magdown_time=60,
        is_first_cycle=False,
        final_max_current=9,
        emf_limit_up_V=0.25,
        emf_limit_down_V=0.120,
    ))


#%% Mag Up for e.g. temp sweeps

ramp_rate = 9 / 1800 #amps / seconds
ramp_task = aio.create_task(mag.ramp_current_feedback(
        target_I_A = 5,
        ramp_rate_A_per_s = ramp_rate,
        timeout_margin = 10,
        emf_limit_up_V = 0.22,
        emf_limit_down_V = 0.12,
        ))


#%% Mag Down for e.g. temp sweeps

ramp_rate = 9 / 3600
ramp_task = aio.create_task(mag.ramp_current_feedback(
        target_I_A = 0,
        ramp_rate_A_per_s = ramp_rate,
        timeout_margin = 10,
        emf_limit_up_V = 0.22,
        emf_limit_down_V = 0.12,
        do_verbose = True,
        ))

#%% Example checks to see if something broke.

print("done?", cycle_task.done())
print("cancelled?", cycle_task.cancelled())
print("exception:", cycle_task.exception() if cycle_task.done() else None)

#%%
print("done?", ramp_task.done())
print("cancelled?", ramp_task.cancelled())
print("exception:", ramp_task.exception() if ramp_task.done() else None)

#%% Open or close heat switch

# hs.SwitchClose()
hs.SwitchOpen()