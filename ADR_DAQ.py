# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 09:56:33 2025

@author: detector-group
"""

from ADR_ARC import ADR_ARC
from ADR_Config import ADR_Config
import copy
import pandas as pd
import time
arc = ADR_ARC()
cg = ADR_Config(init_channel_functions=True)
mc = cg.monitor_channels

class ADR_DAQ():
    def __init__(self):
        arc.init_new_arc()
        self.sample_rate = cg.daq_sample_rate
        return
    

    # Do the channel reading
    def read_channels(self):
        data = copy.deepcopy(arc.empty_data_frame)

        for chidx,chan in enumerate(mc):
            
            mclist = mc[chan]
            if mclist[2]==None:
                val = getattr(getattr(cg,mclist[0]), mclist[1])()
            else:
                val = getattr(getattr(cg,mclist[0]), mclist[1])(mclist[2])
                
            if mclist[3]==None:
                data.loc[0,chan] = val
            else:
                for subidx,subch in enumerate(mclist[3]):
                    data.loc[0,chan.replace(cg.channel_wildcard,subch)] = val[mclist[4][subidx]]


        return data

    def DAQ_run(self):
        # Just read the channels as fast as we can
        # but average over the sampling rate to reduce noise
        print("Starting DAQ")
        data = copy.deepcopy(arc.empty_data_frame)
        t0 = time.time()
        try:
            while True:
                while (time.time()-t0) < self.sample_rate:
                    data = pd.concat([data, self.read_channels()], ignore_index=True)
                
                data = data.mean(axis=0).to_frame().T
                
                arc.save_arc(data)
                t0 = time.time()
                
        except KeyboardInterrupt:
            print("Stopping DAQ")
            cg.close(init_channel_functions=True)
        return

def __del__(self):
    return

if __name__ == '__main__':
    daq = ADR_DAQ()

    daq.DAQ_run()

    
    