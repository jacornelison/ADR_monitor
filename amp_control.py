# -*- coding: utf-8 -*-
"""
Created on Wed Oct  9 15:50:42 2024

@author: jcornelison
"""

import pyvisa as pv


rm = pv.ResourceManager()

LNA_cold = False
if LNA_cold:
    LNA_bias = 1.2 # volts
    LNA_gate1 = 1.7
    LNA_gate2 = 1.9
    LNA_max_bias_current = 0.03 # amps
    LNA_max_gate_current = 0.01
else:
    LNA_bias = 1.8 # volts
    LNA_gate1 = 1.65
    LNA_gate2 = 1.65
    LNA_max_bias_current = 0.06 # amps
    LNA_max_gate_current = 0.01

power_amp_bias = 15 # Volts
power_max_bias_current = 0.7 # Amps

PS1 = rm.open_resource('GPIB0::2::INSTR')
PS2 = rm.open_resource('GPIB0::1::INSTR')

def amps_toggle_on(psnum=0):
    """
    Turns amplifier power supplies on.
    Parameters
    ----------
    psnum : TYPE, optional
        PowerSupply number. 0 for both, 1 for PS1, 2 for PS2. The default is 0.

    Returns
    -------
    None.

    """
    if psnum==0:
        PS1.write('OUTP ON')
        PS2.write('OUTP ON')
    elif psnum==1:
        PS1.write('OUTP ON')
    elif psnum==2:
        PS2.write('OUTP ON')

def amps_toggle_off(psnum=0):
    """
    Turns amplifier power supplies off.
    Parameters
    ----------
    psnum : TYPE, optional
        PowerSupply number. 0 for both, 1 for PS1, 2 for PS2. The default is 0.

    Returns
    -------
    None.

    """
    if psnum==0:
        PS1.write('OUTP OFF')
        PS2.write('OUTP OFF')
    elif psnum==1:
        PS1.write('OUTP OFF')
    elif psnum==2:
        PS2.write('OUTP OFF')

amps_toggle_off()

# PS1 is bias and gate 1
print('Initializing PowerSupply2')
PS1.write('*IDN?')
print(PS1.read())
PS1.write(f'APPL P25V, {LNA_gate1}, {LNA_max_gate_current}')
PS1.write('APPL N25V, 0, 0')
PS1.write(f'APPL P6V, {LNA_bias}, {LNA_max_bias_current}')
print(f'PS1 6V Channel set to: {PS1.query("APPL? P6V")}')
print(f'PS1 +25V Channel set to: {PS1.query("APPL? P25V")}')
print(f'PS1 -25V Channel set to: {PS1.query("APPL? N25V")}')
PS1.write('INST:SEL P6V')
PS1.query('MEAS:VOLT?')

# PS2 is 2nd gate and Power AMP

print('Initializing PowerSupply2')
print(PS2.query('*IDN?'))
PS2.write(f'APPL P6V, {LNA_gate2}, {LNA_max_bias_current}')
PS2.write('APPL N25V, 0, 0')
PS2.write(f'APPL P25V, {power_amp_bias}, {power_max_bias_current}')
print(f'PS2 6V Channel set to: {PS2.query("APPL? P6V")}')
print(f'PS2 +25V Channel set to: {PS2.query("APPL? P25V")}')
print(f'PS2 -25V Channel set to: {PS2.query("APPL? N25V")}')
PS2.write('INST:SEL P25V')
PS2.query('MEAS:VOLT?')


