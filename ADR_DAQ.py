# -*- coding: utf-8 -*-
"""
ADR_DAQ.py

DAQ runner for ADR monitor:
- Reads configured monitor channels (cg.monitor_channels)
- Saves averaged data to ARC logs
- Publishes "fast" magnet telemetry (Time/EMF/MagCurr/MagVolt) to an in-memory cache
  and a 1-element queue for control loops.
"""

import copy
import time
import asyncio as aio
from typing import Optional, Dict, Any

import pandas as pd

from ADR_ARC import ADR_ARC
from ADR_Config import ADR_Config
from ADR_shared import SIM_IO_LOCK


# Instantiate these at import time to match your existing pattern.
# If you ever want faster import / easier testing, we can move these into ADR_DAQ.__init__.
arc = ADR_ARC()
cg = ADR_Config(init_channel_functions=True)
mc = cg.monitor_channels


class ADR_DAQ:
    def __init__(self):
        arc.init_new_arc()

        self.sample_rate = copy.deepcopy(cg.daq_sample_rate)
        self.verbose = copy.deepcopy(cg.daq_verbose_output)
        self.adr_config = cg

        # Shared SIM900 I/O lock (critical)
        self.sim_lock = SIM_IO_LOCK

        # Latest “fast” magnet telemetry (for control loops)
        self.mag_queue: aio.Queue = aio.Queue(maxsize=1)
        self._latest_mag: Optional[Dict[str, Any]] = None
        self._latest_mag_lock = aio.Lock()

        # Control interface
        self.command_queue: aio.Queue = aio.Queue()
        self._stop_event = aio.Event()
        self._pause_event = aio.Event()
        self._pause_event.set()

        # Background task handle
        self.task: Optional[aio.Task] = None

        # Not strictly used, but kept for compatibility
        self.data = None

    # -------------------------------------------------------------------------
    # Magnet telemetry publishing (cache + latest-wins queue)
    # -------------------------------------------------------------------------
    async def _put_mag(self, mag_dict: Dict[str, Any]) -> None:
        """Store and publish newest magnet telemetry without growing the queue."""
        async with self._latest_mag_lock:
            self._latest_mag = mag_dict

        # "latest wins" semantics: queue holds at most one newest sample.
        try:
            if self.mag_queue.full():
                _ = self.mag_queue.get_nowait()
            self.mag_queue.put_nowait(mag_dict)
        except aio.QueueFull:
            # Extremely unlikely given our full() logic, but safe to ignore.
            pass

    async def get_latest_mag(self) -> Optional[Dict[str, Any]]:
        """Return the most recent magnet telemetry dict (or None if not ready)."""
        async with self._latest_mag_lock:
            return None if self._latest_mag is None else dict(self._latest_mag)

    async def wait_mag(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Wait for the next magnet telemetry update from DAQ."""
        if timeout is None:
            return await self.mag_queue.get()
        return await aio.wait_for(self.mag_queue.get(), timeout=timeout)

    # -------------------------------------------------------------------------
    # Channel acquisition (sync read + async wrapper)
    # -------------------------------------------------------------------------
    def read_channels(self) -> pd.DataFrame:
        """
        Synchronous channel read. This may block (instrument I/O).
        Must ONLY be called while holding self.sim_lock, via read_channels_async().
        """
        data = copy.deepcopy(arc.empty_data_frame)

        for _, chan in enumerate(mc):
            mclist = mc[chan]

            # mclist layout appears to be:
            # [obj_name, method_name, method_arg_or_None, subchannels_or_None, subchannel_indices]
            obj = getattr(cg, mclist[0])
            fn = getattr(obj, mclist[1])

            if mclist[2] is None:
                val = fn()
            else:
                val = fn(mclist[2])

            if mclist[3] is None:
                data.loc[0, chan] = val
            else:
                for subidx, subch in enumerate(mclist[3]):
                    col = chan.replace(cg.channel_wildcard, subch)
                    data.loc[0, col] = val[mclist[4][subidx]]

        return data

    async def read_channels_async(self) -> pd.DataFrame:
        """
        Read all channels under the shared SIM I/O lock, using a worker thread.
        This prevents concurrent SIM900 traffic from DAQ vs magnet control.
        """
        async with self.sim_lock:
            # asyncio.to_thread is available in Python 3.9+
            return await aio.to_thread(self.read_channels)

    # -------------------------------------------------------------------------
    # Main run loop
    # -------------------------------------------------------------------------
    async def DAQ_run(self) -> None:
        """
        DAQ loop:
        - repeatedly sample channels for `self.sample_rate` seconds
        - average the samples
        - save to arc
        - continuously service command queue
        """
        data = copy.deepcopy(arc.empty_data_frame)
        t0 = time.time()

        try:
            print("Starting DAQ")

            while not self._stop_event.is_set():
                await self._handle_commands()

                # Pause handling
                while not self._pause_event.is_set():
                    await self._handle_commands()
                    await aio.sleep(0.1)
                    if self._stop_event.is_set():
                        break

                if self._stop_event.is_set():
                    break

                # Collect samples for `sample_rate` seconds
                while (time.time() - t0) < self.sample_rate and not self._stop_event.is_set():
                    await self._handle_commands()
                    if not self._pause_event.is_set():
                        break  # jump back to pause loop

                    sample = await self.read_channels_async()

                    # Publish magnet telemetry each sample (if columns exist)
                    row = sample.iloc[0]
                    mag = {
                        "Time": float(row.get("Time", float("nan"))),
                        "EMF": float(row.get("Sim970 EMF", float("nan"))),
                        "MagCurr": float(row.get("Sim970 MagCurr", float("nan"))),
                        "MagVolt": float(row.get("Sim970 MagVolt", float("nan"))),
                    }
                    await self._put_mag(mag)

                    data = pd.concat([data, sample], ignore_index=True)
                    await aio.sleep(0.001)

                # If we were paused mid-window, don’t average/save partial buffer yet.
                if not self._pause_event.is_set():
                    continue

                # Average & save
                if len(data) > 0:
                    data_avg = data.mean(axis=0).to_frame().T
                else:
                    data_avg = copy.deepcopy(arc.empty_data_frame)

                if self.verbose:
                    print(data_avg)

                arc.save_arc(data_avg)

                # Reset buffer/window
                data = copy.deepcopy(arc.empty_data_frame)
                t0 = time.time()

        except KeyboardInterrupt:
            print("Stopping DAQ (KeyboardInterrupt)")
            await self.stop()
            cg.close(init_channel_functions=True)

    async def start(self) -> None:
        """Start DAQ_run as a background task (returns immediately)."""
        if self.task is None or self.task.done():
            self._stop_event.clear()
            self._pause_event.set()
            self.task = aio.create_task(self.DAQ_run())

    # -------------------------------------------------------------------------
    # Command handling / public control methods
    # -------------------------------------------------------------------------
    async def _handle_commands(self) -> None:
        """Process all pending commands without blocking."""
        while not self.command_queue.empty():
            command, args = await self.command_queue.get()

            if command == "pause":
                self._pause_event.clear()
                print("DAQ paused.")

            elif command == "resume":
                self._pause_event.set()
                print("DAQ resumed.")

            elif command == "change_sampling":
                self.sample_rate = args.get("interval", self.sample_rate)
                print("Sampling interval changed to {} s.".format(self.sample_rate))

            elif command == "set_verbose":
                self.verbose = args.get("flag", self.verbose)
                print("Verbosity set to {}.".format(self.verbose))

            elif command == "stop":
                self._stop_event.set()
                self._pause_event.set()  # in case it's paused
                print("DAQ stopping...")

        await aio.sleep(0.001)

    async def change_sampling_rate(self, interval: float) -> None:
        await self.command_queue.put(("change_sampling", {"interval": interval}))

    async def set_verbose(self, flag: bool) -> None:
        await self.command_queue.put(("set_verbose", {"flag": flag}))

    async def pause(self) -> None:
        await self.command_queue.put(("pause", {}))

    async def resume(self) -> None:
        await self.command_queue.put(("resume", {}))

    async def stop(self) -> None:
        """Request stop and await the DAQ task to finish."""
        await self.command_queue.put(("stop", {}))
        if self.task is not None:
            await self.task

    def __del__(self):
        # Keep destructor minimal: instrument handles are managed by ADR_Config/cg
        return


# -----------------------------------------------------------------------------
# Standalone run (useful for testing)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    async def _main():
        daq = ADR_DAQ()
        await daq.start()
        # Run forever until Ctrl+C
        while True:
            await aio.sleep(1.0)

    aio.run(_main())