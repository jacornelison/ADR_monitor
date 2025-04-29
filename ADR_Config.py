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
        self.daq_verbose_output = False # Will output data to terminal if True
        
        # GUI specifics
        self.plot_refresh_rate = 3000 # in milliseconds
        self.monitor_gui_parameters = self.get_mon_gui_parameters()
        
        # Channel Specifics
        self.channel_wildcard = "#_"
        
        # Any further initialization we need
        if init_channel_functions:
            from SRS_SIM9XX_v3 import SIM900, SIM960, SIM921, SIM922, SIM925, SIM970
            
            self.sim900 = SIM900
            self.sim960 = SIM960()
            self.sim970 = SIM970()
            self.sim925 = SIM925()
            self.sim921 = SIM921()
            self.sim922 = SIM922()
            self.time = time
            self.pt415_interface = pt415_interface
            
            # Init sim921/925
            self.sim921.set_RANG(6) # 6: 20 kO; 7: 200 kO
            self.sim921.set_MODE(2) # voltage
            self.sim921.set_EXCI(3) # 100 uV
            self.sim921.set_TCON(0) # 3s
            self.sim921.set_ADIS(1) # Autorange display
            self.sim921.set_CURV(1) # Select Curve
            self.sim925.set_CHAN(1)

        
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
            "FAA Temp": ["sim921","get_TVAL",None,None,None],
            "Sim970 #_": ["sim970","get_VOLT",(0),["EMF","MagCurr","MagVolt","Pressure (Torr)"],[0,1,2,3]],
            "Cmpsr #_" : ["pt415_interface","status_read_simple",None, pt415_interface.pt415_names, range(0,len(pt415_interface.pt415_names))],
        }
        
        self.channel_plot_options = {}
    
    def get_mon_gui_parameters(self):
        params = [
            {
                'name': 'Global Paramters', 'type':'group','children':
                    [
                     {'name':'Zoom Scrolling', 'type':'group','children':
                      [
                          {'name':'Scrolling','type':'bool','value':True},
                          {'name':'Scroll Time (Min)','type':'float','value':5.0},
                       ]                      
                      }   
                    ],
                }
            ]
        return params
    
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
    
