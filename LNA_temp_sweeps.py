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
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372_Channel
import amp_control as ap
import VNA_control as vn
import LNA_sweep_config as cg


#%%
# Parameters for the user:
# Names and stuff
measdir = cg.measdir
measname = cg.measname
sample_name = cg.sample_name
figdir = cg.figdir
datadir = cg.datadir

# Thermometry Stuff
lakeshore_address = 'GPIB0::3::INSTR'
temp_channel = 10

# VNA setup
#globals
ifbw = 10e3

# Fine sweeps over multiple powers
#vna_power = np.arange(-20,15,10)#np.arange(-20,15,10)
vna_power = np.array([-30,-20,-10])
print_fit_params = False

# Temp Sweep Stuff
Tstop = 8 # Kelvin. Stop sweep after we're above this temp.


# Grab the resonator list from the wide sweeps
fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
print(f'Loading frequency fchedule from:\n {fname}\n\n')
with open(fname,'rb') as file:
   res0 = pk.load(file)
   res = res0[:]

#%% Initialize Instruments

# Initialize the Thermometry
class Model_372_v2(Model_372):
    def __init__(self, name: str, address: str, **kwargs) -> None:
        super().__init__(name, address, **kwargs)

    def scan_status(self):
        self.visa_handle.write('SCAN?')
        _x = self.visa_handle.read()
        return [int(_y) for _y in _x.split(',')]

    def scan(self, ich, autoscan):
        self.visa_handle.write(f'SCAN {ich}, {autoscan}')

ls = Model_372_v2('lakeshore_372', lakeshore_address)
if temp_channel != 'A': # Select our channel and turn off autoscan
    ls.scan(temp_channel,0)
res_temp = Model_372_Channel(ls, 'res_temp', str(temp_channel))



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

norm_dist = 0.2 # Normalized distance between channels (i.e. 0.5 is halfway between a channel)
max_dist = 20e6 # in Hz, don't make the sweeps too big either if the rez's are far apart.
print_output=False

print('\n')

ap.amps_toggle_on()

T0 = 0
tstart = 0
startflag = True
#res = res0[:]
try:
    while T0<=Tstop:
    #for dummy in [0]: # To run just once, for troubleshooting
        # Wait to sweep until change in temp exceeds this number
        # Higher resolution at lower temps.
        if T0<=0.5:
            difftemp_thresh = 0.005 # K.
        else:
            difftemp_thresh = 0.05 # K.
        
        T = res_temp.temperature()
        difftemp = np.abs(T-T0)
        # Only take data if we're above a certain threshold.
        # Continuously check, but only print that we're waiting if it's been
        # a while.
        if difftemp<=difftemp_thresh:
            if time.time()-tstart>5:
                print(f'Waiting for temp to change by {difftemp_thresh} K')
                print(f'Previous Temp: {round(T0,3)}\t|\tCurrent Temp: {round(T,3)} ')
                tstart = time.time()
            continue
        
        
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
                
                fileDataDict = {
                    'I' : I,
                    'Q' : Q,
                    'freq' : FREQ,
                    'name' : f'{sample_name}_RES{fidx}',
                    'pwr' : pwr-60,
                    'temp' : T,
                    'time' : meas_time
                    }
                
                resObj1 = scr.makeResFromData(fileDataDict, paramsFn = scr.cmplxIQ_params, fitFn = scr.cmplxIQ_fit)
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
            #     if pwridx==0 and fidx==0:
            #         est_time_left = np.median(comp_times)*((len(vna_power)-1-pwridx)*len(res)+(len(res)-1))
            #         print(f'Estimated completion time: {round(est_time_left,2)} seconds')
            # est_time_left = np.median(comp_times)*(len(vna_power)-1-pwridx)*len(res)
            # print(f'Estimated completion time: {round(est_time_left,2)} seconds')
        
            
        vn.vna_power_off()
        print(f'Total Completion time: {np.sum(comp_times):0.2f} seconds')

        startflag = False
except KeyboardInterrupt:
    # Turn off the VNA
    print('Stopping Temp measurements')
    vn.vna_power_off()
    

#%
# We may take more than one, so don't overwrite sweep data if it already exists.
count = 0
fname =  os.path.join(datadir,f'temp_sweep_data_and_fits_{sample_name}_{count}.pkl')
while os.path.exists(fname):
    print(f'{fname} already exists!')
    count+=1
    fname =  os.path.join(datadir,f'temp_sweep_data_and_fits_{sample_name}_{count}.pkl')

print(f'Saving temperature sweeps to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(resListList,file)

#%%
# After we're done with the scan/fits, make the plots.
for fidx,f in enumerate(res):
    figA = scr.plotResListData(resListList[fidx],
                               plot_types = ['IQ','LogMag', 'Phase'], #Make three plots
                               num_cols = 3, #Number of columns
                               fig_size = 5, #Size in inches of each subplot
                               color_by='temps',
                               show_colorbar = True, #Don't need a colorbar with just one trace
                               force_square = True, #If you love square plots, this is for you!
                               )#plot_fits = [False]*3) #Overlay the best fit, need to specify for each of the plot_types
    
    [sp.grid(True) for sp in figA.axes[0:-1]]
    figA.suptitle(resListList[fidx][0].name)
    figA.tight_layout()
    fname = os.path.join(figdir,f'IQvsTemp_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)
    

#%%

def plotAllResParamsVsX(reslistlist,xname,xvallabel):
    par_names = reslistlist[0][0].lmfit_labels
    
    plt.figure(figsize=(10/3,10/3))
    fig, axs = plt.subplots(3,3,sharex='all',subplot_kw=dict(xlabel=xvallabel))
    newaxs = np.reshape(axs,(-1,1))
    for axidx,ax in enumerate(newaxs):
        ax = ax[0]
        # consolidate fitparams as a function of xparam
        y_all = []
        for residx,reslist in enumerate(reslistlist):
            xvals = []
            yvals = []
            for xidx,res in enumerate(reslist):
                xvals.append(getattr(res,xname))
                yvals.append(res.lmfit_vals[axidx])
                y_all.append(res.lmfit_vals[axidx])
                
        
        ax.plot(xvals,yvals)
        ax.grid(True)
        ax.set_ylabel(par_names[axidx])
    plt.tight_layout()
    return fig

figB = plotAllResParamsVsX(resListList,'temp','Temperature [K]')
#fname = os.path.join(figdir,f'FitParmsvsTemp_res_{sample_name}.png')
#plt.savefig(fname,dpi=300)


