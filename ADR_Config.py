# config file for ADR scripts

import os
import time
import pt415_interface

class ADR_Config():
    def __init__(self,init_channel_functions=False):
        # Data specifics
        self.datadir =  os.path.join('C:\\Users','detector-group','Documents','ADR_Monitor_Data')
        self.data_size_threshold = 25 # in Megabytes
        self.data_time_threshold = 1 # in days
        
        # DAQ Specifics
        self.daq_sample_rate = 60 # in seconds
        
        # GUI specifics
        self.plot_refresh_rate = 500 # in milliseconds
        
        # Channel Specifics
        self.channel_wildcard = "#_"
        
        # Any further initialization we need
        if init_channel_functions:
            from SRS_SIM9XX_v3 import SIM900, SIM960, SIM921, SIM922, SIM925, SIM970
            
            self.sim900 = SIM900
            #self.sim960 = SIM960()
            self.sim970 = SIM970()
            #self.sim925 = SIM925()
            #self.sim921 = SIM921()
            self.sim922 = SIM922()
            self.time = time
            self.pt415_interface = pt415_interface
        
        # Instead of calling it three times, call once and use array of names to break this entry into multiple channels
        # Use #_ as signifier for this.
        # Order "Channel Name": ["prime function",
        #"function to call",
        #"function args",
        #"subchannel Names",
        #"output array index",
        #"scaling factors"]
        self.monitor_channels = {
            "Time": ["time","time", None,None,None],
            "Stage Temp #_": ["sim922","get_TVAL",(0),["60K","Magnet","4K","4K No.2"],[0,1,2,3]],
            "Sim970 #_": ["sim970","get_VOLT",(0),["EMF","MagCurr","MagVolt","Pressure (Torr)"],[0,1,2,3]],
            "Cmpsr #_" : ["pt415_interface","status_read_simple",None, pt415_interface.pt415_names, range(0,len(pt415_interface.pt415_names))],
        }
        
    
    def __del__(self,init_channel_functions=False):
        if init_channel_functions:
            self.sim900.close()
            
    def close(self,init_channel_functions=False):
        if init_channel_functions:
            self.sim900.close()




# if __name__ == '__main__':
#     chname = "SIM922 300K"
#     #ch_fun_data = monitor_channels[chname]
#     #val = globals()[ch_fun_data[0]](*ch_fun_data[1])
#     val = getattr(globals()["sim922"], "get_TVAL")(0)
#     print(val)
#     #val = getattr(globals()["sim922"], "close")()
    
