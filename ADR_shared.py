# -*- coding: utf-8 -*-
# ADR_shared.py
import asyncio as aio

# Single choke-point for all SIM900 serial traffic.
SIM_IO_LOCK = aio.Lock()
