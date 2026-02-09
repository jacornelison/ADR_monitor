# -*- coding: utf-8 -*-
"""
Created on Mon Dec 16 12:25:09 2024

@author: Jcornelison
"""

import pyvisa as pv
import numpy as np
import time


VNA_address = 'GPIB0::6::INSTR'


# Initialize the VNA
rm = pv.ResourceManager()
vna = rm.open_resource(VNA_address)
vna.timeout = 10*1000
vna.write('OUTP OFF')

def vna_power_off():
    # Turns the VNA outputoff
    vna.write('OUTP OFF')

# Initialize wide VNA Sweep
def init_vna_sweep(fstart,fstop,ifbw,printtime=True,avg=1):
    
    # Max VNA points is 1e5+1. Cap at that value if we went over.
    # Further, that means we can increase the ifbw to make the measurement faster.
    npoints = (fstop-fstart)/ifbw
    if npoints>(1e5+1):
        npoints = int(1e5+1)
        ifbw = (fstop-fstart)/npoints

    # Setting up the sweep involves deleting and remaking the trace.
    # This includes the VNA display, so don't freak out when the VNA goes blank.
    # We'll wait to set the display up until afterward as the measurement
    # goes much faster if we leave display off.
    vna.write('FORM REAL,32')
    vna.write('FORM:BORD SWAP')
    vna.write('CALC:PAR:DEL:ALL')
    vna.write('CALC:PAR:EXT "ch1_s21",S21')
    vna.write('CALC:PAR:SEL "ch1_s21"')
    vna.write('CALC:FORM MLOG')
    vna.write('SENS:SWE:TYPE LIN')
    vna.write('INIT:CONT OFF')
    vna.write('TRIG:SEQ:SOUR MAN')
    vna.write('SENS:SWE:MODE SING')
    vna.write(f'SENS:FREQ:START {fstart}')
    vna.write(f'SENS:FREQ:STOP {fstop}')
    vna.write(f'SENS:BWID {ifbw}')
    vna.write(f'SENS:SWE:POIN {npoints}')
    vna.write('SENS:SWE:TIME MIN')
    
    if avg==1 or avg<=0 or avg==None:
        vna.write('SENS:AVER OFF')
    else:
        vna.write('SENS:AVER ON')
        vna.write(f'SENS:AVER:COUN {avg}')

    swptime = vna.query_ascii_values('SENS:SWE:TIME?')[0]
    if printtime:
        print(f'Sweep should take roughly {round(swptime,2)} seconds')
    if swptime > vna.timeout:
        vna.timeout = 2*swptime*1000


# Run the sweep
def start_vna_sweep(vna_power,turn_off_vna=True):
    # The sweep time is more off guideline. You'll know the sweep is done
    # when the output power turns off again.
    vna.write(f'SOUR:POW {int(vna_power)}')
    vna.write('OUTP ON')
    vna.write('INIT:IMM')
    vna.write('*WAI')
    if turn_off_vna:
        vna.write('OUTP OFF')

# Collect data from VNA buffer
def get_VNA_data(display_on=True):
    try:
        S21 = np.array(vna.query_binary_values('CALC:DATA? RDATA'))
    except pv.errors.VisaIOError as err:
        if err.abbreviation == 'VI_ERROR_TMO':
            print(f'Timed out. Waiting for {vna.timeout/1000} seconds before trying again.')
            time.sleep(vna.timeout/1000)
            S21 = np.array(vna.query_binary_values('CALC:DATA? RDATA'))
        else:
            print(f'VisaIOError: {err}')

    # Get in-phase and quadrature components
    X = S21[range(0,len(S21),2)]
    Y = S21[range(1,len(S21)+1,2)]
    
    # Convert to R/Theta
    # R is 20Log10 in order to match the numbers on the VNA display
    # I think it should be 10Log10, but I don't know why it isn't...?
    R = 20*np.log10(np.sqrt(X**2+Y**2)) 
    THETA = np.arctan2(Y,X)*180.0/np.pi
    
    FREQ = np.array(vna.query_binary_values('CALC:X?'))
    #print(t)
    
    # Display the sweep on the VNA if we want.
    if display_on:
        vna.write('DISP:WIND:STATE ON')
        vna.write('DISP:WIND:TRAC1:FEED "ch1_s21"')
        vna.write('DISP:WIND:Y:AUTO')
    
    return X,Y,R,THETA,FREQ

def init_VNA_noise(set_freq, ifbw,npoints,printtime=True):
    # This if for taking noise measurements with the VNA.
    # Not all that great...
    
    # The ifbw sets the sample rate. Larger=faster
    # Npoints determins the max T
    vna.write('FORM REAL,32')
    vna.write('CALC:PAR:DEL:ALL')
    vna.write('DISP:WIND:STATE OFF')
    vna.write('CALC:PAR:EXT "ch1_s21",S21')
    vna.write('CALC:PAR:SEL "ch1_s21"')
    vna.write('CALC:FORM MLOG')
    vna.write('SENS:SWEEP:TYPE CW')
    vna.write(f'SENS:FREQ:CW {set_freq/1e9}ghz')
    vna.write(f'SENS:BWID {ifbw}hz')
    vna.write(f'SENS:SWE:POIN {npoints}')
    vna.write('SENS:SWE:TIME MIN')
    vna.write('TRIG:SEQ:SOUR MAN')
    vna.write('SENS:SWE:MODE SING')
    vna.write('INIT:CONT OFF')

    swptime = vna.query_ascii_values('SENS:SWE:TIME?')[0]
    if printtime:
        print(f'Sweep should take roughly {round(swptime,2)} seconds')
    if swptime > vna.timeout:
        vna.timeout = 2*swptime*1000



def find_resonators(R_diff,FREQ,db_thresh=3,closeness_thresh=1e5):
    # Grab all points below a certain threshold. Most of these are probably channels.
    # If two data points are too close, we're probably sampling the same rez twice.
    # We don't need to be exact, so throw all but the largest one away.
    # this means that we'll miss colliding channels, but they suck anyway.
    
    idx = R_diff>db_thresh
    R_temp = R_diff[idx]
    f_temp = FREQ[idx]
    
    if len(f_temp)==0:
        print('No resonators found. Try again.')
        return np.array([])
    
    res_list = [f_temp[0]]
    res_amp = [R_temp[0]]
    for fidx,f in enumerate(f_temp[1::]):
        fidx = fidx+1
        if abs(f-res_list[-1])>=closeness_thresh:
            res_list.append(f)
            res_amp.append(R_temp[fidx])
        elif R_temp[fidx]>res_amp[-1]:
            res_list[-1] = f
            res_amp[-1] = R_temp[fidx]

    return np.array(res_list)
