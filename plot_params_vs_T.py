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
import res_misc_funcs as miscfun
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
powers = [-25-60]

# Grab the resonator list from the wide sweeps
fname =  os.path.join(datadir,f'resonator_freq_list_{sample_name}.pkl')
print(f'Loading frequency schedule from:\n {fname}\n\n')
with open(fname,'rb') as file:
    res = pk.load(file)

#count = 0

fname =  os.path.join(datadir,f'temp_sweep_data_and_fits_{sample_name}_1.pkl')
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


# Build sweeps once
resSweeps = [scr.ResonatorSweep(reslist, index='block') for reslist in resListList]


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
    
    

#%% Fit df curves (TLS-only + TLS+MBT) + plots + aggregate params for both models

# ---- shared constants / plotting cosmetics ----
C0 = 1.764 * 8.617e-5  # eV/K (BCS gap factor); used to convert delta0 -> Tc

parmlookup = ['f0','Fd','alpha','delta0','q0','Pc']
parmlabels = ['$f_0$', 'tan$\\delta$', '$\\alpha$', '$T_c$','$Q_0$','$P_c$']
cals = [1/1e9, 1e4, 1, 1/C0,1/1e5,1e9]  # convert to display units
units = ['GHz', '$\\times 10^{-4}$', '', 'K', '$\\times 10^{5}$','pW']


# Model configuration (you can tweak these per model here)

f0_tls = {
    'f0':    {'value': 2e9, 'min': 0.1e9, 'max': 10e9},
    'Fd':    {'value': 1e-6, 'min': 1e-8, 'max': 1e-2},
}

Tc_guess = 2
f0_tls_mbt = {
    'f0':    f0_tls['f0'],
    'Fd':    f0_tls['Fd'],
    'alpha': {'value': 0.7, 'min': 0.5, 'max': 1.0},
    'delta0':{'value': Tc_guess*C0, 'min': 0.5*C0, 'max': 20*C0},
}

qi_tls = {
    'f0':    {'value': 2e9, 'min': 0.1e9, 'max': 10e9},
    'q0':    {'value': 1e4, 'min': 1e3, 'max':1e8 },
    'Fd':    {'value': 1e-6, 'min': 1e-8, 'max': 1e-2},
    'Pc':    {'value': 10**(-90/10), 'min': 10**(-120/10), 'max':10**(-60/10)},
}

qi_tls_mbt = {
    'f0':    qi_tls['f0'],
    'Fd':    qi_tls['Fd'],
    'alpha': {'value': 0.7, 'min': 0.5, 'max': 1.0},
    'delta0':{'value': Tc_guess*C0, 'min': 0.5*C0, 'max': 20*C0},
    'q0':    qi_tls['q0'],
    'Pc':    qi_tls['Pc'],
}


model_cfgs = [
    dict(
        xdata = "f0",
        key="f0_tls_only",
        pretty="$f_0$ TLS-only Fit",
        func=rfm.f0_tls,
        tfitmin=0,
        tfitmax=250,
        tplotmax=500,
        out_tag="f0_tls_only",
        init_params=f0_tls,
    ),
    dict(
        xdata = "f0",
        key="f0_tls_mbt",
        pretty="$f_0$ TLS+MBT Fit",
        func=scr.fitsSweep.f0_tlsAndMBT,
        tfitmin=0,
        tfitmax=500,
        tplotmax=500,
        out_tag="f0_tls+mbt",
        init_params=f0_tls_mbt,
    ),
    dict(
        xdata = "qi",
        key="qi_tls",
        pretty="$Q_i$ TLS-only Fit",
        func=rfm.qi_tls,
        tfitmin=0,
        tfitmax=150,
        tplotmax=500,
        out_tag="qi_tls+mbt",
        init_params=qi_tls,
    ),
    dict(
        xdata = "qi",
        key="qi_tls_mbt",
        pretty="$Q_i$ TLS+MBT Fit",
        func=scr.fitsSweep.qi_tlsAndMBT,
        tfitmin=0,
        tfitmax=500,
        tplotmax=500,
        out_tag="qi_tls+mbt",
        init_params=qi_tls_mbt,
    ),
]

resSweeps = [scr.ResonatorSweep(reslist, index='block') for reslist in resListList]

# Aggregate fit parameters for BOTH models during fitting
parmnames = ['f0', 'Fd', 'alpha', 'delta0']
#parms_by_model = {cfg["key"]: {pn: [] for pn in parmnames} for cfg in model_cfgs}
parms_by_model = {}
plt.close('all') # Helps with memory

# ---- do fits + plots ----
for fidx, sweep in enumerate(resSweeps):
#for fidx, sweep in enumerate([resSweeps[2]]): # Just one for testing
#for fidx, sweep in enumerate(resSweeps[1:3]): # A few For testing
    npwrs = len(sweep.pvec)
    cmap = plt.get_cmap('coolwarm')
    colors = cmap(np.linspace(0, 1, npwrs))
    
    
    for cfgidx,cfg in enumerate(model_cfgs):
        pname = cfg["xdata"]
        key = cfg["key"]
        tfitmin = cfg["tfitmin"]
        tfitmax = cfg["tfitmax"]
        tplotmax = cfg["tplotmax"]
        model_func = cfg["func"]
        P0 = resSweeps[fidx][pname].iloc[0, 0]    
        cfg_parms = list(cfg['init_params'].keys())

        
        # Fit
        # For Qi, hardcode F0 if we have that fit.
        if key.find('qi')==0 and np.any([k['key'].find('f0') for k in model_cfgs]):
            fit, val = next((k, v) for k, v in sweep.lmfit_results.items() if 'f0' in k)
            cfg['init_params']['f0'] = {'value': val.params['f0'].value, 'vary': False}
            cfg['init_params']['Fd'] = {'value': val.params['Fd'].value, 'vary': False}
            
        print(cfg['init_params']['f0'])
        params = miscfun.params_from_dict(cfg["init_params"])
        sweep.lmfit_results[key] = rfm.do_lmfit_ragged(
            sweep,
            model_func,
            params,
            param_name=pname,
            min_temp=tfitmin,
            max_temp=tfitmax,
            method='least_squares',
            minimize_kws=dict(max_nfev=8000, ftol=1e-10, xtol=1e-10, gtol=1e-10),
        )

        lf.report_fit(sweep.lmfit_results[key])

        # Parameter string + aggregation
        parmstr = f"{cfg['pretty']}:\n"
        params = sweep.lmfit_results[key].params

        # # store per-sweep params (NaN if missing for this model)
        if fidx == 0:
            parms_by_model[key] = {p : [] for p in cfg_parms}
            
        for pn in cfg_parms:
            parms_by_model[key][pn].append(params[pn].value)

        # Pretty print (handles delta0 -> Tc)
        for parmidx, parm in enumerate(params.keys()):
            lookupidx = parmlookup.index(parm)
            #parmstr += f"{parmlabels[parmidx]} = {params[parm].value*cals[parmidx]:0.2f}{units[parmidx]}\n"
            parmstr += f"{parmlabels[lookupidx]} = {params[parm].value*cals[lookupidx]:0.2f}{units[lookupidx]}\n"

        # Plot
        fig = plt.figure(fidx + 100*cfgidx, figsize=(7, 5))
        plt.clf()
        fig.subplots_adjust(left=0.12, right=0.78, bottom=0.12, top=0.92, hspace=0.10)

        # Make axes in a fixed grid inside that reserved area
        ax_top = fig.add_subplot(3, 1, (1, 2))  # top spans rows 1-2
        ax_res = fig.add_subplot(3, 1, 3, sharex=ax_top)

        ax_top.set_ylabel(f'$\Delta {pname}/{pname}$')
        ax_res.set_xlabel('T [mK]')
        ax_res.set_ylabel(f'Residual/{pname}')

        # Optional: hide top x tick labels
        #ax_top.tick_params(labelbottom=False)

        #ax_top = plt.subplot2grid((3, 1), (0, 0), rowspan=2)
        ax_top.plot([], [], 'kx', label='Data (not used)')
        lines = []
        for pidx, pwr in enumerate(sweep.pvec):
            fitidx = (sweep.tvec <= tfitmax) & (sweep.tvec >= tfitmin)
            fitdata = sweep[pname][pwr].iloc[fitidx]
            ax_top.plot(
                sweep.tvec[fitidx],
                (fitdata - P0) / P0,
                '.',
                label=f'{pwr} dB',
                color=colors[pidx],
            )

            plotidx = (sweep.tvec <= tplotmax) & (sweep.tvec >= tfitmax)
            plotdata = sweep[pname][pwr].iloc[plotidx]
            ax_top.plot(
                sweep.tvec[plotidx],
                (plotdata - P0) / P0,
                'x',
                color=np.clip(colors[pidx] + 0.3, 0, 1),
            )
        
        for pidx, pwr in enumerate(sweep.pvec):
            idx = sweep.tvec <= tplotmax
            data = np.squeeze(sweep[pname][sweep.pvec[pidx]][idx])
    
            model_T = np.arange(0, tplotmax)
            model = model_func(params, model_T, sweep.pvec[pidx])
            
            
            if pidx == 0:
                lab = 'tan$\\delta$ Best Fit'
                line = ax_top.plot(model_T, (model - P0) / P0, label=lab, lw=1)
                lines.append(line[0])
            else:
                lab = '_nolegend_'  
                ax_top.plot(model_T, (model - P0) / P0, label=lab, color=lines[0].get_color(), lw=1)
            
            # Compare a couple dummy Fd values (only if Fd exists)
            if 'Fd' in params:
                for fdidx,fd_val in enumerate((1e-3, 1e-4)):
     
                    dummyparm = params.copy()
                    dummyparm['Fd'].value = fd_val
                    model2 = model_func(dummyparm, model_T, sweep.pvec[pidx])
                    
                    if pidx==0:
                        lab = f'tan$\\delta$={fd_val:0.0e}'    
                        line = ax_top.plot(model_T, (model2 - P0) / P0, label=lab, lw=1)
                        lines.append(line[0])
                    else:
                        lab = '_nolegend_'  
                        ax_top.plot(model_T, (model2 - P0) / P0, label=lab,color=lines[fdidx+1].get_color(), lw=1)
    
            ax_top.grid(True)
            #ax_top.legend(loc='center right', fontsize='small',bbox_to_anchor=(1.35, 0.5))
            ax_top.text(
                0.05, 0.95, parmstr,
                horizontalalignment='left',
                verticalalignment='top',
                transform=ax_top.transAxes
            )
            handles, labels = ax_top.get_legend_handles_labels()
            leg = ax_top.legend(
                handles, labels,
                loc='center left',
                bbox_to_anchor=(1.02, 0.5),   # just outside the axes
                borderaxespad=0.0,
                fontsize='small',
            )
    
            
            # Residual panel
            ax_res.set_xlim(ax_top.get_xlim())
            model_full = model_func(params, sweep.tvec, sweep.pvec[pidx])[idx]
            ax_res.plot(sweep.tvec[idx], (data - model_full) / P0,color=colors[pidx])
        

        
        ax_res.grid(True)
        
        plt.suptitle(f'{sample_name} Res_{fidx} ({cfg["pretty"]})')
        plt.tight_layout()
        fname = os.path.join(figdir, f'{pname}_vs_T_fits_{cfg["out_tag"]}_res_{fidx}_{sample_name}.png')
        plt.savefig(fname, dpi=300)


#%% Plot histograms for BOTH models (uses parms_by_model from the previous cell)

parmlookup = ['f0','Fd','alpha','delta0','q0','Pc']
parmlabels = ['$f_0$', 'tan$\\delta$', '$\\alpha$', '$T_c$','$Q_0$','$P_c$']
cals = [1/1e9, 1e4, 1, 1/C0,1/1e5,1e9]  # convert to display units
units = ['GHz', '$\\times 10^{-4}$', '', 'K', '$\\times 10^{5}$','pW']
lims = [(0.5, 4), (1, 10), (0, 1.1), (0.5, 3),(0,1e6),(0,1e9)]         # also used as cuts
Nbins = 20
plt.close('all') # Helps with memory


for cfg in model_cfgs:
    key = cfg["key"]
    tag = cfg["out_tag"]
    cfg_parms = list(cfg['init_params'].keys())
    # Compute cuts consistently across params (after scaling)
    cut_array = np.ones(len(resSweeps), dtype=bool)
    parms_all_data = []

    
    for parmidx, pn in enumerate(cfg_parms):
        raw = np.array(parms_by_model[key][pn], dtype=float)
        scaled = raw * cals[parmidx]
        parms_all_data.append(scaled)
        lookupidx = parmlookup.index(pn)
        
        # cut if outside limits OR NaN
        #bad = (~np.isfinite(scaled)) | (scaled <= lims[parmidx][0]) | (scaled >= lims[parmidx][1])
        bad = (scaled <= lims[lookupidx][0]) | (scaled >= lims[lookupidx][1])
        cut_array[bad] = False

    parms_all_data = np.array(parms_all_data)
    
    
    # Plot hists
    for parmidx, pn in enumerate(cfg_parms):
        lookupidx = parmlookup.index(pn)
        V = parms_all_data[parmidx][cut_array]

        plt.figure(f"{tag}_{parmidx}", figsize=(4, 4))
        plt.clf()

        step = float(np.diff(lims[lookupidx])) / Nbins
        bins = np.arange(lims[lookupidx][0], lims[lookupidx][1] + step, step)
        plt.hist(V, bins=bins)
        plt.grid(True)
        plt.xlabel(parmlabels[lookupidx] + f' [{units[parmidx]}]')

        M = np.nanmedian(V)
        S = np.nanstd(V)
        N = len(V)

        plt.suptitle(
            f'{sample_name} {pn} ({tag})\n'
            f'Md={M:0.2f} | $\\sigma$={S:0.2f}{units[lookupidx]} | $N_{{samp}}$={N}'
        )
        plt.tight_layout()

        fname = os.path.join(figdir, f'F_vs_T_overall_hist_parm_{pn}_{tag}_{sample_name}.png')
        plt.show()
        #plt.savefig(fname, dpi=300)

#%%






