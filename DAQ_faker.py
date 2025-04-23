# Create a bunch of fake data and then make new fake data every N seconds for testing the monitor plots
# This will also help test the read/write system.

import pandas as pd
import ADRConfig as cg
import arcfile_handler as ah
import numpy as np
import time
import os
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'

def init_fake_data(filename):
    data = ah.init_new_arc(filename)
    
    for k in data.keys()[1::]:
        data[k] = np.random.normal(size=100)
    
    t = time.time()
    l = len(data[data.keys()[1]])
    data["Time"] = np.linspace(t-l,t,l)
    ah.save_or_create(filename,data)
    
    return

def ADR_read(filename):
    data = ah.init_new_arc(filename,do_save=False)
    
    data[data.keys()[0]] = np.array(time.time()).reshape((1,))
    for k in data.keys()[1::]:
        data[k] = np.random.normal(size=1)
    
    ah.save_or_create(filename,data)
    return 

if __name__ == '__main__':
    filename = 'test'
    samp_rate = 1
    init_fake_data(filename)
    
    while True:
        ADR_read(filename)
        time.sleep(samp_rate)
        
        
    