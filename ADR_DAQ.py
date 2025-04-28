# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 09:56:33 2025

@author: detector-group
"""

from ADR_ARC import ADR_ARC
from ADR_Config import ADR_Config
import copy
import pandas as pd
import time
#import threading as th
import asyncio as aio
arc = ADR_ARC()
cg = ADR_Config(init_channel_functions=True)
mc = cg.monitor_channels

class ADR_DAQ():
    def __init__(self):
        arc.init_new_arc()
        self.sample_rate = copy.deepcopy(cg.daq_sample_rate)
        self.verbose = copy.deepcopy(cg.daq_verbose_output)
        self.adr_config = cg
        self.command_queue = aio.Queue() #Allow for command changes
        self._stop_event = aio.Event()
        self._pause_event = aio.Event()
        self._pause_event.set() # Initially not paused
        self.task = None
        self.data = None
        return
    

    # Do the channel reading
    def read_channels(self):
        data = copy.deepcopy(arc.empty_data_frame)

        for chidx,chan in enumerate(mc):
            
            mclist = mc[chan]
            if mclist[2]==None:
                val = getattr(getattr(cg,mclist[0]), mclist[1])()
            else:
                val = getattr(getattr(cg,mclist[0]), mclist[1])(mclist[2])
                
            if mclist[3]==None:
                data.loc[0,chan] = val
            else:
                for subidx,subch in enumerate(mclist[3]):
                    data.loc[0,chan.replace(cg.channel_wildcard,subch)] = val[mclist[4][subidx]]


        return data

    async def DAQ_run(self):
        # Just read the channels as fast as we can
        # but average over the sampling rate to reduce noise
        data = copy.deepcopy(arc.empty_data_frame)
        t0 = time.time()
        try:
            print("Starting DAQ")
            while not self._stop_event.is_set():
                await self._handle_commands()
                while not self._pause_event.is_set():
                    await self._handle_commands()
                    await aio.sleep(0.1)  # Sleep a bit to avoid busy loop

    
                while (time.time()-t0) < self.sample_rate:
                    data = pd.concat([data, self.read_channels()], ignore_index=True)
                    await aio.sleep(0.001)
                    # to-do: force loop end if sample rate changes
                    
                data = data.mean(axis=0).to_frame().T
                if self.verbose:
                    print(data)

                arc.save_arc(data)
                t0 = time.time()
                
                
        except KeyboardInterrupt:
            print("Stopping DAQ")
            self.stop()
            cg.close(init_channel_functions=True)
        return

    async def start(self):
        if self.task is None or self.task.done():
            self._stop_event.clear()
            self._pause_event.set()
            self.task = aio.create_task(self.DAQ_run())
            
   
    async def _handle_commands(self):
        # Process all available commands without blocking
        while not self.command_queue.empty():
            command, args = await self.command_queue.get()
            if command == 'pause':
                self._pause_event.clear()
                print("DAQ paused.")
            elif command == 'resume':
                self._pause_event.set()
                print("DAQ resumed.")
            elif command == 'change_sampling':
                self.sample_rate = args.get('interval', self.sample_rate)
                print(f"Sampling interval changed to {self.sample_rate}s.")
            elif command == 'set_verbose':
                self.verbose = args.get('flag', self.verbose)
                print(f"Verbosity set to {self.verbose}.")
            elif command == 'stop':
                self._stop_event.set()
                self._pause_event.set()  # in case it's paused
                print("DAQ stopping...")        
        await aio.sleep(0.001)
    
    async def change_sampling_rate(self, interval):
        await self.command_queue.put(('change_sampling', {'interval': interval}))

    async def set_verbose(self, flag):
        await self.command_queue.put(('set_verbose', {'flag': flag}))

    async def pause(self):
        await self.command_queue.put(('pause',{}))
        
    async def resume(self):
        await self.command_queue.put(('resume',{}))
        
    async def stop(self):
        await self.command_queue.put(('stop',{}))
        if self.task:
            await self.task


    def __del__(self):
        return

if __name__ == '__main__':
    daq = ADR_DAQ()

    daq.DAQ_run()

    
    