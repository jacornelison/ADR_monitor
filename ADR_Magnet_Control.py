# -*- coding: utf-8 -*-
"""
ADR_Magnet_Control.py

Magnet controller that:
- ramps based on measured current and EMF (from DAQ telemetry fed by SIM970)
- writes Kepco setpoint via SIM960 MOUT
- optionally verifies each command using:
    (1) SIM960 OMON (instrument-level verify)
    (2) SIM970 MagVolt and MagCurr response (physical verify)

Python 3.9 compatible.
"""

import asyncio as aio
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any
import warnings
from ADR_shared import SIM_IO_LOCK


@dataclass
class MagTelemetry:
    t: float
    emf_v: float
    imag_raw: float     # DAQ "MagCurr" (in amps, per your note)
    magvolt_v: float


class ADRMagController:
    def __init__(
        self,
        daq,
        sim960,
        hs,
        lead_resistance_ohm: float = 1.2,
        v_gain: float = 2.0,
        curr_sense_v_per_a: float = 1.0,
        telem_timeout_default_s: float = 5.0,
    ):
        """
        Parameters
        ----------
        daq:
            ADR_DAQ instance (must be running). Controller consumes DAQ magnet telemetry.
        sim960:
            SIM960 instance (typically daq.adr_config.sim960).
        hs:
            ADR heat switch controller instance. Needs hs.open() and hs.close() functions to work.
        lead_resistance_ohm:
            Effective series resistance (used for simple I->V mapping: V_kepco = I_cmd * Rlead).
        v_gain:
            Kepco V = v_gain * SIM960 MOUT.
        curr_sense_v_per_a:
            If DAQ MagCurr is already in amps, leave at 1.0.
            Otherwise I[A] = MagCurr_raw / curr_sense_v_per_a.
        telem_timeout_default_s:
            Default timeout when waiting for the next DAQ telemetry update.
        """
        self.daq = daq
        self.sim960 = sim960
        self.hs = hs
        self.Rlead = float(lead_resistance_ohm)
        self.v_gain = float(v_gain)
        self.curr_sense = float(curr_sense_v_per_a)

        self.sim_lock = SIM_IO_LOCK
        self.telem_timeout_default_s = float(telem_timeout_default_s)
        
        self.mag_max_current = 9.0 # in Amps
    
        # Event helpers
        self._abort_event = aio.Event()
        self._pause_event = aio.Event()
        self._pause_event.set()  # not paused initially
        
        
    def _imag_amps(self, imag_raw: float) -> float:
        return imag_raw / self.curr_sense

    def _telem_timeout_s_default(self) -> float:
        return self.telem_timeout_default_s

    async def _get_telem(self, timeout: Optional[float] = None) -> MagTelemetry:
        """
        Get the next telemetry update from DAQ.
        DAQ is the only reader of SIM970; controller consumes DAQ-published values.
        """
        if timeout is None:
            timeout = self._telem_timeout_s_default()

        d = await self.daq.wait_mag(timeout=timeout)
        return MagTelemetry(
            t=float(d.get("Time", float("nan"))),
            emf_v=float(d.get("EMF", float("nan"))),
            imag_raw=float(d.get("MagCurr", float("nan"))),
            magvolt_v=float(d.get("MagVolt", float("nan"))),
        )



    async def _verify_physical_response(
        self,
        v960_cmd: float,
        expected_dir: Optional[int],
        I0_A: float,
        V0_V: float,
        updates: int = 4,
        timeout_s: float = 6.0,
        min_dmagvolt_V: float = 5e-4,
        min_dimag_A: float = 1e-3,
    ) -> Dict[str, Any]:
        """
        Verify that the physical system responded after a voltage command.

        We determine expected direction from sign(v960_cmd).
        Over the next `updates` telemetry samples (or until timeout), look for:
          ΔMagVolt in expected direction beyond min_dmagvolt_V
          ΔMagCurr in expected direction beyond min_dimag_A

        Returns a diagnostics dict.
        """
        t_start = time.time()

        expected = 0 if expected_dir is None else int(expected_dir)
        dir_check = (expected != 0)
        

        I1_A = I0_A
        V1_V = V0_V

        saw_I = False
        saw_V = False
        dI_best = 0.0
        dV_best = 0.0

        for _ in range(max(1, updates)):
            remaining = max(0.0, timeout_s - (time.time() - t_start))
            if remaining <= 0:
                break

            try:
                telem = await self._get_telem(timeout=min(self._telem_timeout_s_default(), remaining))
            except aio.TimeoutError:
                break

            I1_A = self._imag_amps(telem.imag_raw)
            V1_V = float(telem.magvolt_v)

            dI = I1_A - I0_A
            dV = V1_V - V0_V

            if abs(dI) > abs(dI_best):
                dI_best = float(dI)
            if abs(dV) > abs(dV_best):
                dV_best = float(dV)

            if dir_check:
                if abs(dI) >= min_dimag_A and (dI * expected) > 0:
                    saw_I = True
                if abs(dV) >= min_dmagvolt_V and (dV * expected) > 0:
                    saw_V = True
            else:
                # Direction ambiguous near zero command: accept any movement above thresholds
                if abs(dI) >= min_dimag_A:
                    saw_I = True
                if abs(dV) >= min_dmagvolt_V:
                    saw_V = True

            if saw_I or saw_V:
                break

        phys_ok_any = bool(saw_I or saw_V)
        phys_ok_both = bool(saw_I and saw_V)

        return {
            "expected_dir": expected,     # +1, -1, or 0
            "I1_A": float(I1_A),
            "V1_V": float(V1_V),
            "dI_A_best": float(dI_best),
            "dV_V_best": float(dV_best),
            "phys_ok_I": bool(saw_I),
            "phys_ok_V": bool(saw_V),
            "phys_ok_any": phys_ok_any,
            "phys_ok_both": phys_ok_both,
        }
    
    
    async def _set_kepco_voltage(
        self,
        v_kepco: float,
        verify_sim960: bool = False,
        verify_mout: bool = True,
        mout_tol_V: float = 0.002,        # tighter setpoint tolerance
        omon_tol_V: float = 0.03,         # looser monitor tolerance
        sim960_delay_s: float = 0.25,
        sim960_attempts: int = 3,
        verify_physical: bool = False,
        phys_timeout_s: float = 10.0,
        phys_updates: int = 4,
        min_dmagvolt_V: float = 5e-4,
        min_dimag_A: float = 1e-3,
        expected_dir: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Set Kepco voltage via SIM960 MOUT, with optional verification:
          - SIM960 verify: verify MOUT (tight) and OMON (looser) against command
          - Physical verify: confirm SIM970 MagVolt and/or MagCurr respond as expected
    
        Returns a dict of diagnostic information (useful for logging/troubleshooting).
        """
        diag: Dict[str, Any] = {}
    
        v960_cmd = v_kepco / self.v_gain
        diag["v_kepco_cmd"] = float(v_kepco)
        diag["v960_cmd"] = float(v960_cmd)
    
        # Baseline telemetry (outside SIM lock)
        baseline = None
        if verify_physical:
            baseline = await self._get_telem(timeout=max(2.0, self._telem_timeout_s_default()))
            I0 = self._imag_amps(baseline.imag_raw)
            V0 = float(baseline.magvolt_v)
            E0 = float(baseline.emf_v)
            diag.update({"I0_A": I0, "MagVolt0_V": V0, "EMF0_V": E0})
    
        # -------------------- Write MOUT (I/O under lock) --------------------
        async with self.sim_lock:
            await aio.to_thread(self.sim960.set_MOUT, v960_cmd)
    
        # -------------------- Optional SIM960 verify --------------------
        if verify_sim960:
            # 1) Verify MOUT (setpoint) quickly and tightly
            last_mout = None
            mout_ok = False
            for _ in range(max(1, sim960_attempts)):
                await aio.sleep(sim960_delay_s)
    
                async with self.sim_lock:
                    last_mout = await aio.to_thread(self.sim960.get_MOUT)
    
                if last_mout is not None and abs(last_mout - v960_cmd) <= mout_tol_V:
                    mout_ok = True
                    break
    
            diag["MOUT_V"] = None if last_mout is None else float(last_mout)
            diag["mout_ok"] = bool(mout_ok)
    
            if verify_mout and not mout_ok:
                raise RuntimeError(
                    "SIM960 MOUT verify failed: cmd={:.4f} V, MOUT={}".format(v960_cmd, last_mout)
                )
    
            # 2) Verify OMON (output monitor) with more settling slack
            last_omon = None
            omon_ok = False
            for _ in range(max(1, sim960_attempts + 2)):  # give OMON a bit longer
                await aio.sleep(sim960_delay_s)
    
                async with self.sim_lock:
                    last_omon = await aio.to_thread(self.sim960.get_OMON)
    
                if last_omon is not None and abs(last_omon - v960_cmd) <= omon_tol_V:
                    omon_ok = True
                    break
    
            diag["OMON_V"] = None if last_omon is None else float(last_omon)
            diag["omon_ok"] = bool(omon_ok)
    
            if not omon_ok:
                raise RuntimeError(
                    "SIM960 OMON verify failed (may be settling): cmd={:.4f} V, OMON={}".format(v960_cmd, last_omon)
                )
        else:
            diag["mout_ok"] = None
            diag["omon_ok"] = None
    
        # -------------------- Optional physical verify (outside lock) --------------------
        if verify_physical and baseline is not None:
            phys = await self._verify_physical_response(
                v960_cmd=v960_cmd,
                expected_dir = expected_dir,
                I0_A=float(diag["I0_A"]),
                V0_V=float(diag["MagVolt0_V"]),
                updates=phys_updates,
                timeout_s=phys_timeout_s,
                min_dmagvolt_V=min_dmagvolt_V,
                min_dimag_A=min_dimag_A,
            )
            diag.update(phys)
    
            if not phys["phys_ok_any"]:
                raise RuntimeError(
                    "Physical verify failed: no expected response in MagVolt or MagCurr. "
                    "Details: {}".format(
                        {k: phys[k] for k in phys if k.startswith(("dI", "dV", "phys_", "I1", "V1", "expected_"))}
                    )
                )
    
        return diag
    
    def _clamp_mag_current(self, input_I: float) -> float:
        """
        Clamp requested magnet current to [0, self.mag_max_current].
    
        Uses warnings.warn to notify when clamping occurs.
        """
        if input_I < 0:
            warnings.warn(
                f"Requested current {input_I:.6g} A is negative; clamping to 0 A.",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return 0.0
    
        max_I = getattr(self, "mag_max_current", None)
        if max_I is None:
            # If no max is configured, don't clamp high values.
            return float(input_I)
    
        if input_I > max_I:
            warnings.warn(
                f"Requested current {input_I:.6g} A exceeds max current {max_I:.6g} A; "
                f"clamping to {max_I:.6g} A.",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return float(max_I)
    
        return float(input_I)

    async def ramp_current_feedback(
        self,
        target_I_A: float,
        ramp_rate_A_per_s: float = 0.005,
        emf_limit_up_V: float = 0.240,
        emf_limit_down_V: float = 0.120,
        I_tol_A: float = 0.02,
        timeout_s: Optional[float] = None,
        timeout_margin: float = 10,
        timeout_overhead_s: float = 10.0,
        telem_timeout_s: Optional[float] = None,
        verify_every: int = 20,
        # Safety clamps
        v_kepco_max: Optional[float] = 10.0,   # if None, no explicit clamp besides >=0
        do_verbose: bool = False,
    ) -> None:
        """
        Ramp magnet current toward target_I_A using DAQ telemetry as the clock.
    
        Key design choice:
          - Control variable is Kepco voltage command (V_cmd), clamped to [0, v_kepco_max].
          - Ramp-up: increase V_cmd
          - Ramp-down: decrease V_cmd (toward 0 V), since negative voltage is disallowed.
    
        Ramp speed:
          - ramp_rate_A_per_s is the user-requested speed in A/s.
          - EMF limits are enforced as HARD limits on the voltage-step rate (conservative).
            This prevents "too aggressive" changes even if ramp_rate is high.
    
        Notes:
          - This is still not a true current servo (no PI loop), but it is stable and safe for
            monotonic ramping in a no-negative-voltage system.
          - If your wiring/system has significant series resistance uncertainty, a PI loop is the
            next upgrade.
        """
        # Basic checks
        if (target_I_A < 0) or (hasattr(self, "mag_max_current") and target_I_A > self.mag_max_current):
            max_I = getattr(self, "mag_max_current", None)
            if max_I is None:
                raise ValueError("Target current is invalid (negative).")
            raise ValueError(
                f"Target current: {target_I_A} A is invalid.\n"
                f"Target current must be between 0 and {max_I:.2f} A."
            )
    
        if ramp_rate_A_per_s <= 0:
            raise ValueError("ramp_rate_A_per_s must be > 0")
    
        if telem_timeout_s is None:
            telem_timeout_s = self._telem_timeout_s_default()
    
        # Initial telemetry sample
        try:
            telem0 = await self._get_telem(timeout=telem_timeout_s)
        except aio.TimeoutError:
            raise TimeoutError("No magnet telemetry from DAQ (initial wait timed out).")
    
        I_now = self._imag_amps(telem0.imag_raw)
        direction = 1.0 if target_I_A > I_now else -1.0  # +1 mag-up, -1 mag-down
        #print(direction)
        
        # Manual EMF limits as hard limits
        emf_limit = float(emf_limit_up_V) if direction > 0 else float(emf_limit_down_V)
    
        # Compute a reasonable overall timeout if not provided
        if timeout_s is None:
            expected = abs(target_I_A - I_now) / ramp_rate_A_per_s
            timeout_s = expected * timeout_margin + timeout_overhead_s
    
        t_start = time.time()
        last_update_t = time.time()
        step_idx = 0
    
        # ---- State: commanded Kepco voltage (physical volts) ----
        # Initialize V_cmd from current state estimate:
        # - For mag-up: start supporting the present current (so we don't jump)
        # - For mag-down: start at the present support level, but we will step downward
        # We estimate present support using Rlead; it's imperfect but avoids a large initial discontinuity.
        async with self.sim_lock:
            omon = await aio.to_thread(self.sim960.get_OMON)
        V_cmd = max(0.0, float(omon) * self.v_gain)
        
        if do_verbose:
            print(f"Starting V_cmd: {V_cmd:0.3f}")
    
        # Apply optional max clamp
        if v_kepco_max is not None:
            V_cmd = min(V_cmd, float(v_kepco_max))
    
        # Command initial V_cmd (optional: can skip if already close)
        # Keep verify off here to avoid spamming verifies at entry.
        await self._set_kepco_voltage(V_cmd, verify_sim960=False, verify_physical=False)
        
        if do_verbose:
            print(f"Starting V_cmd (after clamping): {V_cmd:0.3f}")
        
        stop_flag = False
        while True:
            
            if (time.time() - t_start) > timeout_s:
                raise TimeoutError("ramp_current_feedback timed out (overall ramp deadline).")
            
            await self._check_abort_pause()
            
            # Telemetry update = one control step
            try:
                telem = await self._get_telem(timeout=telem_timeout_s)
            except aio.TimeoutError:
                raise TimeoutError("No magnet telemetry from DAQ (per-step wait timed out).")
    
            now_t = time.time()
            dt = max(0.0, now_t - last_update_t)
            last_update_t = now_t
    
            I_now = self._imag_amps(telem.imag_raw)
            emf = float(telem.emf_v)
    
            # ------------------- Compute requested voltage step -------------------
            # User-requested current change (A) over this dt
            dI_req = ramp_rate_A_per_s * dt
            #min_dimag_A = dI_req * 0.05
            # Convert requested dI to a requested dV using Rlead estimate
            dV_req = dI_req * self.Rlead
            #min_dmagvolt_V = dV_req * 0.05
    
            # Hard limit dV by EMF constraint (conservative "speed limiter")
            # This ties command slew to the manual EMF bounds.
            dV_emf_max = emf_limit * dt
    
            # Choose actual dV magnitude (always positive), limited by both
            dV = min(dV_req, dV_emf_max)
    
            # If EMF is already above limit, stop moving voltage in the risky direction.
            # For mag-up: do not increase voltage
            # For mag-down: do not decrease voltage (hold)
            if abs(emf) > emf_limit:
                dV = 0.0
            
    
            # Apply direction: + up increases voltage, - down decreases voltage
            if direction < 0:
                dV = -1*dV
            
            # Step the command voltage.
            V_cmd = V_cmd + dV
            
            # Reasons to stop:
            if abs(I_now - target_I_A) <= I_tol_A:
                # Reset V_cmd
                V_cmd = V_cmd - dV
                stop_flag = True
                stop_reason = "Ramp Complete."
            
            elif V_cmd < 0.0:
                V_cmd = 0.0
                stop_flag = True
                stop_reason = "Command voltage below zero. Clamping to zero."
                
            elif v_kepco_max is not None and V_cmd > float(v_kepco_max):
                V_cmd = float(v_kepco_max)
                stop_flag = True
                stop_reason = "Command voltage ({V_cmd:0.2f}) above output max ({v_kepco_max}). Clamping to ({v_kepco_max}) V."
                
    
            # Optional verification cadence
            verify_now = (step_idx == 0) or (verify_every > 0 and (step_idx % verify_every == 0))
            
            if do_verbose and verify_now:
                print(f"dI: {dI_req:0.3f} | dV_req: {dV_req:0.3f} | V_cmd: {V_cmd:0.3f} | Ramp Index: {step_idx}")
            
            close_to_target = abs(target_I_A - I_now) < 0.25  # tune
            
            await self._set_kepco_voltage(
                V_cmd,
                verify_sim960=verify_now,
                verify_physical=(verify_now and (not close_to_target)),
                phys_updates=4,
                phys_timeout_s=6.0,
                min_dmagvolt_V=1e-4,
                min_dimag_A=3e-4,
                expected_dir = +1 if direction > 0 else -1,
            )
            
            step_idx += 1
            
            if stop_flag:
                print("Stopping ramp.")
                print(f"Reason: {stop_reason}")
                return
        return
             
    async def ramp_to_zero(
        self,
        ramp_rate_A_per_s: float = 0.005,
        emf_limit_up_V: float = 0.25,
        emf_limit_down_V: float = 0.125,
        I_tol_A: float = 0.02,
        timeout_s: Optional[float] = None,
        timeout_margin: float = 1.5,
        timeout_overhead_s: float = 10.0,
        telem_timeout_s: Optional[float] = None,
        verify_every: int = 20,
    ) -> None:
        """
        Convenience wrapper to ramp magnet current to ~0 A using the same feedback logic.
        """
        await self.ramp_current_feedback(
            target_I_A=0.0,
            ramp_rate_A_per_s=ramp_rate_A_per_s,
            emf_limit_up_V=emf_limit_up_V,
            emf_limit_down_V=emf_limit_down_V,
            I_tol_A=I_tol_A,
            timeout_s=timeout_s,
            timeout_margin=timeout_margin,
            timeout_overhead_s=timeout_overhead_s,
            telem_timeout_s=telem_timeout_s,
            verify_every=verify_every,
        )
        
        

    async def do_mag_cycle(
        self,
        magup_time=30,
        magsoak_time=60,
        magdown_time=60,
        is_first_cycle=False,
        final_max_current=9.0,
        emf_limit_up_V=0.25,
        emf_limit_down_V=0.12,
    ):
        """
        Times are in minutes.
        """
        try:
            # Validate
            if magup_time <= 0 or magdown_time <= 0 or magsoak_time < 0:
                raise ValueError("Times must be positive (soak can be 0).")
        
            if hasattr(self, "mag_max_current") and final_max_current > self.mag_max_current:
                raise ValueError(
                    f"final_max_current={final_max_current} exceeds mag_max_current={self.mag_max_current}"
                )
        
            # Convert to A/s (minutes -> seconds)
            ramp_rate_up = float(final_max_current) / (magup_time * 60.0)
            ramp_rate_down = float(final_max_current) / (magdown_time * 60.0)
        
            if is_first_cycle:
                # Ensure heat switch closed (and optionally "reset" it)
                self.hs.SwitchOpen()
                self.hs.SwitchClose()
            
            comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Mag Up at:\n{comp_time}")
            
            # Mag up
            await self.ramp_current_feedback(
                target_I_A=float(final_max_current),
                ramp_rate_A_per_s=ramp_rate_up,
                emf_limit_up_V=emf_limit_up_V,
                emf_limit_down_V=emf_limit_down_V,
                timeout_s=None,
            )
        
            # Reset heat switch after mag-up (if this is intentional)
            self.hs.SwitchOpen()
            self.hs.SwitchClose()
        
            comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Mag Up completed at:\n{comp_time}")
            print(f"Soaking for {magsoak_time} minutes.")
        
            # Soak
            soak_s = magsoak_time * 60.0
            t0 = time.time()
            while (time.time() - t0) < soak_s:
                await self._check_abort_pause()
                await aio.sleep(1.0)  # check once per second
        
            # Open heat switch for demag (if this matches your procedure)
            self.hs.SwitchOpen()
        
            # Mag down to zero (no negative voltage allowed, so ramp function should handle this properly)
            await self.ramp_current_feedback(
                target_I_A=0.0,
                ramp_rate_A_per_s=ramp_rate_down,
                emf_limit_up_V=emf_limit_up_V,
                emf_limit_down_V=emf_limit_down_V,
                timeout_s=None,
            )
        
            comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Mag Down completed at:\n{comp_time}")
            
        except aio.CancelledError:
            # Best-effort safe state
            await self.abort(set_voltage_zero=False)
            print("Mag cycle aborted.")
            raise
        
        except Exception as e:
            # ---- report immediately ----
            print("\n[do_mag_cycle] ERROR:", repr(e), flush=True)
            raise
                
    def clear_abort(self) -> None:
        """Clear abort flag so future operations can run."""
        self._abort_event.clear()
    
    async def abort(self, set_voltage_zero: bool = False) -> None:
        """
        Abort any ongoing operation (ramp/soak/cycle).
        Safe action: command 0 V output (no negative voltage).
        """
        self._abort_event.set()
        if set_voltage_zero:
            # Best-effort: don't hang forever during an abort
            try:
                await self.ramp_current_feedback(
                    target_I_A=0.0,
                    ramp_rate_A_per_s=9 / 1800,
                    emf_limit_up_V= 0.25,
                    emf_limit_down_V=0.125,
                    timeout_s=None,
                    timeout_margin=10,
                )
            except Exception:
                pass
    
    def is_aborted(self) -> bool:
        return self._abort_event.is_set()
    
    async def pause(self) -> None:
        self._pause_event.clear()
    
    async def resume(self) -> None:
        self._pause_event.set()
    
    async def _check_abort_pause(self) -> None:
        """Call this inside loops."""
        if self._abort_event.is_set():
            raise aio.CancelledError("Operation aborted.")
        while not self._pause_event.is_set():
            if self._abort_event.is_set():
                raise aio.CancelledError("Operation aborted.")
            await aio.sleep(0.1)