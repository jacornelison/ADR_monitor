"""ADR Monitor GUI (time-range capable).

This module launches the ADR monitor GUI, which plots archived ADR telemetry in real time
using pyqtgraph's DockArea/ParameterTree widgets.

Key behaviors
-------------
- Live mode (default): continuously updates, plotting the most recent data.
  If "Zoom Scrolling" is enabled, the view is restricted to the last N minutes.

- Manual time range mode: plots a fixed [start, end] window and *pauses* live updating
  (the QTimer is stopped) so the display remains static.

- "Return to Live (Last 24h)" switches back to continuous plotting of the last 24 hours.

Notes
-----
- Time values are assumed to be Unix epoch seconds throughout.
- Archive I/O is handled by :class:`ADR_ARC.ADR_ARC`.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import pyqtgraph as pg
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.parametertree import Parameter, ParameterTree

from ADR_ARC import ADR_ARC
from ADR_Config_time_range import ADR_Config

# HDF5 file locking can cause issues on network shares; the archive code uses HDF5 via pandas.
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

arc = ADR_ARC()
cg = ADR_Config()

# ---- Qt / pyqtgraph app + top-level window ----

app = pg.mkQApp("ADR Monitor")
win = QtWidgets.QMainWindow()
win.setWindowTitle("ADR Monitor Plots")

area_plots = DockArea()
area_params = DockArea()
area_params.setMinimumWidth(250)

splitter = QtWidgets.QSplitter()
splitter.addWidget(area_params)
splitter.addWidget(area_plots)
splitter.setStretchFactor(0, 0)  # Parameter area stays smaller
splitter.setStretchFactor(1, 1)  # Plot area takes most space
win.setCentralWidget(splitter)

# ---- Parameter tree root ----

params = Parameter.create(name="globals", type="group", children=cg.monitor_gui_parameters)

# ---- Plot widgets (one per channel) ----


class ADRPlot:
    """Single channel plot + its per-channel parameter controls."""

    def __init__(self, ch_name: str, ch_group: int, plot_area: DockArea, group_params: Parameter):
        self.ch_name = ch_name
        self.ch_group = ch_group
        self._plot_area = plot_area
        self._group_params = group_params

        self.dock = Dock(name=ch_name, size=(200, 100))
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen(color=(255, 51, 0), width=2))
        self.plot_widget.showGrid(x=True, y=True)

        self.dock.addWidget(self.plot_widget)
        self.params = self._init_params()

    def _init_params(self) -> Parameter:
        p = Parameter.create(
            name=self.ch_name,
            title=self.ch_name,
            type="group",
            children=[
                {"name": "On/Off", "type": "bool", "value": True},
                {"name": "Log Scale", "type": "bool", "value": False},
            ],
        )
        p.param("On/Off").sigValueChanged.connect(self._toggle_dock)
        p.param("Log Scale").sigValueChanged.connect(self._toggle_log_scale)
        return p

    def _toggle_dock(self, _param: Parameter, enabled: bool) -> None:
        """Show/hide this channel's dock, preserving its plot widget."""
        if enabled:
            # Recreate a Dock (so it can be reinserted cleanly) but reuse the plot widget.
            self.dock = Dock(name=self.ch_name, closable=True, size=(200, 100))
            self.plot_widget.showGrid(x=True, y=True)
            self.dock.addWidget(self.plot_widget)

            # Insert above the first active dock in this channel group (if possible).
            for child_idx, child in enumerate(self._group_params.children()):
                if child.name() == self.ch_name:
                    continue
                if child.param("On/Off").value():
                    self._plot_area.addDock(self.dock, "above", plot_list[self.ch_group][child_idx].dock)
                    break
            else:
                self._plot_area.addDock(self.dock)
        else:
            self.dock.close()

    def _toggle_log_scale(self, _param: Parameter, enabled: bool) -> None:
        self.plot_curve.setLogMode(False, enabled)


def _get_channel_groups() -> Tuple[list[str], list[int]]:
    """Expand `cg.monitor_channels` into a flat list of channel names and group ids.

    The config supports wildcard channel names (e.g. "Stage Temp #_") which expand
    into multiple subchannels. The first entry is expected to be "Time" and is excluded.
    """
    mc = cg.monitor_channels
    channel_group: list[int] = []
    channel_list: list[str] = []

    for chidx, chan in enumerate(mc):
        subnames = mc[chan][3]
        if subnames is None:
            channel_list.append(chan)
            channel_group.append(chidx - 1)
        else:
            for subch in subnames:
                channel_list.append(chan.replace(cg.channel_wildcard, subch))
                channel_group.append(chidx - 1)

    # Return all channels except Time
    return channel_list[1:], channel_group[1:]


def _init_docks_and_plots(channel_list: list[str], channel_group: list[int]) -> Tuple[list[list[ADRPlot]], Parameter]:
    """Create plot docks and the matching plot-options Parameter group."""
    plot_params = Parameter.create(name="params", title="Plot Options", type="group", children=[])

    plot_list_local: list[list[ADRPlot]] = []
    for grp in np.unique(channel_group):
        plot_list_local.append([])
        plot_params.addChild(Parameter.create(name=f"Channel Group {grp}", title=f"Channel Group {grp}", type="group", children=[]))

    for idx, ch in enumerate(channel_list):
        grp = channel_group[idx]
        grp_param = plot_params.param(f"Channel Group {grp}")
        p = ADRPlot(ch_name=ch, ch_group=grp, plot_area=area_plots, group_params=grp_param)
        plot_list_local[grp].append(p)
        grp_param.addChild(p.params)

        # First plot starts the layout; subsequent plots are stacked under previous ones.
        if idx == 0:
            area_plots.addDock(p.dock)
        elif channel_group[idx] == channel_group[idx - 1]:
            area_plots.addDock(p.dock, "below", plot_list_local[grp][-2].dock)
        else:
            area_plots.addDock(p.dock, "bottom", plot_list_local[grp - 1][0].dock)

    return plot_list_local, plot_params


channel_list, channel_group = _get_channel_groups()
plot_list, plt_params = _init_docks_and_plots(channel_list, channel_group)
params.addChild(plt_params)

# ---- Manual time range plotting helpers ----

_plot_state = {"manual": False, "t_oldest": None, "t_newest": None}
timer: Optional[QtCore.QTimer] = None


def _set_param_value(path_tuple: Tuple[str, ...], value) -> None:
    """Set a pyqtgraph Parameter value (attempting to block signal emission)."""
    try:
        p = params.param(*path_tuple)
        try:
            p.setValue(value, blockSignal=True)
        except TypeError:
            # older pyqtgraph versions may not support blockSignal keyword
            p.setValue(value)
    except Exception:
        pass


def _parse_time_input(s: Optional[str]) -> Optional[float]:
    """Parse user input into epoch seconds.

    Accepts:
      - empty string -> None
      - unix seconds (float/int)
      - datetime strings: 'YYYY-MM-DD HH:MM[:SS]' or ISO 'YYYY-MM-DDTHH:MM[:SS]'
      - 'now'
    """
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    if s.lower() == "now":
        return time.time()

    # Numeric epoch seconds
    try:
        return float(s)
    except ValueError:
        pass

    # Common datetime formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue

    # ISO 8601 (e.g. 2026-01-12T10:00:00)
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError as e:
        raise ValueError(
            f"Unrecognized time '{s}'. Use unix seconds or 'YYYY-MM-DD HH:MM:SS'."
        ) from e


def _get_manual_range_from_params() -> Tuple[float, float]:
    """Read and normalize [start, end] from the Global Parameters -> Time Range group."""
    t0 = _parse_time_input(params["Global Paramters", "Time Range", "Start (YYYY-MM-DD HH:MM:SS)"])
    t1 = _parse_time_input(params["Global Paramters", "Time Range", "End (YYYY-MM-DD HH:MM:SS)"])

    # Defaults if only one end is supplied
    if t0 is None and t1 is None:
        t1 = time.time()
        t0 = t1 - 24 * 60 * 60
    elif t0 is None:
        t0 = t1 - 24 * 60 * 60
    elif t1 is None:
        t1 = time.time()

    if t0 > t1:
        t0, t1 = t1, t0

    return float(t0), float(t1)


def apply_manual_range() -> None:
    """Plot the manual time window once, then pause live updating."""
    global timer
    try:
        t0, t1 = _get_manual_range_from_params()
    except Exception as e:
        print(f"[ADR Monitor] Manual range parse error: {e}")
        return

    _plot_state.update(manual=True, t_oldest=t0, t_newest=t1)

    # Ensure the UI toggle reflects the state
    _set_param_value(("Global Paramters", "Time Range", "Use Manual Range"), True)

    # Pause updates and redraw once
    if timer is not None:
        timer.stop()
    update_plots()

    print(f"[ADR Monitor] Manual plot window set: {datetime.fromtimestamp(t0)} -> {datetime.fromtimestamp(t1)}")


def resume_live_last24h() -> None:
    """Return to continuous plotting of the last 24 hours."""
    global timer
    _plot_state.update(manual=False, t_oldest=None, t_newest=None)

    _set_param_value(("Global Paramters", "Time Range", "Use Manual Range"), False)
    _set_param_value(("Global Paramters", "Zoom Scrolling", "Scrolling"), False)

    update_plots()
    if timer is not None and not timer.isActive():
        timer.start(cg.plot_refresh_rate)

    print("[ADR Monitor] Returned to live view (last 24 hours).")


def _on_manual_toggle(_param: Parameter, enabled: bool) -> None:
    """Respond to the 'Use Manual Range' toggle."""
    global timer
    if enabled:
        # If the user enables manual mode without specifying a range, freeze the last 24 hours.
        if not _plot_state.get("manual", False) or _plot_state.get("t_oldest") is None:
            t1 = time.time()
            _plot_state.update(manual=True, t_oldest=t1 - 24 * 60 * 60, t_newest=t1)

        if timer is not None:
            timer.stop()
        update_plots()
        print("[ADR Monitor] Manual mode enabled. Live updating paused.")
    else:
        resume_live_last24h()


def update_plots() -> None:
    """Fetch archive data and update each plot curve."""
    # Decide whether we're live (default) or frozen in a manual time window
    try:
        manual_enabled = bool(params["Global Paramters", "Time Range", "Use Manual Range"])
    except Exception:
        manual_enabled = False

    if manual_enabled or _plot_state.get("manual", False):
        t0 = _plot_state.get("t_oldest")
        t1 = _plot_state.get("t_newest")
        data = arc.load_arc(t_newest=t1, t_oldest=t0)
        idx = np.ones(len(data), dtype=bool)
    else:
        data = arc.load_arc()
        if len(data) == 0:
            return
        t = data["Time"].values
        idx = np.ones_like(t, dtype=bool)

        # Optional zoom-scrolling window (minutes)
        if params["Global Paramters", "Zoom Scrolling", "Scrolling"]:
            rng = params["Global Paramters", "Zoom Scrolling", "Scroll Time (Min)"]
            idx = t >= (t[-1] - rng * 60)

    if len(data) == 0:
        return

    for pltgrp in plot_list:
        for plt in pltgrp:
            if plt.ch_name in cg.channel_plot_options and "convert_func" in cg.channel_plot_options[plt.ch_name]:
                conv = getattr(cg.mf, cg.channel_plot_options[plt.ch_name]["convert_func"])
                y = conv(data[plt.ch_name].iloc[idx].values)
            else:
                y = data[plt.ch_name].iloc[idx].values

            plt.plot_curve.setData(x=data["Time"].iloc[idx].values, y=y)


# ---- Timer and signal wiring ----

timer = QtCore.QTimer()
timer.timeout.connect(update_plots)
timer.start(cg.plot_refresh_rate)

# Wire up time range controls (safe if the config doesn't include them)
try:
    params.param("Global Paramters", "Time Range", "Apply Manual Range").sigActivated.connect(apply_manual_range)
    params.param("Global Paramters", "Time Range", "Return to Live (Last 24h)").sigActivated.connect(resume_live_last24h)
    params.param("Global Paramters", "Time Range", "Use Manual Range").sigValueChanged.connect(_on_manual_toggle)
except Exception as e:
    print(f"[ADR Monitor] Could not connect time-range parameter signals: {e}")

# ---- ParameterTree dock ----

dock_params = Dock("Parameters", size=(100, 100))
area_params.addDock(dock_params)

tree = ParameterTree()
tree.setParameters(params, showTop=False)

# Keep the ParameterTree columns sane so long strings don't create a giant horizontal scroll bar
tree.setTextElideMode(QtCore.Qt.ElideRight)
hdr = tree.header()
try:
    hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
    hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
except Exception:
    # Qt4 compatibility
    try:
        hdr.setResizeMode(0, QtWidgets.QHeaderView.Stretch)
        hdr.setResizeMode(1, QtWidgets.QHeaderView.Interactive)
    except Exception:
        pass

tree.setColumnWidth(1, 240)
dock_params.addWidget(tree)

# Size the window and show
win.resize(1000, 500)
win.show()

if __name__ == "__main__":
    pg.exec()
