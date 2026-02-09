# -*- coding: utf-8 -*-
"""
Created on Thu Oct 10 14:52:23 2024

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





#%%


# Parameters for the user:
# Names and stuff
measdir = cg.measdir
measname = cg.measname
sample_name = cg.sample_name
figdir = cg.figdir
datadir = cg.datadir




#%%
# VNA setup
#globals
ifbw = 10e3

# For wide sweeps to find the resonances
Nsweeps = 1
fstart_wide = 0.75e9#0.75e9 # Hz
fstop_wide = 4.0e9#2.5e9 # Hz
ifbw_wide = 50e3 # Hz
vna_power_wide = -20 # in dBm
ddf_thresh = 0.75 # Will look for peaks above this value in the double differential
closeness_thresh = 5e5 # in Hz. throw out peaks that are closer than this

# Fine sweeps over multiple powers
skip_wide_sweep = True
vna_power = np.arange(-50,-5,10)#np.arange(-50,15,10)
print_fit_params = False


#%% Run the wide sweep to find resonators
# If you already have a wide sweep. Skip this and run the next step
# with load_sweep = True


T = res_temp.temperature()
vn.init_vna_sweep(fstart_wide, fstop_wide, ifbw_wide,avg=Nsweeps)
for N in np.arange(0,Nsweeps):
    vn.start_vna_sweep(vna_power_wide)
    X,Y,R,THETA,FREQ = vn.get_VNA_data()

#tme = time.strftime("%H_%M_%S")


wide_sweep_data = {
    'X' : X,
    'Y' : Y,
    'R' : R,
    'THETA' : THETA,
    'FREQ' : FREQ,
    'ifbw' : ifbw_wide,
    'power': vna_power_wide,
    'T' : T,
    }


# fname =  os.path.join(datadir,f'VNA_wide_sweep_{sample_name}.pkl')
# print(f'Saving  sweeps to: {fname}\n\n')
# with open(fname,'wb') as file:
#     pk.dump(wide_sweep_data,file)
    
#%% Actually find the resonators

load_sweep = False
if load_sweep:
    fname =  os.path.join(datadir,f'VNA_wide_sweep_{sample_name}.pkl')
    wide_sweep_data = pk.load(open(fname,'rb'))
    R = wide_sweep_data['R']
    FREQ = wide_sweep_data['FREQ']
    #T = wide_sweep_data['T']

R_diff = np.abs(np.diff((np.diff(R))))
F_diff = FREQ[0:len(R_diff)]
ddf_thresh = 5*np.std(R_diff)+np.median(R_diff)

res = vn.find_resonators(R_diff,F_diff,ddf_thresh,closeness_thresh)
res_R = np.interp(res,FREQ,R)

#res = res0
idx = np.isin(F_diff,res)

plt.figure(1,figsize=(10,5))
plt.subplot(2,1,1)
plt.plot(FREQ/1e9,R)
plt.plot(res/1e9,res_R,'rx')
plt.grid(True)
plt.minorticks_on()
plt.grid(True, which='minor', linestyle=':', linewidth='0.5', color='gray')
plt.xlabel('Frequency [GHz]')
plt.ylabel('S21 Magnitude [dB]')

plt.subplot(2,1,2)
plt.plot(F_diff,R_diff)
plt.plot(F_diff,R_diff,'.')
plt.plot(F_diff[idx],R_diff[idx],'rx')
plt.plot(F_diff,np.ones(np.shape(F_diff))*ddf_thresh,'k--')
plt.grid(True)
plt.legend(['Data','Data-dots','Res Peaks','Threshold'])
plt.xlabel('Frequency [Hz]')
plt.ylabel('$-\partial^2 S_{21}/\partial f^2$')
#plt.yscale('log')

plt.suptitle(f'VNA Wide Sweep: {sample_name} @ {vna_power_wide} dBm input power @ {int(T*1000-np.mod(T*1000,50))} mK')
if T>1:
    plt.suptitle(f'VNA Wide Sweep: {sample_name} @ {vna_power_wide} dBm input power @ {T-np.mod(T,0.5)} K')
plt.tight_layout()
#pltname = os.path.join(figdir,f'VNA_wide_sweep_{sample_name}_pwr_{vna_power_wide}_time_{tme}.png')
pltname = os.path.join(figdir,f'VNA_wide_sweep_{sample_name}_pwr_{vna_power_wide}.png')
print(f'Saving wide sweep plot to:\n{pltname}\n\n')
#plt.savefig(pltname,dpi=300)

print(f'Found {len(res)} resonators at (GHz):\n{res/1e9}\nPlease verify that these make sense in the plots\n\n')


#%% Save wide sweep stuff if we're happy with it
fname =  os.path.join(datadir,f'VNA_wide_sweep_{sample_name}.pkl')
print(f'Saving Wide Sweep to:\n{fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(wide_sweep_data,file)

#%% Save resonator freq list once we're happy with it.
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

# Grab the resonator list from the wide sweeps if we already have them
if skip_wide_sweep:
    fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
    print(f'Loading frequency fchedule from:\n {fname}\n\n')
    with open(fname,'rb') as file:
        res = pk.load(file)

#%% Actually run the Fine sweeps

#res = [5.83225344e9]

print('Running and fitting fine sweeps')
resListList = []
max_dist = 20e6 # in Hz, don't make the sweeps too big either if the rez's are far apart.
norm_dist = 0.3 # Normalized distance between channels (i.e. 0.5 is halfway between a channel)
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
        vn.start_vna_sweep(pwr)
        I,Q,R,THETA,FREQ = vn.get_VNA_data()
        
        fileDataDict = {
            'I' : I,
            'Q' : Q,
            'freq' : FREQ,
            'name' : f'{sample_name}_RES{fidx}',
            'pwr' : pwr-60,
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
tme = time.strftime("%H_%M_%S")
fname =  os.path.join(datadir,f'fine_sweep_data_and_fits_{sample_name}.pkl')
print(f'Saving Fine sweeps to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(resListList,file)

#%%
# After we're done with the scan/fits, make the plots.
tme = time.strftime("%H_%M_%S")
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
    figA.suptitle(f"{resListList[fidx][0].name} @ {resListList[fidx][0].temp:0.3f}K")
    figA.tight_layout()
    fname = os.path.join(figdir,f'IQvsPower_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)

#%%
plt.close('all')

#%%

lims = [(-3e4,3e4),None,(0,2e5),(0,5e5),None,None,None,None,None]

def plotAllResParamsVsX(reslistlist,xname,xvallabel):
    par_names = reslistlist[0][0].lmfit_labels
    
    plt.figure(figsize=(10/3,10/3))
    fig, axs = plt.subplots(3,3,sharex='all',subplot_kw=dict(xlabel=xvallabel))
    newaxs = np.reshape(axs,(-1,1))
    for axidx,ax in enumerate(newaxs):
        xvals_all = []
        yvals_all = []
        ax = ax[0]
        # consolidate fitparams as a function of xparam
        for residx,reslist in enumerate(reslistlist):
            xvals = []
            yvals = []
            for xidx,res in enumerate(reslist):
                xvals.append(getattr(res,xname)+60)
                yvals.append(res.lmfit_vals[axidx])
            xvals_all.append(xvals)
            yvals_all.append(yvals)
            ax.plot(xvals,yvals)
        ax.grid(True)
        ax.set_ylabel(par_names[axidx])

        yvals_all = np.array(yvals_all)
        ystd = np.median(np.std(yvals_all,axis=0))
        ylwr = np.min(np.median(yvals_all,axis=0))
        yupr = np.max(np.median(yvals_all,axis=0))
        ax.set_ylim((ylwr-ystd,yupr+ystd))
        if isinstance(lims[axidx],tuple):
            ax.set_ylim(lims[axidx])
            

    plt.tight_layout()
    return fig

figB = plotAllResParamsVsX(resListList,'pwr','Input Power [dBm]')
fname = os.path.join(figdir,f'FitParmsvsPower_res_{sample_name}.png')
plt.savefig(fname,dpi=300)

#%% Ultrawide

# For wide sweeps to find the resonances


for fidx,sfreq in enumerate(np.arange(1,15,1)):

    
    Nsweeps = 1
    fstart_wide = sfreq*1e9 # Hz
    fstop_wide = (sfreq+1)*1e9 # Hz
    ifbw_wide = 10e3 # Hz
    vna_power_wide = 10 # in dBm
    ddf_thresh = 0.75 # Will look for peaks above this value in the double differential
    closeness_thresh = 1e7 # in Hz. throw out peaks that are closer than this
    
    # Fine sweeps over multiple powers
    skip_wide_sweep = False
    vna_power = np.arange(-40,15,5)
    print_fit_params = False
    
    
    #% Run the wide sweep to find resonators
    # If you already have a wide sweep. Skip this and run the next step
    # with load_sweep = True
    
    
    T = res_temp.temperature()
    vn.init_vna_sweep(fstart_wide, fstop_wide, ifbw_wide,avg=Nsweeps)
    for N in np.arange(0,Nsweeps):
        vn.start_vna_sweep(vna_power_wide)
        X,Y,R,THETA,FREQ = vn.get_VNA_data()
    
    
    wide_sweep_data = {
        'X' : X,
        'Y' : Y,
        'R' : R,
        'THETA' : THETA,
        'FREQ' : FREQ,
        'ifbw' : ifbw_wide,
        'power': vna_power_wide,
        'T' : T,
        }
    

    if fidx == 0:
        F_ultra = FREQ
        R_ultra = R
    else:
        F_ultra = np.concatenate((F_ultra,FREQ))
        R_ultra = np.concatenate((R_ultra,R))
     
#%%
        
plt.figure(1245,figsize=(30,5))
plt.plot(F_ultra,R_ultra)
plt.grid(True)


plt.tight_layout()
plt.savefig(datadir+'R1C2_ultrawide.png', dpi=300)
plt.show()

sd = {}
sd['Freq'] = F_ultra
sd['R'] = R_ultra
fname =  os.path.join(datadir,f'ultrawide_{sample_name}.pkl')
print(f'Saving Fine sweeps to: {fname}\n\n')
with open(fname,'wb') as file:
    pk.dump(sd,file)

#%%
vn.vna_power_off()
ap.amps_toggle_off()