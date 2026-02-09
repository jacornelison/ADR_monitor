# -*- coding: utf-8 -*-
"""
Created on Wed Feb  4 13:00:48 2026

@author: svc_csi359876
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import lmfit as lf


def params_from_dict(param_dict: dict) -> lf.Parameters:
    p = lf.Parameters()
    for name, cfg in param_dict.items():
        if not isinstance(cfg, dict):
            # allow shorthand: {'Fd': 1e-6}
            cfg = {'value': cfg}
        p.add(name, **cfg)
    return p




class DR_temp_read:
    """
    Read the most recent temperature value from Bluefors channel log files.

    Directory structure:
        <log_dir>/<yy-mm-dd>/CH<channel> T <yy-mm-dd>.log

    Log file rows (CSV, no header):
        dd-mm-yy,HH:MM:SS,temperature_K
    """

    def __init__(self, channel: int, log_dir: Optional[str] = None) -> None:
        self.channel = int(channel)
        self.log_dir = Path(
            log_dir
            if log_dir is not None
            else os.path.join("C:\\Users", "svc_csi359876", "Bluefors logs")
        )

    def _latest_date_folder(self) -> Path:
        """
        Return the Path to the most recent yy-mm-dd folder under self.log_dir.
        """
        if not self.log_dir.exists():
            raise FileNotFoundError(f"Log directory not found: {self.log_dir}")

        date_re = re.compile(r"^\d{2}-\d{2}-\d{2}$")
        dated = []
        for p in self.log_dir.iterdir():
            if p.is_dir() and date_re.match(p.name):
                # Interpret folder name as yy-mm-dd
                try:
                    dt = datetime.strptime(p.name, "%y-%m-%d")
                except ValueError:
                    continue
                dated.append((dt, p))

        if not dated:
            raise FileNotFoundError(f"No yy-mm-dd folders found under: {self.log_dir}")

        dated.sort(key=lambda x: x[0])
        return dated[-1][1]

    @staticmethod
    def _read_last_nonempty_line(path: Path) -> str:
        """
        Efficiently read the last non-empty line of a text file.
        """
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            if end == 0:
                raise ValueError(f"Empty log file: {path}")

            # Walk backwards until we have at least one full line
            chunk_size = 4096
            data = b""
            pos = end
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                data = f.read(read_size) + data
                if b"\n" in data and data.strip():
                    break

            # Split and find last non-empty
            lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
            if not lines:
                raise ValueError(f"No non-empty lines found in: {path}")
            return lines[-1].decode("utf-8", errors="replace")

    def temperature(self) -> float:
        """
        Return the most recent temperature reading (Kelvin) for this channel.
        """
        folder = self._latest_date_folder()
        datestr = folder.name  # yy-mm-dd
        expected = folder / f"CH{self.channel} T {datestr}.log"

        if not expected.exists():
            # Fallback: search in that folder for any matching file, in case naming differs slightly
            matches = sorted(folder.glob(f"CH{self.channel} T*.log"))
            if not matches:
                raise FileNotFoundError(
                    f"Could not find log for channel {self.channel} in {folder}"
                )
            expected = matches[-1]

        last_line = self._read_last_nonempty_line(expected)
        parts = [p.strip() for p in last_line.split(",")]
        if len(parts) < 3:
            raise ValueError(f"Malformed line in {expected}: {last_line!r}")

        try:
            T = float(parts[2])
        except ValueError as e:
            raise ValueError(f"Could not parse temperature from line: {last_line!r}") from e

        return T




class ADR_temp_read():
    def __init__(self):
        from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
        from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372_Channel
        # Thermometry Stuff
        lakeshore_address = 'GPIB0::3::INSTR'
        temp_channel = 10
        
        # Initialize Instruments
        
        
        # Initialize the Thermometry
        class Model_372_v2(Model_372):
            def __init__(self, name: str, address: str, **kwargs) -> None:
                super().__init__(name, address, **kwargs)
        
            def scan_status(self):
                self.visa_handle.write('SCAN?')
                _x = self.visa_handle.read()
                return [int(_y) for _y in _x.split(',')]
        
            def scan(self, ich, autoscan):
                self.visa_handle.write(f'SCAN {ich}, {autoscan}')
        
        ls = Model_372_v2('lakeshore_372_1', lakeshore_address)
        if temp_channel != 'A': # Select our channel and turn off autoscan
            ls.scan(temp_channel,0)
        self.res_temp = Model_372_Channel(ls, 'res_temp', str(temp_channel))
        
        
        
    def temperature(self,channel):
        return self.res_temp.temperature()

    
