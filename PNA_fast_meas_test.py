# -*- coding: utf-8 -*-
"""
Created on Wed Oct  9 15:51:25 2024

@author: jcornelison
"""

#%%
import pyvisa as pv
import numpy as np
rm = pv.ResourceManager()
vna = rm.open_resource("GPIB0::6::INSTR")

#%%

vna.write('FORM ASCII,0')
vna.write('CALC:PAR:DEL:ALL')
vna.write('DISP:WIND:STATE OFF')
vna.write('CALC:PAR:EXT "ch1_s21",S21')
vna.write('CALC:PAR:SEL "ch1_s21"')
vna.write('CALC:FORM MLOG')
#vna.write('SENS:SWE:TYPE LIN')
vna.write('SENS:SWEEP:TYPE CW')
vna.write('SENS:FREQ:CW 1ghz')
vna.write('SENS:BWID 60KHZ')
vna.write('SENS:SWE:POIN 1000')
vna.write('SENS:SWE:TIME MIN')
vna.write('TRIG:SEQ:SOUR MAN')
vna.write('SENS:SWE:MODE SING')
vna.write('INIT:CONT OFF')
#vna.write('TRIG:SEQ:SOUR ')

vna.write('INIT:IMM')
vna.write('*WAI')

vna.write('FORM REAL,32')
vna.write('FORM:BORD SWAP')
S21 = np.array(vna.query_binary_values('CALC:DATA? RDATA'))
X = S21[range(0,len(S21),2)]
Y = S21[range(1,len(S21)+1,2)]
R = 10*np.log10(np.sqrt(X**2+Y**2))*2
THETA = np.arctan2(Y,X)*180.0/np.pi

t = np.array(vna.query_binary_values('CALC:X?'))
#print(t)


vna.write('DISP:WIND:STATE ON')
vna.write('DISP:WIND:TRAC1:FEED "ch1_s21"')
vna.write('DISP:WIND:Y:AUTO')


import matplotlib.pyplot as plt

plt.figure(1,figsize=(10,6))
plt.plot(t,R)
plt.grid(True)
plt.show()

#%%
vna.close()