"""ADR configuration for the ADR monitor/DAQ (time-range enabled).

This variant of ADR_Config includes an additional ParameterTree group
("Global Paramters" -> "Time Range") used by ADR_monitor_main_time_range.

The config defines:
- where archive data live on disk
- channel definitions (including wildcard-expanded subchannels)
- GUI parameters and refresh rates
- optional conversion functions for plotting
"""

import os
import time
import pt415_interface
import ADR_misc_funcs as mf


class ADR_Config():
    """Configuration container for ADR monitoring and acquisition.

    Parameters
    ----------
    init_channel_functions:
        If True, import and initialize instrument interfaces (SIM9xx, PT415, etc.).
        The monitor GUI typically runs with this False and reads from the archive.
    """

    def __init__(self,init_channel_functions=False):
        self.mf = mf
        
        # Data specifics
        self.datadir =  os.path.join('C:\\Users','detector-group','Documents','ADR_Monitor_Data')
        self.data_size_threshold = 25 # in Megabytes
        self.data_time_threshold = 1 # in days
        
        # DAQ Specifics
        self.daq_sample_rate = 60 # in seconds
        self.daq_verbose_output = False # Will output data to terminal if True
        
        # GUI specifics
        self.plot_refresh_rate = 1000 # in milliseconds
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
        
        self.channel_plot_options = {
            "Sim970 Pressure (Torr)": {"convert_func":"SIM970_pressure_curve"},
            }
    
    def get_mon_gui_parameters(self):
        """Build the ParameterTree schema used by the GUI.

        Returns a list of parameter dictionaries compatible with
        ``pyqtgraph.parametertree.Parameter.create(children=...)``.

        The "Time Range" group is used by the monitor GUI to:
        - freeze plotting to a manual [start, end] window (and pause live updates)
        - return to continuous plotting of the last 24 hours
        """
        params = [
            {
                'name': 'Global Paramters', 'type': 'group', 'children':
                    [
                        {'name': 'Zoom Scrolling', 'type': 'group', 'children':
                            [
                                {'name': 'Scrolling', 'type': 'bool', 'value': True},
                                {'name': 'Scroll Time (Min)', 'type': 'float', 'value': 120.0},
                            ]
                        },
                        {'name': 'Time Range', 'type': 'group', 'children':
                            [
                                {'name': 'Use Manual Range', 'type': 'bool', 'value': False},
                                {'name': 'Start (YYYY-MM-DD HH:MM:SS)', 'type': 'str', 'value': ''},
                                {'name': 'End (YYYY-MM-DD HH:MM:SS)', 'type': 'str', 'value': ''},
                                {'name': 'Apply Manual Range', 'type': 'action'},
                                {'name': 'Return to Live (Last 24h)', 'type': 'action'},
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




