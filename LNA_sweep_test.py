# -*- coding: utf-8 -*-
"""
Created on Thu Oct 10 14:52:23 2024

@author: jcornelison
"""
import os
# Parameters for the user:
# Names and stuff
measdir = os.path.join('C:\\Users','detector-group','Documents','Jcornelison')
measname = '20241016_cooldown'
figdir = os.path.join(measdir,measname,'figs')
datadir = os.path.join(measdir,measname,'data')
sample_name = 'FT133'

# Thermometry Stuff
lakeshore_address = 'GPIB0::3::INSTR'
temp_channel = 10

# VNA setup
#globals
VNA_address = 'GPIB0::6::INSTR'
ifbw = 5e3

# For wide sweeps to find the resonances
fstart_wide = 1.0e9
fstop_wide = 2.5e9
vna_power_wide = -20
ddf_thresh = 2 # Will look for peaks above this value in the double differential
closeness_thresh = 1e5 # in Hz. throw out peaks that are closer than this


#%% Imports
import pyvisa as pv
import numpy as np
import time
import matplotlib.pyplot as plt
import scraps as scr
import pickle as pk
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372_Channel
class Model_372_v2(Model_372):
    def __init__(self, name: str, address: str, **kwargs) -> None:
        super().__init__(name, address, **kwargs)

    def scan_status(self):
        self.visa_handle.write('SCAN?')
        _x = self.visa_handle.read()
        return [int(_y) for _y in _x.split(',')]

    def scan(self, ich, autoscan):
        self.visa_handle.write(f'SCAN {ich}, {autoscan}')


# Initialize the Thermometry
ls = Model_372_v2('lakeshore_372', lakeshore_address)
if temp_channel != 'A': # Select our channel and turn off autoscan
    ls.scan(temp_channel,0)
res_temp = Model_372_Channel(ls, 'res_temp', str(temp_channel))


# Initialize the VNA
rm = pv.ResourceManager()
vna = rm.open_resource(VNA_address)
vna.timeout = 10*1000
vna.write('OUTP OFF')

# Initialize wide VNA Sweep
def init_vna_sweep(fstart,fstop,ifbw,printtime=True):
    
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
    
    swptime = vna.query_ascii_values('SENS:SWE:TIME?')[0]
    if printtime:
        print(f'Sweep should take roughly {round(swptime,2)} seconds')
    if swptime > vna.timeout:
        vna.timeout = 2*swptime*1000

# Run the sweep
def start_vna_sweep(vna_power):
    # The sweep time is more off guideline. You'll know the sweep is done
    # when the output power turns off again.
    vna.write(f'SOUR:POW {int(vna_power)}')
    vna.write('OUTP ON')
    vna.write('INIT:IMM')
    vna.write('*WAI')
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
    if True:
        vna.write('DISP:WIND:STATE ON')
        vna.write('DISP:WIND:TRAC1:FEED "ch1_s21"')
        vna.write('DISP:WIND:Y:AUTO')
    
    return X,Y,R,THETA,FREQ


#%% Run the wide sweep to find resonators

init_vna_sweep(fstart_wide, fstop_wide, ifbw)
start_vna_sweep(vna_power_wide)
X,Y,R,THETA,FREQ = get_VNA_data()
wide_sweep_data = {
    'X' : X,
    'Y' : Y,
    'R' : R,
    'THETA' : THETA,
    'FREQ' : FREQ,
    'ifbw' : ifbw,
    'power': vna_power_wide
    }


#%% Actually find the resonators

def find_resonators(R_diff,FREQ,db_thresh=3,closeness_thresh=1e5):
    # Grab all points below a certain threshold. Most of these are probably channels.
    # If two data points are too close, we're probably sampling the same rez twice.
    # We don't need to be exact, so throw all but the largest one away.
    # this means that we'll miss colliding channels, but they suck anyway.
    
    idx = R_diff>db_thresh
    R_temp = R_diff[idx]
    f_temp = FREQ[idx]
        
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

R_diff = np.abs(np.diff(np.diff(R)))
F_diff = FREQ[0:len(R_diff)]
res = find_resonators(R_diff,F_diff,ddf_thresh,closeness_thresh)
idx = np.isin(F_diff,res)

plt.figure(1,figsize=(10,5))
plt.subplot(2,1,1)
plt.plot(FREQ/1e9,R)
plt.grid(True)
plt.xlabel('Frequency [GHz]')
plt.ylabel('S21 Magnitude [dB]')

plt.subplot(2,1,2)
plt.plot(F_diff,R_diff)
plt.plot(F_diff,R_diff,'.')
plt.plot(F_diff[idx],R_diff[idx],'rx')
plt.plot(F_diff,np.ones(np.shape(F_diff))*ddf_thresh,'k--')
plt.grid(True)
plt.legend(['Data','Data-dots','Res Peaks','Threshold'])

plt.suptitle(f'VNA Wide Sweep: {sample_name} @ {vna_power_wide} dBm input power')

pltname = os.path.join(figdir,f'VNA_wide_sweep_{sample_name}_pwr_{vna_power_wide}.png')
print(f'Saving wide sweep plot to:\n{pltname}\n\n')
plt.savefig(pltname,dpi=300)

print(f'Found {len(res)} resonators at (GHz):\n{res/1e9}\nPlease verify that these make sense in the plots\n\n')


#%% Save wide sweep stuff if we're happy with it
fname =  os.path.join(datadir,f'VNA_wide_sweep_{sample_name}.pkl')
print(f'Saving Wide Sweep to:\n{fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(wide_sweep_data,file)

fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
print(f'Saving Frequency Schedule to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(res,file)


#%% 
# Do the fine sweeps now. (loop over powers if we want)
# Just so we don't have to think about how wide we make the sweeps
# I just tell it to sweep over some distance between channels.
# Long enough to get good data. Short enough to not see the neighboring resonators.
# This obviously breaks for colliding channels, but it's their fault, really.

print('Running and fitting fine sweeps')
resListList = []

norm_dist = 0.1 # Normalized distance between channels (i.e. 0.5 is halfway between a channel)
vna_power = np.arange(-70,-15,10)
ifbw = 5e3
print_output=False
comp_times = []
print('\n')
# Loop over resonators at a given input power.
for pwridx,pwr in enumerate(vna_power):
    for fidx,f in enumerate(res):
        # Add a new spot in the list of resonators
        tstart = time.time()
        if pwridx == 0:
            resListList.append([])
        
        # Find resonator distance. 
        if fidx==0:
            resdist = abs(f-res[fidx+1])
        elif fidx==(len(res)-1):
            resdist = abs(f-res[fidx-1])
        else:
            resdist = np.min([abs(f-res[fidx+1]),abs(f-res[fidx-1])])
    
        sweep_dist = resdist*norm_dist
        
        fstart = f-sweep_dist
        fstop = f+sweep_dist        
    
        init_vna_sweep(fstart, fstop, ifbw,printtime=False)
        start_vna_sweep(pwr)
        I,Q,R,THETA,FREQ = get_VNA_data()
        
        fileDataDict = {
            'I' : I,
            'Q' : Q,
            'freq' : FREQ,
            'name' : f'{sample_name}_RES{fidx}',
            'pwr' : pwr-40,
            'temp' : res_temp.temperature()
            }
        
        resObj1 = scr.makeResFromData(fileDataDict, paramsFn = scr.cmplxIQ_params, fitFn = scr.cmplxIQ_fit)
        resListList[fidx].append(resObj1)
        
        
        if print_output:
            par_names  = resObj1.lmfit_labels
            #txtstr = ''
            vals = resObj1.lmfit_vals
            for i, value in enumerate(resObj1.lmfit_vals):
                print('Parameter %s'%par_names[i] + ' is %.4f'%value)
                #txtstr += f'{par_names[i]}:{int(value)}\n'
        comp_times.append(time.time()-tstart)
        if pwridx==0 and fidx==0:
            est_time_left = np.median(comp_times)*((len(vna_power)-1-pwridx)*len(res)+(len(res)-1))
            print(f'Estimated completion time: {round(est_time_left,2)} seconds')
    est_time_left = np.median(comp_times)*(len(vna_power)-1-pwridx)*len(res)
    print(f'Estimated completion time: {round(est_time_left,2)} seconds')
print(f'Total Completion time: {round(np.sum(comp_times),2)} seconds')

#%%
fname =  os.path.join(datadir,f'fine_sweep_data_and_fits_{sample_name}.pkl')
print(f'Saving Fine sweeps to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(resListList,file)

#%%
# After we're done with the scan/fits, make the plots.
for fidx,f in enumerate(res):
    figA = scr.plotResListData(resListList[fidx],
                               plot_types = ['IQ','LogMag', 'Phase'], #Make three plots
                               num_cols = 3, #Number of columns
                               fig_size = 5, #Size in inches of each subplot
                               color_by='pwrs',
                               show_colorbar = True, #Don't need a colorbar with just one trace
                               force_square = True, #If you love square plots, this is for you!
                               )#plot_fits = [False]*3) #Overlay the best fit, need to specify for each of the plot_types
    
    [sp.grid(True) for sp in figA.axes[0:-1]]
    figA.suptitle(resListList[fidx][0].name)
    figA.tight_layout()
    fname = os.path.join(figdir,f'IQvsPower_res_{fidx}_{sample_name}.png')
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
        for residx,reslist in enumerate(reslistlist):
            xvals = []
            yvals = []
            for xidx,res in enumerate(reslist):
                xvals.append(getattr(res,xname))
                yvals.append(res.lmfit_vals[axidx])
            
            ax.plot(xvals,yvals)
            ax.grid(True)
            ax.set_ylabel(par_names[axidx])
    plt.tight_layout()
    return fig

figB = plotAllResParamsVsX(resListList,'pwr','Input Power [dBm]')
fname = os.path.join(figdir,f'FitParmsvsPower_res_{sample_name}.png')
plt.savefig(fname,dpi=300)


#%%
vna.write('SOUR:POW -50')
vna.write('OUTP OFF')
vna.close()