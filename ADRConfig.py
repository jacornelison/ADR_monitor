# config file for ADR scripts

import os
from SRS_SIM9XX_v3 import SIM900, SIM960, SIM921, SIM922, SIM925, SIM970

#sim900 = SIM900()
sim960 = SIM960()
sim970 = SIM970()
sim925 = SIM925()
sim921 = SIM921()
sim922 = SIM922()

# set up channels to monitor
# Order "Channel Name": ["prime function",
#"function to call",
#"function args",
#"output array index", # Instead of calling it three times, call once and use array of names to break this entry into multiple channels
#"scaling factors"]
monitor_channels = {
    "Stage Temp #_K": ["sim922","get_TVAL",(0),[]],
    "Test_Channel 2": ["bar",[""],[]]
}

# data save file location
datadir =  os.path.join('C:\\Users','detector-group','Documents','ADR_Monitor_Data')



if __name__ == '__main__':
    chname = "SIM922 300K"
    ch_fun_data = monitor_channels[chname]
    #val = globals()[ch_fun_data[0]](*ch_fun_data[1])
    val = getattr(sim922, "get_TVAL")(0)
    print(val)
    
