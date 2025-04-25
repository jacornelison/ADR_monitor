
import pandas as pd
from ADR_Config import ADR_Config
import os
import time
from datetime import datetime
import glob
import numpy as np
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'
cg = ADR_Config()
mc = cg.monitor_channels

class ADR_ARC():
    def __init__(self):
        self.channel_list = self.init_channel_list()
        self.arctime = None
        self.arcname = None
        self.empty_data_frame = self.create_empty_dataframe()
        return
    
    def init_channel_list(self):
        channel_list = []
        
        for chan in mc:
            subnames = mc[chan][3]
            if subnames==None:
                channel_list.append(chan)
            else:
                for subch in subnames:
                    channel_list.append(chan.replace(cg.channel_wildcard,subch))            
        
        return channel_list

    # Save data to an archive file
    # Automatically create new files after a certain limit is reached?
    def save_arc(self,data,filename=None):
        self.check_new_arc()
        
        if filename==None:
            filename = self.arcname
        
        data.to_hdf(os.path.join(cg.datadir,filename+".hdf5"),key="data",mode="a",format="table",append=True)
        
        return 
    
    def init_new_arc(self, do_save=True):
        self.arctime, self.arcname = self.create_arcname()
        
        if do_save:
            self.empty_data_frame.to_hdf(os.path.join(cg.datadir,self.arcname+".hdf5"),key="data",mode="w",format="table")
            print(f"Created new arcfile at: {os.path.join(cg.datadir,self.arcname+'.hdf5')}")
        return
      
    
    def load_arc(self,t_newest=None,t_oldest=None,filename=None):
        
        if filename:        
            filename.replace(".hdf5","")        
            data = pd.read_hdf(os.path.join(cg.datadir,filename+".hdf5"))
            return data
        
        timelist = []
        arcfiles = os.listdir(cg.datadir)

        for idx,af in enumerate(arcfiles):
            try:
                timelist.append(self.arcname_to_time(af.replace(".hdf5","")))
            except ValueError:
                del arcfiles[idx]
        
        timelist = np.array(timelist)
        
        # Exclude data outside of our desired timeframe
        if t_newest==None:
            t_newest = time.time()
        if t_oldest==None:
            t_oldest = t_newest-24*60*60
            
        cutidx = (timelist<=t_newest) & (timelist>=t_oldest)
        
        arcfiles = np.array(arcfiles)[cutidx]
        data = self.empty_data_frame
        for idx,af in enumerate(arcfiles):
            data = pd.concat([data,pd.read_hdf(os.path.join(cg.datadir,af))],ignore_index=True)
        return data
        
        
        
        
    
    def create_empty_dataframe(self):
        data = dict()
        for k in self.channel_list:
            data[k] = []
        
        return pd.DataFrame(data)
    
    def create_arcname(self):
        t0 = time.time()
        return t0, self.time_to_arcname(t0)
    
    def check_new_arc(self):
        '''
        Checks if a new arcfile needs to be created. 
        Current checks:
            - File size (i.e. >25MB)
            - Time span (i.e. once per day)

        Returns
        -------
        Bool

        '''
        make_new_arc_flag = False

        if os.path.getsize(os.path.join(cg.datadir,self.arcname+".hdf5"))/1.0e6>cg.data_size_threshold:
            make_new_arc_flag = True
        
        elif (time.time()-self.arctime)/60/60/24 >= cg.data_time_threshold:
            make_new_arc_flag = True
                
        if make_new_arc_flag:
            self.init_new_arc()
        
        return
    
    def time_to_arcname(self, timeval):
        return time.strftime("%y%m%d_%H%M%S",time.localtime(timeval))
    
    def arcname_to_time(self, arcname):
        return datetime.strptime(arcname,"%y%m%d_%H%M%S").timestamp()
    
    
# for testing
if __name__ == '__main__':

    arc = ADR_ARC()
    arc.load_arc(filename="250425_174819")
    
    
    
    
