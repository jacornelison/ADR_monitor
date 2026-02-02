# -*- coding: utf-8 -*-
"""
Created on Tue Apr 29 09:58:22 2025

@author: detector-group
"""
# ADR_Magnet_Control.py
from __future__ import annotations

import asyncio as aio
import time
from dataclasses import dataclass
from ADR_shared import SIM_IO_LOCK


@dataclass
class MagTelemetry:
    t: float
    emf_v: float
    imag_raw: float
    magvolt_v: float


class ADRMagController:
    def __init__(
        self,
        daq,
        sim960,
        lead_resistance_ohm: float = 1.2,
        v_gain: float = 2.0,
        curr_sense_v_per_a: float = 1.0,
    ):
        """
        Parameters
        ----------
        daq:
            ADR_DAQ instance (must be running).
        sim960:
            SIM960 instance (from daq.adr_config.sim960).
        lead_resistance_ohm:
            Effective R between supply and magnet (used to convert I->V).
        v_gain:
            Kepco V = v_gain * SIM960 MOUT (your ADR_run uses 2).
        curr_sense_v_per_a:
            Convert DAQ's MagCurr channel to amps:
              I[A] = MagCurr_raw[V] / curr_sense_v_per_a
            Set to 1.0 if MagCurr is already in amps.
        """
        self.daq = daq
        self.sim960 = sim960
        self.Rlead = float(lead_resistance_ohm)
        self.v_gain = float(v_gain)
        self.curr_sense = float(curr_sense_v_per_a)
        self.sim_lock = SIM_IO_LOCK

    def _imag_amps(self, imag_raw: float) -> float:
        return imag_raw / self.curr_sense

    async def _set_kepco_voltage(self, v_kepco: float) -> None:
        """Write to SIM960 under the shared SIM I/O lock."""
        v960 = v_kepco / self.v_gain
        async with self.sim_lock:
            await aio.to_thread(self.sim960.set_MOUT, v960)

    async def _get_telem(self, timeout: float = 2.0) -> MagTelemetry:
        d = await self.daq.wait_mag(timeout=timeout)
        return MagTelemetry(
            t=float(d["Time"]),
            emf_v=float(d["EMF"]),
            imag_raw=float(d["MagCurr"]),
            magvolt_v=float(d["MagVolt"]),
        )

    async def ramp_current_feedback(
        self,
        target_I_A: float,
        ramp_rate_A_per_s: float = 5.6e-3,
        dt_s: float = 0.25,
        emf_limit_V: float = 0.15,
        I_tol_A: float = 0.02,
        timeout_s: float = 10.0,
    ) -> None:
        """
        Ramp toward target current using measured current and EMF.
        EMF is used as a “stress gauge”: if |EMF| is too large, pause/slow.

        This is intentionally conservative and simple.
        """
        t_start = time.time()

        # Prime telemetry
        telem = await self._get_telem()
        I_now = self._imag_amps(telem.imag_raw)

        # The “desired current” we advance each step (bounded by ramp_rate)
        I_cmd = I_now
        direction = 1.0 if target_I_A > I_now else -1.0

        while True:
            if (time.time() - t_start) > timeout_s:
                raise TimeoutError("ramp_current_feedback timed out.")

            telem = await self._get_telem()
            I_now = self._imag_amps(telem.imag_raw)
            emf = telem.emf_v

            # Done?
            if abs(I_now - target_I_A) <= I_tol_A:
                # Set final setpoint based on measured current (small cleanup step)
                v_kepco = target_I_A * self.Rlead
                await self._set_kepco_voltage(v_kepco)
                return

            # If EMF is high, hold (or you could reduce I_cmd slightly)
            if abs(emf) > emf_limit_V:
                # hold voltage based on present current (don’t push harder)
                v_kepco = I_now * self.Rlead
                await self._set_kepco_voltage(v_kepco)
                await aio.sleep(dt_s)
                continue

            # Advance commanded current at a safe rate
            I_cmd += direction * ramp_rate_A_per_s * dt_s

            # Don’t step past the final target
            if direction > 0:
                I_cmd = min(I_cmd, target_I_A)
            else:
                I_cmd = max(I_cmd, target_I_A)

            # Convert desired current to supply voltage (simple Ohm’s law model)
            # (You can later add compensation using magvolt_v/emf if you want.)
            v_kepco = I_cmd * self.Rlead
            await self._set_kepco_voltage(v_kepco)

            await aio.sleep(dt_s)