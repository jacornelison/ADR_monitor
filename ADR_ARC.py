"""ADR archive I/O utilities.

This module provides :class:`ADR_ARC`, a small helper used by the ADR DAQ/monitor
to write and read time-ordered telemetry data from disk.

Storage format
--------------
- Each archive file is a pandas HDF5 store written with ``format='table'``.
- Files are named ``YYMMDD_HHMMSS.hdf5`` (local time) and live in ``ADR_Config.datadir``.
- Data are appended under key ``'data'``.

Why multiple files?
-------------------
To keep individual HDF5 files from growing too large (or spanning too long a time),
the archive rolls over to a new file when either:
- the current file exceeds ``ADR_Config.data_size_threshold`` (MB), or
- the current file is older than ``ADR_Config.data_time_threshold`` (days).

All times are Unix epoch seconds.
"""

from __future__ import annotations

import bisect
import os
import time
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ADR_Config import ADR_Config

# HDF5 file locking can cause issues on network shares; pandas HDF uses PyTables/HDF5.
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

cg = ADR_Config()
mc = cg.monitor_channels


class ADR_ARC:
    """Read/write ADR telemetry archive files."""

    def __init__(self) -> None:
        self.channel_list = self.init_channel_list()
        self.arctime: Optional[float] = None
        self.arcname: Optional[str] = None
        self.empty_data_frame = self.create_empty_dataframe()

    def init_channel_list(self) -> List[str]:
        """Expand configured channels (including wildcard subchannels) into a flat list."""
        channel_list: List[str] = []
        for chan in mc:
            subnames = mc[chan][3]
            if subnames is None:
                channel_list.append(chan)
            else:
                for subch in subnames:
                    channel_list.append(chan.replace(cg.channel_wildcard, subch))
        return channel_list

    def save_arc(self, data: pd.DataFrame, filename: Optional[str] = None) -> None:
        """Append a dataframe of samples to the current archive file.

        Parameters
        ----------
        data:
            Telemetry samples to append. Expected to include a "Time" column plus
            one column per channel.
        filename:
            Optional explicit archive base name (without .hdf5). If not provided,
            uses the current rolling archive name (creating one if needed).
        """
        self.check_new_arc()

        if filename is None:
            filename = self.arcname

        if filename is None:
            # If called before any archive was initialized, create one now.
            self.init_new_arc(do_save=True)
            filename = self.arcname

        data.to_hdf(
            os.path.join(cg.datadir, filename + ".hdf5"),
            key="data",
            mode="a",
            format="table",
            append=True,
        )

    def init_new_arc(self, do_save: bool = True) -> None:
        """Start a new rolling archive file."""
        self.arctime, self.arcname = self.create_arcname()

        if do_save and self.arcname is not None:
            self.empty_data_frame.to_hdf(
                os.path.join(cg.datadir, self.arcname + ".hdf5"),
                key="data",
                mode="w",
                format="table",
            )
            print(f"Created new arcfile at: {os.path.join(cg.datadir, self.arcname + '.hdf5')}") 

    def load_arc(
        self,
        t_newest: Optional[float] = None,
        t_oldest: Optional[float] = None,
        filename: Optional[str] = None,
        columns: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        """Load archive data from disk.

        Parameters
        ----------
        t_newest, t_oldest:
            Time window bounds in epoch seconds. If both are None, defaults to the
            last 24 hours.
        filename:
            If provided, load *only* this specific archive file (base name, with or
            without the .hdf5 suffix) and return it without time filtering.
        columns:
            Optional list of columns to read (passed through to pandas ``read_hdf``).

        Returns
        -------
        pandas.DataFrame
            Concatenated samples within the requested time bounds.
        """
        # Direct file load (no windowing)
        if filename:
            filename = filename.replace(".hdf5", "")
            return pd.read_hdf(os.path.join(cg.datadir, filename + ".hdf5"))

        # Determine time window
        if t_newest is None:
            t_newest = time.time()
        if t_oldest is None:
            t_oldest = t_newest - 24 * 60 * 60

        # Build a sorted list of archive files by their embedded timestamps.
        arcfiles_all = os.listdir(cg.datadir)
        timelist: List[float] = []
        arcfiles: List[str] = []

        for af in arcfiles_all:
            try:
                timelist.append(self.arcname_to_time(af.replace(".hdf5", "")))
                arcfiles.append(af)
            except ValueError:
                # Ignore non-archive files in the data directory
                continue

        if len(arcfiles) == 0:
            return self.empty_data_frame.copy()

        timelist, arcfiles = zip(*sorted(zip(timelist, arcfiles)))
        timelist = np.array(timelist)

        # Find which archive files might contain the window.
        # Include one extra file before the lower bound because an archive can start
        # earlier than the requested t_oldest but still contain samples in range.
        idx_lower = bisect.bisect_right(timelist, t_oldest)
        idx_upper = bisect.bisect_right(timelist, t_newest)

        file_slice = np.arange(max(idx_lower - 1, 0), idx_upper)
        arcfiles_sel = np.array(arcfiles)[file_slice]

        frames: List[pd.DataFrame] = []
        for af in arcfiles_sel:
            try:
                frames.append(pd.read_hdf(os.path.join(cg.datadir, af), columns=columns))
            except ValueError:
                # Occasionally an archive file may be mid-write when read is attempted.
                continue

        if len(frames) == 0:
            return self.empty_data_frame.copy()

        data = pd.concat(frames, ignore_index=True)
        cutidx = (data["Time"].values >= t_oldest) & (data["Time"].values <= t_newest)
        return data.iloc[cutidx]

    def create_empty_dataframe(self) -> pd.DataFrame:
        """Create an empty dataframe with the correct channel columns."""
        data = {k: [] for k in self.channel_list}
        return pd.DataFrame(data)

    def create_arcname(self) -> Tuple[float, str]:
        """Generate a new archive name based on the current time."""
        t0 = time.time()
        return t0, self.time_to_arcname(t0)

    def check_new_arc(self) -> None:
        """Create a new archive file if the current one is too large or too old."""
        if self.arcname is None or self.arctime is None:
            self.init_new_arc(do_save=True)
            return

        make_new_arc_flag = False

        try:
            size_mb = os.path.getsize(os.path.join(cg.datadir, self.arcname + ".hdf5")) / 1.0e6
            if size_mb > cg.data_size_threshold:
                make_new_arc_flag = True
        except OSError:
            # If the current file went missing, start fresh.
            make_new_arc_flag = True

        if (time.time() - self.arctime) / (60 * 60 * 24) >= cg.data_time_threshold:
            make_new_arc_flag = True

        if make_new_arc_flag:
            self.init_new_arc()

    def time_to_arcname(self, timeval: float) -> str:
        """Convert epoch seconds to an archive filename stem (YYMMDD_HHMMSS)."""
        return time.strftime("%y%m%d_%H%M%S", time.localtime(timeval))

    def arcname_to_time(self, arcname: str) -> float:
        """Convert an archive filename stem (YYMMDD_HHMMSS) to epoch seconds."""
        return datetime.strptime(arcname, "%y%m%d_%H%M%S").timestamp()


if __name__ == "__main__":
    # Minimal smoke test: load a specific archive file by name.
    arc = ADR_ARC()
    _ = arc.load_arc(filename="250425_174819")
