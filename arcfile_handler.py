
import pandas as pd
import ADRConfig as cg
import os
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'

# Save data to an archive file
# Automatically create new files after a certain limit is reached?
def save_or_create(filename,data):
    #
    
    data.to_hdf(os.path.join(cg.datadir,filename),key="data",mode="a",format="table",append=True)
    
    return 

def init_new_arc(filename, do_save=True):
    data = {"Time":[]}
    for k in cg.monitor_channels.keys():
        data[k] = []
    
    data = pd.DataFrame(data)
    if do_save:
        data.to_hdf(os.path.join(cg.datadir,filename),key="data",mode="w",format="table")
    
    return data

def return_empty_dataframe(data):
    return pd.DataFrame(columns=data.columns)

def load_arc(t1,t2):
    
    return

def check_file_size():
    
    return