"""
This example demonstrates the use of pyqtgraph's dock widget system.

The dockarea system allows the design of user interfaces which can be rearranged by
the user at runtime. Docks can be moved, resized, stacked, and torn out of the main
window. This is similar in principle to the docking system built into Qt, but 
offers a more deterministic dock placement API (in Qt it is very difficult to 
programatically generate complex dock arrangements). Additionally, Qt's docks are 
designed to be used as small panels around the outer edge of a window. Pyqtgraph's 
docks were created with the notion that the entire window (or any portion of it) 
would consist of dockable components.
"""

import numpy as np
import os
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'
import pyqtgraph as pg
from pyqtgraph.console import ConsoleWidget
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.parametertree import Parameter, ParameterTree
from ADR_Config import ADR_Config
from ADR_ARC import ADR_ARC
arc = ADR_ARC()
cg = ADR_Config()



app = pg.mkQApp("DockArea Example")
win = QtWidgets.QMainWindow()
area = DockArea()
area_params = DockArea()
area_params.setMinimumWidth(250)
splitter = QtWidgets.QSplitter()
splitter.addWidget(area_params)
splitter.addWidget(area)
splitter.setStretchFactor(0, 0)  # Parameter area stays smaller
splitter.setStretchFactor(1, 1)  # Plot area takes most space

win.setCentralWidget(splitter)
win.resize(1000,500)
win.setWindowTitle('pyqtgraph example: dockarea')

# ## Create docks, place them into the window one at a time.
# ## Note that size arguments are only a suggestion; docks will still have to
# ## fill the entire dock area and obey the limits of their internal widgets.
d1 = Dock("Dock1", size=(100, 100))     ## give this dock the minimum possible size
# d2 = Dock("Dock2 - Console", size=(500,300), closable=True)
# d3 = Dock("Dock3", size=(500,400))
# d4 = Dock("Dock4 (tabbed) - Plot", size=(500,200))
# d5 = Dock("Dock5 - Image", size=(500,200))
# d6 = Dock("Dock6 (tabbed) - Plot", size=(500,200))
area_params.addDock(d1)      ## place d1 at left edge of dock area (it will fill the whole space since there are no other docks yet)
# area.addDock(d2, 'right')     ## place d2 at right edge of dock area
# area.addDock(d3, 'bottom', d1)## place d3 at bottom edge of d1
# area.addDock(d4, 'right')     ## place d4 at right edge of dock area
# area.addDock(d5, 'left', d1)  ## place d5 at left edge of d1
# area.addDock(d6, 'top', d4)   ## place d5 at top edge of d4

# ## Test ability to move docks programatically after they have been placed
# area.moveDock(d4, 'top', d2)     ## move d4 to top edge of d2
# area.moveDock(d6, 'above', d4)   ## move d6 to stack on top of d4
# area.moveDock(d5, 'top', d2)     ## move d5 to top edge of d2


# ## Add widgets into each dock

# ## first dock gets save/restore buttons
w1 = pg.LayoutWidget()
label = QtWidgets.QLabel(""" -- DockArea Example -- 
This window has 6 Dock widgets in it. Each dock can be dragged
by its title bar to occupy a different space within the window 
but note that one dock has its title bar hidden). Additionally,
the borders between docks may be dragged to resize. Docks that are dragged on top
of one another are stacked in a tabbed layout. Double-click a dock title
bar to place it in its own window.
""")
#saveBtn = QtWidgets.QPushButton('Save dock state')
#restoreBtn = QtWidgets.QPushButton('Restore dock state')
#restoreBtn.setEnabled(False)
#w1.addWidget(label, row=0, col=0)
#w1.addWidget(saveBtn, row=1, col=0)
#w1.addWidget(restoreBtn, row=2, col=0)
params = Parameter.create(name='params',type='group',children=cg.monitor_gui_parameters)
t = ParameterTree()
t.setParameters(params,showTop=False)
#w1.addWidget(t)
d1.addWidget(t)


# import pandas as pd

class ADR_plot():
    def __init__(self,ch_name):
        self.Dock = Dock(name=ch_name,closable=True,size=(200,100))
        self.PlotWidget = pg.PlotWidget(axisItems={'bottom':pg.DateAxisItem()})
        self.plot = self.PlotWidget.plot(pen=pg.mkPen(color=(255,51,0),width=2))
        
        self.PlotWidget.showGrid(x=True,y=True)
        self.Dock.addWidget(self.PlotWidget)


def init_dock_and_plot(area,channel_list,channel_group):
    plot_list = []
    
    for kidx,k in enumerate(channel_list):
        plot_list.append(ADR_plot(ch_name=k))
        
        if kidx==0:
            area.addDock(plot_list[kidx].Dock)
        elif channel_group[kidx]==channel_group[kidx-1]:
            area.addDock(plot_list[kidx].Dock,'below',plot_list[kidx-1].Dock)
        else:
            area.addDock(plot_list[kidx].Dock,'bottom',plot_list[kidx-1].Dock)
    return plot_list

def get_channel_groups():
    mc = cg.monitor_channels
    channel_group = []
    channel_list = []
    for chidx,chan in enumerate(mc):
        subnames = mc[chan][3]
        if subnames==None:
            channel_list.append(chan)
            channel_group.append(chidx)
        else:
            for subch in subnames:
                channel_list.append(chan.replace(cg.channel_wildcard,subch))       
                channel_group.append(chidx)
    
    # Return all channels except Time
    return channel_list[1::], channel_group[1::]


channel_list, channel_group = get_channel_groups()
plot_list = init_dock_and_plot(area,channel_list, channel_group)
#print(plot_list)

def update_plots():
    global plot_list, params
    data = arc.load_arc()
    t = data["Time"].values
    idx = (t <= t[-1])
    if params['Global Paramters','Zoom Scrolling','Scrolling']:
        rng = params['Global Paramters','Zoom Scrolling','Scroll Time (Min)']
        idx = (t >= (t[-1] - rng*60))
    for kidx,k in enumerate(arc.channel_list[1::]):
        plot_list[kidx].plot.setData(x=data["Time"].iloc[idx].values,y=data[k].iloc[idx].values)
    

    



timer = QtCore.QTimer()
timer.timeout.connect(update_plots)
timer.start(cg.plot_refresh_rate)

# w2 = ConsoleWidget()
# d2.addWidget(w2)

# ## Hide title bar on dock 3
# d3.hideTitleBar()
# w3 = pg.PlotWidget(title="Plot inside dock with no title bar")
# w3.plot(np.random.normal(size=100))
# d3.addWidget(w3)

# w4 = pg.PlotWidget(title="Dock 4 plot")
# w4.plot(np.random.normal(size=100))
# d4.addWidget(w4)

# w5 = pg.ImageView()
# w5.setImage(np.random.normal(size=(100,100)))
# d5.addWidget(w5)

# w6 = pg.PlotWidget(title="Dock 6 plot")
# w6.plot(np.random.normal(size=100))
# d6.addWidget(w6)


tree_size = t.sizeHint()
d1.resize(tree_size.width() + 20, tree_size.height() + 20)
win.resize(1000,500)
win.show()



if __name__ == '__main__':
    pg.exec()
