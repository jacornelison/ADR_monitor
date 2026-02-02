# -*- coding: utf-8 -*-
"""
Created on Wed Oct 30 13:16:22 2024

@author: detector-group
"""
import numpy as np
#import time
import os
import matplotlib.pyplot as plt
import scraps as scr
import pickle as pk
import warnings
import glob
import lmfit as lf
import res_fit_models as rfm
import LNA_sweep_config as cg
warnings.filterwarnings('ignore')


#%%
# Parameters for the user:
# Names and stuff
measdir = cg.measdir
measname = cg.measname
sample_name = cg.sample_name
figdir = cg.figdir
datadir = cg.datadir
powers = [-70]

# Grab the resonator list from the wide sweeps
fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
print(f'Loading frequency schedule from:\n {fname}\n\n')
with open(fname,'rb') as file:
    res = pk.load(file)

#count = 0

fname =  os.path.join(datadir,f'temp_sweep_data_and_fits_{sample_name}_*.pkl')
files = glob.glob(fname)


for fileidx,file in enumerate(files):

    print(f'Loading temperature sweeps from:\n {file}\n\n')
    resListListtemp = pk.load(open(file,'rb'))
    
    resListListtemp = resListListtemp[0:len(res)]
    
    # get rid of the last sweep, since its usually bad.
    nmin = np.min([len(r) for r in resListListtemp])-2
    for fidx,reslist in enumerate(resListListtemp):
        resListListtemp[fidx] = resListListtemp[fidx][0:nmin]
        #del resListListtemp[fidx][nmin::]
    if fileidx==0:
        resListList = resListListtemp
    else:
        for residx,r in enumerate(res):
           resListList[residx].extend(resListListtemp[residx])



# redo the fits if we need to.
#resListList = rfm.refit_QI_curves(resListList, res,tmax=0.2)

# redo freq fit by finding min freq
#resListList = rfm.refit_QI_min_freq(resListList)

# Cuts
# tmax = 2 # Kelvin
# Qicut = [1e2,1e6]
# Qccut = 1e6
# for fidx, reslist in enumerate(resListList):
#     rltemp = reslist[::]
#     rltemp = [r for r in rltemp if r.temp <= tmax]
#     #rltemp = [r for r in rltemp if r.pwr == powers[0]]
#     rltemp = [r for r in rltemp if r.lmfit_vals[2]<=Qccut]
#     rltemp = [r for r in rltemp if (r.lmfit_vals[3]>=Qicut[0] and r.lmfit_vals[3]<=Qicut[1])]
#     resListList[fidx] = rltemp[::]




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
                               max_temp = 1,
                               detrend_phase = True,
                               powers = powers,
                               )#plot_fits = [True]*3) #Overlay the best fit, need to specify for each of the plot_types
    
    [sp.grid(True) for sp in figA.axes[0:-1]]
    figA.suptitle(resListList[fidx][0].name)
    figA.tight_layout()
    fname = os.path.join(figdir,f'IQvsTemp_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)


#%%
resSweeps = []
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist[::-1],index='block'))

    sweepkey = resSweeps[fidx]['f0'].keys()[0]
    f0 = np.max(resSweeps[fidx]['f0'][sweepkey].values)
    figA = scr.plotResSweepParamsVsX(resSweeps[fidx],
                                        plot_keys=['f0','qi','qc'],
                                        xvals='temperature',
                                        force_square=True,
                                        show_colorbar=False,
                                        
                                        xmax=1000,
                                        unit_multipliers = [1e4/f0,1,1]
                                        )

    [sp.grid(True) for sp in figA.axes]
    figA.suptitle(reslist[0].name)
    figA.tight_layout()
    fname = os.path.join(figdir,f'F0_Qi_vsTemp_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)


#%% Get rid of nans

for fidx, reslist in enumerate(resListList):
    for tidx,Tlist in enumerate(reslist):
        if not Tlist.lmfit_result['default']['result'].errorbars:
            Tlist.lmfit_result['default']['result'].errorbars = True
            Tlist.lmfit_result['default']['result'].covar = np.ones((9,9))*1e9
            #print(Tlist.lmfit_result['default']['result'].covar)
        if sample_name=='FT157' and ((fidx == 0) or (fidx==1)) and ((Tlist.temp < 0.160) and (Tlist.temp > 0.100)):
            Tlist.lmfit_result['default']['result'].covar = np.ones((9,9))*1e20


#%% Fit df curves
Tfitmax = np.ones((len(res),1))*1200#
#Tfitmax = [1000,1000,1000,1000,1000,1100,1100,1200,1200,1200]
Tfitmin = np.zeros((len(res),1))
Tplotmax = 1500
# Tfitmax = [500, 500, 500, 500]#
# Tfitmin = [00, 00, 00, 00]
# Tplotmax = 700
parmlabels = ['$f_0$','tan$\\delta$','$\\alpha$','$T_c$']
resSweeps = []

#for fidx,reslist in enumerate([resListList[2]]):
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    f0_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    f0_params.add('f0',
                  value = f0_guess,)
                  #min = f0_guess*0.85,
                  #max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    f0_params.add('Fd',
                  value = 1e-6,
                  min = 1e-15,
                  max=1e-2)
    
    #The kinetic inductance fraction
    f0_params.add('alpha',
                  value = 0.7,
                  min = 0,
                  max = 1)

    #The BCS energy gap at zero temperature
    # Convert from known critical temperature
    C0 = 1.764*8.617e-5 # ev/K
    Tc = 10 # K
    lims = 10.9# K
    f0_params.add('delta0',
                  value = Tc*C0,
                  min = (Tc-lims)*C0,
                  max = (Tc+lims)*C0,)


    model = scr.fitsSweep.f0_tlsAndMBT(f0_params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)

    resSweeps[fidx].do_lmfit(['f0'],
                            [scr.fitsSweep.f0_tlsAndMBT], #The model
                            [f0_params], #The paramters
                            min_temp=Tfitmin[fidx],
                            max_temp=Tfitmax[fidx],
                            powers=powers,
                            )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['f0'])
    parmstr = "TLS+MBT Fit:\n"
    params = resSweeps[fidx].lmfit_results['f0'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"

    f0_guess = resSweeps[fidx].lmfit_results['f0'].params['f0'].value
    plt.figure(fidx+4,figsize=(5,5))
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])
    fitdata = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][fitidx])
    plt.plot(resSweeps[fidx].tvec[fitidx],(fitdata-f0_guess)/f0_guess,'.',label='Fit Data',c=[0.4,0.4,0.4])
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = scr.fitsSweep.f0_tlsAndMBT(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    mod_df = (model-f0_guess)/f0_guess
    data = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][idx])
    plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
    plt.plot(resSweeps[fidx].tvec[idx],(model-f0_guess)/f0_guess,label='Model',lw=1)
    #ymn = np.max([np.min(mod_df[np.isnan(mod_df)==0])*1.1,-1e-1])
    #ymx = np.min([np.max(mod_df[np.isnan(mod_df)==0])*1.1,1e-1])
    #plt.ylim((ymn,ymx))
    
    # model_T = np.arange(0,Tplotmax)
    # dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    # dummyparm['delta0'].value = 3*C0
    # dummyparm['alpha'].value = 0.7
    # model2 = scr.fitsSweep.f0_tlsAndMBT(dummyparm,model_T,resSweeps[fidx].pvec)
    # plt.plot(model_T,(model2-f0_guess)/f0_guess,label='a=0.7,Tc=3',lw=1)
    
    # model_T = np.arange(0,Tplotmax)
    # dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    # dummyparm['delta0'].value = 2.4*C0
    # dummyparm['alpha'].value = 0.2
    # model2 = scr.fitsSweep.f0_tlsAndMBT(dummyparm,model_T,resSweeps[fidx].pvec)
    # plt.plot(model_T,(model2-f0_guess)/f0_guess,label='a=0.2,Tc=2.4',lw=1)
    
    
    ymn = np.min(mod_df[np.isnan(mod_df)==0])
    ymx = np.max(mod_df[np.isnan(mod_df)==0])
    yd = ymx-ymn
    yav = (ymx+ymn)/2
    plt.ylim((yav-yd*1.1,yav+yd*1.1))
    
    plt.grid(True)
    plt.legend(loc='upper right')
    plt.ylabel('$\Delta f/f$')
    ax = plt.gca();
    plt.text(0.05, 0, parmstr, horizontalalignment='left', verticalalignment='bottom', transform=ax.transAxes)
    
    
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)

    

#%% Fit df curves
Tfitmax = [2600, 2600, 2600, 2600]#
Tfitmin = [200, 200, 200, 200]
Tplotmax = 4400
# Tfitmax = [500, 500, 500, 500]#
# Tfitmin = [00, 00, 00, 00]
# Tplotmax = 700
parmlabels = ['$f_0$','tan$\\delta$','$\\alpha$','$T_c$','$\\Delta$T']
resSweeps = []
#for fidx,reslist in enumerate([resListList[2]]):
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    f0_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    f0_params.add('f0',
                  value = f0_guess,)
                  #min = f0_guess*0.85,
                  #max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    f0_params.add('Fd',
                  value = 1e-6,
                  min = 1e-8,
                  max=1e-2)
    
    #The kinetic inductance fraction
    f0_params.add('alpha',
                  value = 0.005,
                  min = 0,
                  max = 1)
    


    
    #The BCS energy gap at zero temperature
    # Convert from known critical temperature
    C0 = 1.764*8.617e-5 # ev/K
    Tc = 7.32 # K
    lims = 2# K
    f0_params.add('delta0',
                  value = Tc*C0,
                  min = (Tc-lims)*C0,
                  max = (Tc+lims)*C0,)


    #The loss roughly equivalent to tan delta
    f0_params.add('DT',
                  value = 0,
                  min = -80,
                  max=2000)

    model = rfm.f0_tlsAndMBT_mod(f0_params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)

    resSweeps[fidx].do_lmfit(['f0'],
                            [rfm.f0_tlsAndMBT_mod], #The model
                            [f0_params], #The paramters
                            min_temp=Tfitmin[fidx],
                            max_temp=Tfitmax[fidx],
                            )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['f0'])
    parmstr = "TLS+MBT Fit:\n"
    params = resSweeps[fidx].lmfit_results['f0'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"

    f0_guess = resSweeps[fidx].lmfit_results['f0'].params['f0'].value
    plt.figure(fidx+4,figsize=(5,5))
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])
    fitdata = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][fitidx])
    plt.plot(resSweeps[fidx].tvec[fitidx],(fitdata-f0_guess)/f0_guess,'.',label='Fit Data',c=[0.4,0.4,0.4])
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = rfm.f0_tlsAndMBT_mod(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    data = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][idx])
    plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
    plt.plot(resSweeps[fidx].tvec[idx],(model-f0_guess)/f0_guess,label='Model',lw=1)
    
    plt.grid(True)
    plt.legend(loc='upper right')
    plt.ylabel('$\Delta f/f$')
    ax = plt.gca();
    plt.text(0.05, 0, parmstr, horizontalalignment='left', verticalalignment='bottom', transform=ax.transAxes)
    
    
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_res_MBT_mod_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)


#%% Fit df curves TLS
Tfitmax = [1200 for r in range(0,len(res))]#
Tfitmin = [0 for r in range(0,len(res))]
Tplotmax = np.max(Tfitmax)
parmlabels = ['$f_0$','tan$\\delta$','$\\alpha$','$T_c$']
plt.figure(1)
resSweeps = []
#for fidx,reslist in enumerate([resListList[2]]):
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    f0_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    f0_params.add('f0',
                  value = f0_guess,
                  min = f0_guess*0.85,
                  max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    f0_params.add('Fd',
                  value = 1e-6,
                  min = 1e-8,
                  max=1e-2)

    #The loss roughly equivalent to tan delta
    # f0_params.add('DT',
    #               value = 0,
    #               min = -2,
    #               max=2)

    resSweeps[fidx].do_lmfit(['f0'],
                            [rfm.f0_tls], #The model
                            [f0_params], #The paramters
                            min_temp=Tfitmin[fidx],
                            max_temp=Tfitmax[fidx],
                            )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['f0'])
    parmstr = "TLS-only Fit:\n"
    params = resSweeps[fidx].lmfit_results['f0'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"

    f0_guess = resSweeps[fidx].lmfit_results['f0'].params['f0'].value
    plt.figure(fidx+4,figsize=(5,5))
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])
    fitdata = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][fitidx])
    plt.plot(resSweeps[fidx].tvec[fitidx],(fitdata-f0_guess)/f0_guess,'.',label='Fit Data',c=[0.4,0.4,0.4])
    idx = resSweeps[fidx].tvec<=Tplotmax
    model_T = np.arange(0,Tplotmax)
    model = rfm.f0_tls(resSweeps[fidx].lmfit_results['f0'].params,model_T,resSweeps[fidx].pvec)
    data = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][idx])
    plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
    plt.plot(model_T,(model-f0_guess)/f0_guess,label='Model',lw=1)

    dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    dummyparm['Fd'].value = 0.001
    model2 = rfm.f0_tls(dummyparm,model_T,resSweeps[fidx].pvec)
    plt.plot(model_T,(model2-f0_guess)/f0_guess,label='tan$\delta$=1e-3',lw=1)

    dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    dummyparm['Fd'].value = 0.0001
    model2 = rfm.f0_tls(dummyparm,model_T,resSweeps[fidx].pvec)
    plt.plot(model_T,(model2-f0_guess)/f0_guess,label='tan$\delta$=1e-4',lw=1)
    
    plt.grid(True)
    plt.legend(loc='center right',fontsize='small')
    plt.ylabel('$\Delta f/f$')
    ax = plt.gca();
    plt.text(0.05, 0.95, parmstr, horizontalalignment='left', verticalalignment='top', transform=ax.transAxes)
    
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = rfm.f0_tls(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_tls_only_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)
    
    
#%% Fit df curves TLS with delta T
Tfitmax = [500, 500, 500, 500]#
Tfitmin = [0, 0, 0, 0]
Tplotmax = 700
parmlabels = ['$f_0$','tan$\\delta$','$\\Delta$T','$T_c$']
plt.figure(1)
resSweeps = []
#for fidx,reslist in enumerate([resListList[2]]):
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    f0_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    f0_params.add('f0',
                  value = f0_guess,
                  min = f0_guess*0.85,
                  max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    f0_params.add('Fd',
                  value = 1e-6,
                  min = 1e-8,
                  max=1e-2)

    #The loss roughly equivalent to tan delta
    f0_params.add('DT',
                  value = 0,
                  min = -70,
                  max=2000)

    resSweeps[fidx].do_lmfit(['f0'],
                            [rfm.f0_tls_mod], #The model
                            [f0_params], #The paramters
                            min_temp=Tfitmin[fidx],
                            max_temp=Tfitmax[fidx],
                            )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['f0'])
    parmstr = "TLS-only Fit:\n"
    params = resSweeps[fidx].lmfit_results['f0'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"
    
    
    f0_guess = resSweeps[fidx].lmfit_results['f0'].params['f0'].value
    print(f0_guess)
    plt.figure(fidx+4,figsize=(5,5))
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])
    fitdata = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][fitidx])
    plt.plot(resSweeps[fidx].tvec[fitidx],(fitdata-f0_guess)/f0_guess,'.',label='Fit Data',c=[0.4,0.4,0.4])
    idx = resSweeps[fidx].tvec<=Tplotmax
    model_T = np.arange(0,Tplotmax)
    model = rfm.f0_tls_mod(resSweeps[fidx].lmfit_results['f0'].params,model_T,resSweeps[fidx].pvec)
    data = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][idx])
    plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
    plt.plot(model_T,(model-f0_guess)/f0_guess,label='Model',lw=1)

    dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    dummyparm['Fd'].value = 0.001
    model2 = rfm.f0_tls_mod(dummyparm,model_T,resSweeps[fidx].pvec)
    m2_df = (model2-f0_guess)/f0_guess
    plt.plot(model_T,m2_df,label='tan$\delta$=1e-3',lw=1)

    
    plt.grid(True)
    plt.legend(loc='lower right')
    plt.ylabel('$\Delta f/f$')
    ax = plt.gca();
    plt.text(0.05, 0.95, parmstr, horizontalalignment='left', verticalalignment='top', transform=ax.transAxes)
    plt.ylim((np.min(m2_df[np.isnan(m2_df)==0])*1.1,np.max(m2_df[np.isnan(m2_df)==0])*1.1))

    
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = rfm.f0_tls_mod(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
   
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_tls_mod_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)
    
    
#%% Fit Q curves
Tfitmax = np.ones((len(res),1))*500#
#Tfitmax = [1000,1000,1000,1000,1000,1100,1100,1200,1200,1200]
Tfitmin = np.zeros((len(res),1))+50
Tplotmax = 1500
# Tfitmax = [500, 500, 500, 500]#
# Tfitmin = [00, 00, 00, 00]
# Tplotmax = 700
parmlabels = ['$f_0$','$Q_0$','$P_c$','tan$\\delta$','$\\alpha$','$T_c$']
resSweeps = []

for fidx,reslist in enumerate([resListList[8]]):
#for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    qi_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    qi_params.add('f0',
                  value = f0_guess,
                  min = f0_guess*0.85,
                 max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    qi_params.add('q0',
                  value = 1e6,
                  min = 1e0,
                  max=1e8)
       
    #The loss roughly equivalent to tan delta
    qi_params.add('Pc',
                  value = -110,
                  min = -300,
                  max=0)
    
    #The loss roughly equivalent to tan delta
    qi_params.add('Fd',
                  value = 1e-6,
                  min = 1e-15,
                  max=1e-2)
    
    #The kinetic inductance fraction
    qi_params.add('alpha',
                  value = 0.7,
                  min = 0,
                  max = 1)

    #The BCS energy gap at zero temperature
    # Convert from known critical temperature
    C0 = 1.764*8.617e-5 # ev/K
    Tc = 10 # K
    lims = 10.9# K
    qi_params.add('delta0',
                  value = Tc*C0,
                  min = (Tc-lims)*C0,
                  max = (Tc+lims)*C0,)


    #model = rfm.qi_tlsAndMBT(qi_params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)
        
    resSweeps[fidx].lmfit_results['qi'] = rfm.do_lmfit_ragged(resSweeps[fidx],
                                 scr.fitsSweep.qi_tlsAndMBT,
                                 qi_params,
                                 param_name='qi',
                                 min_temp=Tfitmin[fidx],
                                 max_temp=Tfitmax[fidx],
                                 )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['qi'])
    parmstr = "TLS-only Fit:\n"
    params = resSweeps[fidx].lmfit_results['qi'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"
            
    npwrs = len(resSweeps[fidx].pvec)
    cmap = plt.get_cmap('coolwarm')  # 'warm' equivalent in matplotlib
    colors = cmap(np.linspace(0, 1, npwrs))  # evenly sample the colormap
    
    plt.figure(fidx+4,figsize=(5,5))
    plt.clf()
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])

    for pidx,pwr in enumerate(resSweeps[fidx].pvec):
        fitdata = resSweeps[fidx]['qi'][pwr].iloc[fitidx]
        plt.plot(resSweeps[fidx].tvec[fitidx],fitdata,'.',label=f'{pwr} dB',color=colors[pidx])#c=[0.4,0.4,0.4])


        idx = resSweeps[fidx].tvec<=Tplotmax
        model_T = np.arange(0,Tplotmax)
        model = scr.fitsSweep.qi_tlsAndMBT(resSweeps[fidx].lmfit_results['qi'].params,model_T,pwr)
        #plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
        plt.plot(model_T,model,label='tan$\delta$ Best Fit',lw=1)
    
        dummyparm = resSweeps[fidx].lmfit_results['qi'].params.copy()
        dummyparm['Fd'].value = 0.001
        model2 = scr.fitsSweep.qi_tlsAndMBT(dummyparm,model_T,pwr)
        plt.plot(model_T,model2,label='tan$\delta$=1e-3',lw=1)
    
        dummyparm = resSweeps[fidx].lmfit_results['qi'].params.copy()
        dummyparm['Fd'].value = 0.000001
        model2 = scr.fitsSweep.qi_tlsAndMBT(dummyparm,model_T,pwr)
        plt.plot(model_T,model2,label='tan$\delta$=1e-4',lw=1)
        
        plt.grid(True)
        plt.legend(loc='center right',fontsize='small')
        plt.ylabel('$Q_i$')
        ax = plt.gca();
        plt.text(0.05, 0.95, parmstr, horizontalalignment='left', verticalalignment='top', transform=ax.transAxes)

#%%        
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = rfm.f0_tls(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_tls_only_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)
    

#%% Fit df curves TLS test new lmfit func
Tfitmax = [1200 for r in range(0,len(res))]#
Tfitmin = [0 for r in range(0,len(res))]
Tplotmax = np.max(Tfitmax)
parmlabels = ['$f_0$','tan$\\delta$','$\\alpha$','$T_c$']
plt.figure(1)
resSweeps = []
#for fidx,reslist in enumerate([resListList[0]]):
for fidx,reslist in enumerate(resListList):
    resSweeps.append(scr.ResonatorSweep(reslist,index='block'))

    f0_params = lf.Parameters()
    
    #Resonant frequency at zero temperature and zero power
    f0_guess = resSweeps[fidx]['f0'].iloc[0, 0]
    f0_params.add('f0',
                  value = f0_guess,
                  min = f0_guess*0.85,
                  max = f0_guess*1.15)
    
    #The loss roughly equivalent to tan delta
    f0_params.add('Fd',
                  value = 1e-6,
                  min = 1e-8,
                  max=1e-2)

    #The loss roughly equivalent to tan delta
    # f0_params.add('DT',
    #               value = 0,
    #               min = -2,
    #               max=2)

    # resSweeps[fidx].do_lmfit(['f0'],
    #                         [rfm.f0_tls], #The model
    #                         [f0_params], #The paramters
    #                         min_temp=Tfitmin[fidx],
    #                         max_temp=Tfitmax[fidx],
    #                         powers=[-60],
    #                         )
    
    resSweeps[fidx].lmfit_results['f0'] = rfm.do_lmfit_ragged(resSweeps[fidx],
                                 rfm.f0_tls,
                                 f0_params,
                                 param_name='f0',
                                 min_temp=Tfitmin[fidx],
                                 max_temp=Tfitmax[fidx],
                                 )
    
    lf.report_fit(resSweeps[fidx].lmfit_results['f0'])
    parmstr = "TLS-only Fit:\n"
    params = resSweeps[fidx].lmfit_results['f0'].params
    for parmidx,parm in enumerate(params.keys()):
        if parm == 'delta0':
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value/C0:0.2f}\n"
        else:
            parmstr+= f"{parmlabels[parmidx]} = {params[parm].value:0.2E}\n"
            
    npwrs = len(resSweeps[fidx].pvec)
    cmap = plt.get_cmap('coolwarm')  # 'warm' equivalent in matplotlib
    colors = cmap(np.linspace(0, 1, npwrs))  # evenly sample the colormap


    f0_guess = resSweeps[fidx].lmfit_results['f0'].params['f0'].value
    plt.figure(fidx+4,figsize=(5,5))
    plt.clf()
    plt.subplot2grid((3,1),(0,0),rowspan=2)
    fitidx = (resSweeps[fidx].tvec<=Tfitmax[fidx]) & (resSweeps[fidx].tvec>=Tfitmin[fidx])

    for pidx,pwr in enumerate(resSweeps[fidx].pvec):
        fitdata = resSweeps[fidx]['f0'][pwr].iloc[fitidx]
        plt.plot(resSweeps[fidx].tvec[fitidx],(fitdata-f0_guess)/f0_guess,'.',label=f'{pwr} dB',color=colors[pidx])#c=[0.4,0.4,0.4])

    idx = resSweeps[fidx].tvec<=Tplotmax
    model_T = np.arange(0,Tplotmax)
    model = rfm.f0_tls(resSweeps[fidx].lmfit_results['f0'].params,model_T,resSweeps[fidx].pvec)
    data = np.squeeze(resSweeps[fidx]['f0'][resSweeps[fidx].pvec[0]][idx])
    #plt.plot(resSweeps[fidx].tvec[idx],(data-f0_guess)/f0_guess,label='All Data',lw=1)
    plt.plot(model_T,(model-f0_guess)/f0_guess,label='tan$\delta$ Best Fit',lw=1)

    dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    dummyparm['Fd'].value = 0.001
    model2 = rfm.f0_tls(dummyparm,model_T,resSweeps[fidx].pvec)
    plt.plot(model_T,(model2-f0_guess)/f0_guess,label='tan$\delta$=1e-3',lw=1)

    dummyparm = resSweeps[fidx].lmfit_results['f0'].params.copy()
    dummyparm['Fd'].value = 0.0001
    model2 = rfm.f0_tls(dummyparm,model_T,resSweeps[fidx].pvec)
    plt.plot(model_T,(model2-f0_guess)/f0_guess,label='tan$\delta$=1e-4',lw=1)
    
    plt.grid(True)
    plt.legend(loc='center right',fontsize='small')
    plt.ylabel('$\Delta f/f$')
    ax = plt.gca();
    plt.text(0.05, 0.95, parmstr, horizontalalignment='left', verticalalignment='top', transform=ax.transAxes)
    
    plt.subplot2grid((3,1),(2,0))
    idx = resSweeps[fidx].tvec<=Tplotmax
    model = rfm.f0_tls(resSweeps[fidx].lmfit_results['f0'].params,resSweeps[fidx].tvec,resSweeps[fidx].pvec)[idx]
    plt.plot(resSweeps[fidx].tvec[idx],((data-model))/f0_guess)
    plt.grid(True)
    plt.xlabel('T [mK]')
    plt.ylabel('Residual/F0')
    
    plt.suptitle(f'{sample_name} Res_{fidx}')
    plt.tight_layout()
    fname = os.path.join(figdir,f'F_vs_T_fits_tls_only_res_{fidx}_{sample_name}.png')
    plt.savefig(fname,dpi=300)
    
    
    