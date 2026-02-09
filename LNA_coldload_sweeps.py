# -*- coding: utf-8 -*-
"""
Created on Wed Oct 30 10:44:29 2024

@author: jcornelison
"""
#%% Imports
import numpy as np
import time
import os
import matplotlib.pyplot as plt
import scraps as scr
import pickle as pk
import LNA_sweep_config as cg
import res_misc_funcs as rmf

temp_channel = 8 # 8 for DR / 10 for ADR

if cg.cryostat_name == "DR":
    import VNA_control.RS_ZNB as vn
    res_temp = rmf.DR_temp_read(temp_channel)
    
else:
    import amp_control as ap
    import VNA_control.KS_PNA as vn
    ap.amps_toggle_on()


#% Init Cold load thermometer
from drivers import model_218
ls218_address = 'COM13'
ls218 = model_218.Model218(baud_rate=9600, com_port=ls218_address)
cl_channel = 2

def get_tcl():
    tmp = ls218.get_sensor_reading(cl_channel)
    if tmp is None:
	    tmp = 0.000
    return tmp

#% Init cold load heater
import qcodes.instrument_drivers.Keysight.keysight_E36311a as ks
ksdc2 = ks.E36313A('DC3', 'USB0::0x2A8D::0x1002::MY59001527::INSTR')



#%%
# Parameters for the user:
# Names and stuff
measdir = cg.measdir
measname = cg.measname
sample_name = cg.sample_name
figdir = cg.figdir
datadir = cg.datadir

# VNA setup
#globals
ifbw = 10e3

# Fine sweeps over multiple powers
#vna_power = np.arange(-20,15,10)#np.arange(-20,15,10)
vna_power = np.array([-35,-30,-25])
print_fit_params = False


# Grab the resonator list from the wide sweeps
fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
print(f'Loading frequency schedule from:\n {fname}\n\n')
with open(fname,'rb') as file:
   res0 = pk.load(file)
   res = res0[:]



#%% 
# Do the fine sweeps now. (loop over powers if we want)
# Just so we don't have to think about how wide we make the sweeps
# I just tell it to sweep over some distance between channels.
# Long enough to get good data. Short enough to not see the neighboring resonators.
# This obviously breaks for colliding channels, but it's their fault, really.
#
# We'll also track the resonator peaks as they move so they don't fall off the sweep range.

# Option to follow the resonator as it shifts
follow_res = True
follow_power = np.max(vna_power)

print('Running and fitting fine sweeps')
resListList = []

norm_dist = 0.3 # Normalized distance between channels (i.e. 0.5 is halfway between a channel)
max_dist = 20e6 # in Hz, don't make the sweeps too big either if the rez's are far apart.
print_output=False

print('\n')

#%
# Zhaodi / Cyndia had roughly 2V increments and waited 1 hour between each setting.
wait_ratio = 2 / (3600*2) # Let's go slower, but only go half of full temp

Vstart = 0
Vend = 10 # Max voltage I've seen in code / logs is 21 V
wait_interval = 300 # in seconds
Vincrement = wait_ratio * wait_interval
Vloop = np.round(np.arange(Vstart,Vend+Vincrement,Vincrement),2)
Nsteps = len(Vloop)


#% Run cold load ramp and VNA sweeps.

startflag = True
#res = res0[:]
try:

    for ramp_idx, cl_volts in enumerate(Vloop):
    #for ramp_idx, cl_volts in enumerate([0]): # To run just once, for troubleshooting
        # Ramp to voltage and wait allotted time. before sweeping.
        
        print(f'Stepping to {cl_volts}V')
        if ramp_idx == 0:
            time.sleep(0)
        else:
            ksdc2.ch2.source_voltage(cl_volts)
            ksdc2.ch2.enable('on')
            time.sleep(wait_interval)
            

        T = res_temp.temperature()
        # Loop over resonators at a given input power.
        comp_times = []
        for pwridx,pwr in enumerate(vna_power):
            meas_time = time.time()
            for fidx,f in enumerate(res):
                tstart = time.time()
                
                # Add a new spot in the list of resonators
                if pwridx == 0 and startflag:
                    resListList.append([])
                
                # Find resonator distance. 
                if fidx==0:
                    if len(res) == 1:
                        resdist = max_dist
                    else:
                        resdist = abs(f-res[fidx+1])
                elif fidx==(len(res)-1):
                    resdist = abs(f-res[fidx-1])
                else:
                    resdist = np.min([abs(f-res[fidx+1]),abs(f-res[fidx-1])])
                    
                
                sweep_dist = resdist*norm_dist
                if sweep_dist > max_dist:
                    sweep_dist = max_dist
                
                fstart = f-sweep_dist
                fstop = f+sweep_dist        
            
                vn.init_vna_sweep(fstart, fstop, ifbw,printtime=False)
                vn.start_vna_sweep(pwr,turn_off_vna=False)
                I,Q,R,THETA,FREQ = vn.get_VNA_data(display_on=False)
                
                T = res_temp.temperature()
                if fidx == 0:
                    T0 = T
                
                Tcl = get_tcl()
                fileDataDict = {
                    'I' : I,
                    'Q' : Q,
                    'freq' : FREQ,
                    'name' : f'{sample_name}_RES{fidx}',
                    'pwr' : pwr-60,
                    'temp' : T,
                    'time' : meas_time,
                    'cold_load_temp': Tcl
                    }
                
                resObj1 = scr.makeResFromData(fileDataDict, paramsFn = scr.cmplxIQ_params, fitFn = scr.cmplxIQ_fit)
                
                # scraps doesn't save metadata naturally, so add time and cold load into its own metadata dict.
                resObj1.meta = {
                    "time": fileDataDict["time"],
                    "cold_load_temp": fileDataDict["cold_load_temp"],
                    }
                
                resListList[fidx].append(resObj1)
                
                if follow_res and pwr==follow_power:
                    res[fidx] = FREQ[np.argmin(R)]
                
                if print_output:
                    par_names  = resObj1.lmfit_labels
                    #txtstr = ''
                    vals = resObj1.lmfit_vals
                    for i, value in enumerate(resObj1.lmfit_vals):
                        print('Parameter %s'%par_names[i] + ' is %.4f'%value)
                        #txtstr += f'{par_names[i]}:{int(value)}\n'
                comp_times.append(time.time()-tstart)

            
        vn.vna_power_off()
        print(f'Cold Load Temp: {Tcl} K')
        print(f'Total Completion time: {np.sum(comp_times):0.2f} seconds')

        startflag = False
except KeyboardInterrupt:
    # Turn off the VNA
    print('Stopping Temp measurements')
    vn.vna_power_off()
    
    

# except Exception as e:
#     print(f"An unexpected error occurred: {e}")
    
#     # Turn off the VNA
#     print('Stopping Temp measurements')
#     vn.vna_power_off()
        
#%%
# We may take more than one, so don't overwrite sweep data if it already exists.
count = 0
fname =  os.path.join(datadir,f'coldload_sweep_data_and_fits_{sample_name}_{count}.pkl')
while os.path.exists(fname):
    print(f'{fname} already exists!')
    count+=1
    fname =  os.path.join(datadir,f'coldload_sweep_data_and_fits_{sample_name}_{count}.pkl')

print(f'Saving temperature sweeps to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(resListList,file)


