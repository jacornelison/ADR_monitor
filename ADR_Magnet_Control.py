# -*- coding: utf-8 -*-
"""
Created on Tue Apr 29 09:58:22 2025

@author: detector-group
"""

import asyncio as aio


# WIP. Don't use this yet.
class ADR_MAG():
    def __init__(self):
        self.command_queue = aio.Queue() #Allow for command changes
        self._stop_event = aio.Event()
        self._pause_event = aio.Event()
        self._pause_event.set() # Initially not paused
        self.task = None
        self.data = None
        
        
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
