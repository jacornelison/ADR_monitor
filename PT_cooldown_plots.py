# -*- coding: utf-8 -*-
"""
Created on Sat Jul  5 11:22:39 2025

@author: detector-group
"""

from ADR_ARC import ADR_ARC
from ADR_Config import ADR_Config
import pandas as pd
import time
import matplotlib.pyplot as plt
import numpy as np

arc = ADR_ARC()
cg = ADR_Config(init_channel_functions=False)
mc = cg.monitor_channels

time_oldest = arc.arcname_to_time('250501_000001')
#time_oldest = arc.arcname_to_time('250603_000001')
time_newest = time.time()

cols = ['Time','Stage Temp 60K','Stage Temp 4K','Stage Temp Magnet','Cmpsr motor_current','Cmpsr pressure_low_side','Cmpsr pressure_high_side','Sim970 Pressure (Torr)']
data = arc.load_arc(t_newest=time_newest,t_oldest=time_oldest, columns=cols)


#%%

comp_on_thresh = 20 #amps

plt.figure(1,figsize=(8,12))

cmpsr_turn_on = np.where(np.diff(data['Cmpsr motor_current'])>comp_on_thresh)
Ncols = len(cols)-1


cooldown_starts = []
for onidx, onsamp in enumerate(cmpsr_turn_on[0]):
    cooldown_starts.append(data['Time'].iloc[onsamp]-30*60)

    t_range = np.where((data['Time']>=cooldown_starts[-1]) & (data['Time']<=cooldown_starts[-1]+25*60*60))
    
    if onidx == len(cmpsr_turn_on[0])-1:
        color = 'black'
    else:
        color='gray'

    for colidx,col in enumerate(cols[1::]):

        plt.subplot(Ncols,1,colidx+1)
        plt.plot((data['Time'].iloc[t_range]-cooldown_starts[-1])/3600,data[col].iloc[t_range],color=color)
        plt.grid(True)
        plt.title(col)
            
    # plt.subplot(4,1,2)
    # plt.plot((data['Time'].iloc[t_range]-cooldown_starts[-1])/3600,data['Stage Temp 60K'].iloc[t_range],color=color)
    # plt.grid(True)
    # plt.title('Stage Temp 60K')
    # plt.yscale('log')
    
    # plt.subplot(4,1,3)
    # plt.plot((data['Time'].iloc[t_range]-cooldown_starts[-1])/3600,data['Stage Temp 4K'].iloc[t_range],color=color)
    # plt.grid(True)
    # plt.title('Stage Temp 4K')
    # plt.yscale('log')
    
    # plt.subplot(4,1,4)
    # plt.plot((data['Time'].iloc[t_range]-cooldown_starts[-1])/3600,data['Stage Temp Magnet'].iloc[t_range],color=color)
    # plt.grid(True)
    # plt.title('Stage Temp Magnet')
    # plt.xlabel('Time [hours]')    
    # plt.yscale('log')


plt.tight_layout()
plt.show()