# -*- coding: utf-8 -*-
"""
R&S ZNB(VNA) drop-in replacement for the KS_PNA-style VNA_control module.

Intended usage:
    import VNA_control.RS_ZNB as vn

Functions implemented to match your existing API:
    - vna_power_off()
    - init_vna_sweep(fstart, fstop, ifbw, printtime=True, avg=1)
    - start_vna_sweep(vna_power, turn_off_vna=True)
    - get_VNA_data(display_on=True)
    - init_VNA_noise(set_freq, ifbw, npoints, printtime=True)
    - find_resonators(R_diff, FREQ, db_thresh=3, closeness_thresh=1e5)

Notes:
    - The ZNB family controls RF output per physical port via SOURce:POWer<PhyPt>:STATe.
      We default to SOURCE_PORT=1 (typical for S21 with stimulus at port 1).
    - Data readback uses CALCulate:DATA:ALL? SDATa (complex) and CALCulate:DATA:STIMulus?
      for the stimulus axis (frequency for frequency sweeps).
"""

import time
import numpy as np
import pyvisa as pv


# -------------------------
# User-editable globals
# -------------------------
VNA_address = 'TCPIP0::192.168.0.100::hislip0::INSTR'
CHANNEL = 1
TRACE_NAME = "Trc1"
S_PARAM = "S21"

SOURCE_PORT = 1   # physical stimulus port for turning RF on/off
MAX_POINTS = int(1e5 + 1)


# -------------------------
# Initialize VISA + instrument (module-level, like your current file)
# -------------------------
rm = pv.ResourceManager()
vna = rm.open_resource(VNA_address)
vna.timeout = 10 * 1000  # ms

# Set binary float32 transfers; SWAP byte order often matches little-endian hosts.
# If you see nonsense values, try 'FORM:BORD NORM' or set is_big_endian=True in reads.
try:
    vna.write("FORM REAL,32")
    vna.write("FORM:BORD SWAP")
except Exception:
    # Some interfaces/firmware variants may not like these at import time; init_vna_sweep also sets them.
    pass

# Make sure RF is off initially
try:
    vna.write(f"SOUR{CHANNEL}:POW{SOURCE_PORT}:STAT OFF")
except Exception:
    # If the instrument is not ready yet, user will discover at first init; keep import non-fatal.
    pass


def vna_power_off():
    """Turns the VNA source output off (for SOURCE_PORT)."""
    vna.write(f"SOUR{CHANNEL}:POW{SOURCE_PORT}:STAT OFF")


def _safe_query_ascii(cmd: str, default=None):
    try:
        return vna.query_ascii_values(cmd)[0]
    except Exception:
        return default


def init_vna_sweep(fstart, fstop, ifbw, printtime=True, avg=1):
    """
    Configure a single-shot linear frequency sweep for S21 on an R&S ZNB.

    Parameters
    ----------
    fstart, fstop : float
        Sweep start/stop frequency in Hz.
    ifbw : float
        IF bandwidth in Hz (mapped to SENSe:BANDwidth:RESolution).
    printtime : bool
        Print estimated sweep time.
    avg : int
        If <=1: averaging OFF. If >1: enable averaging and set count.
    """

    # Cap points similar to your KS implementation
    npoints = (fstop - fstart) / ifbw
    if npoints > MAX_POINTS:
        npoints = MAX_POINTS
        ifbw = (fstop - fstart) / npoints
    npoints = int(max(2, round(npoints)))

    # Use binary float32 transfers
    vna.write("FORM REAL,32")
    vna.write("FORM:BORD SWAP")

    # Delete and recreate traces (keeps things deterministic)
    vna.write(f"CALC{CHANNEL}:PAR:DEL:ALL")
    vna.write(f"CALC{CHANNEL}:PAR:SDEF '{TRACE_NAME}','{S_PARAM}'")
    vna.write(f"CALC{CHANNEL}:PAR:SEL '{TRACE_NAME}'")

    # Turn off continuous sweeping; we will trigger single sweeps manually
    vna.write(f"INIT{CHANNEL}:CONT OFF")

    # Frequency sweep setup
    vna.write(f"SENS{CHANNEL}:SWE:TYPE LIN")
    vna.write(f"SENS{CHANNEL}:FREQ:STAR {fstart}")
    vna.write(f"SENS{CHANNEL}:FREQ:STOP {fstop}")
    vna.write(f"SENS{CHANNEL}:BAND:RES {ifbw}")
    vna.write(f"SENS{CHANNEL}:SWE:POIN {npoints}")

    # Minimum sweep time (auto, zero dwell)
    vna.write(f"SENS{CHANNEL}:SWE:TIME:AUTO ON")

    # Trigger configuration (immediate trigger source; we still explicitly INIT:IMM)
    vna.write(f"TRIG{CHANNEL}:SEQ:SOUR IMM")

    # Averaging
    if avg is None or avg <= 1:
        vna.write(f"SENS{CHANNEL}:AVER:STAT OFF")
    else:
        vna.write(f"SENS{CHANNEL}:AVER:STAT ON")
        vna.write(f"SENS{CHANNEL}:AVER:COUN {int(avg)}")
        # Clear averaging accumulator if supported (safe to ignore failures)
        try:
            vna.write(f"SENS{CHANNEL}:AVER:CLE")
        except Exception:
            pass

    # Estimate sweep time
    swptime = _safe_query_ascii(f"SENS{CHANNEL}:SWE:TIME?", default=None)
    if (swptime is not None) and printtime:
        print(f"Sweep should take roughly {round(swptime, 2)} seconds")

    # Ensure VISA timeout is comfortably above sweep time (timeout expects ms)
    if (swptime is not None) and (swptime * 1000 > vna.timeout):
        vna.timeout = int(2 * swptime * 1000)


def start_vna_sweep(vna_power, turn_off_vna=True):
    """
    Start a single sweep at the requested source power.

    Parameters
    ----------
    vna_power : float
        Source power in dBm.
    turn_off_vna : bool
        If True, turn RF off after sweep completes.
    """
    # Set power (applies to channel; ZNB can also do per-port power, but this is simplest)
    vna.write(f"SOUR{CHANNEL}:POW {float(vna_power)}")

    # RF on (per source port)
    vna.write(f"SOUR{CHANNEL}:POW{SOURCE_PORT}:STAT ON")

    # Trigger a single sweep and wait until finished
    # *OPC? blocks until operation complete (or timeout)
    vna.write(f"INIT{CHANNEL}:IMM")
    _ = vna.query("*OPC?")

    if turn_off_vna:
        vna.write(f"SOUR{CHANNEL}:POW{SOURCE_PORT}:STAT OFF")


def get_VNA_data(display_on=True):
    """
    Read complex S-parameter data + stimulus axis, returning:
        X, Y, R(dB), THETA(deg), FREQ(Hz)

    X,Y are I/Q (real/imag) of unformatted complex data.
    """
    # Data query:
    # - SDATa returns real/imag pairs (2 values per point)
    # - DATA:ALL? returns all traces; since we keep one trace, it’s the trace you want.
    try:
        raw = np.array(
            vna.query_binary_values(
                f"CALC{CHANNEL}:DATA:ALL? SDAT",
                datatype="f",
                container=list,
            ),
            dtype=float,
        )
    except pv.errors.VisaIOError as err:
        if getattr(err, "abbreviation", "") == "VI_ERROR_TMO":
            print(f"Timed out. Waiting for {vna.timeout/1000} seconds before trying again.")
            time.sleep(vna.timeout / 1000)
            raw = np.array(
                vna.query_binary_values(
                    f"CALC{CHANNEL}:DATA:ALL? SDAT",
                    datatype="f",
                    container=list,
                ),
                dtype=float,
            )
        else:
            raise

    # Interleaved real/imag
    X = raw[0::2]
    Y = raw[1::2]

    # Convert to magnitude (dB) and phase (deg)
    R = 20.0 * np.log10(np.sqrt(X**2 + Y**2))
    THETA = np.degrees(np.arctan2(Y, X))

    # Stimulus axis (frequency for frequency sweeps)
    FREQ = np.array(
        vna.query_binary_values(
            f"CALC{CHANNEL}:DATA:STIM?",
            datatype="f",
            container=list,
        ),
        dtype=float,
    )

    # Optionally show the trace on the VNA
    if display_on:
        try:
            vna.write("DISP:WIND1:STAT ON")
            vna.write(f"DISP:WIND1:TRAC1:FEED '{TRACE_NAME}'")
            # Autoscale if supported
            try:
                vna.write("DISP:WIND1:TRAC1:Y:SCAL:AUTO ONCE")
            except Exception:
                pass
        except Exception:
            # Don’t die if display commands differ by FW/config
            pass

    return X, Y, R, THETA, FREQ


def init_VNA_noise(set_freq, ifbw, npoints, printtime=True):
    """
    Configure a 'CW mode' style acquisition.

    This mirrors your older helper: fixed frequency, set IFBW, and use many points.
    Depending on your ZNB firmware/options, CW Mode sweeps may behave differently;
    if you prefer, switching to a Time sweep is another option.
    """

    vna.write("FORM REAL,32")
    vna.write("FORM:BORD SWAP")

    vna.write(f"CALC{CHANNEL}:PAR:DEL:ALL")
    vna.write(f"CALC{CHANNEL}:PAR:SDEF '{TRACE_NAME}','{S_PARAM}'")
    vna.write(f"CALC{CHANNEL}:PAR:SEL '{TRACE_NAME}'")

    # CW frequency set (works for CW Mode, Power, Time sweeps per manual)
    vna.write(f"FREQ:CW {float(set_freq)}")

    # Attempt to select CW Mode sweep type
    # (Some firmware uses 'CW' keyword; if yours complains, replace with the correct keyword for your unit.)
    try:
        vna.write(f"SENS{CHANNEL}:SWE:TYPE CW")
    except Exception:
        # Fall back: keep whatever sweep type is active; still uses fixed CW frequency above.
        pass

    vna.write(f"SENS{CHANNEL}:BAND:RES {float(ifbw)}")
    vna.write(f"SENS{CHANNEL}:SWE:POIN {int(npoints)}")
    vna.write(f"SENS{CHANNEL}:SWE:TIME:AUTO ON")
    vna.write(f"TRIG{CHANNEL}:SEQ:SOUR IMM")
    vna.write(f"INIT{CHANNEL}:CONT OFF")

    swptime = _safe_query_ascii(f"SENS{CHANNEL}:SWE:TIME?", default=None)
    if (swptime is not None) and printtime:
        print(f"Sweep should take roughly {round(swptime, 2)} seconds")
    if (swptime is not None) and (swptime * 1000 > vna.timeout):
        vna.timeout = int(2 * swptime * 1000)


def find_resonators(R_diff, FREQ, db_thresh=3, closeness_thresh=1e5):
    """
    Same helper you already have: pick peaks above threshold in second-diff magnitude,
    de-dupe by closeness_thresh keeping the largest peak in each cluster.
    """
    idx = R_diff > db_thresh
    R_temp = R_diff[idx]
    f_temp = FREQ[idx]

    if len(f_temp) == 0:
        print("No resonators found. Try again.")
        return np.array([])

    res_list = [f_temp[0]]
    res_amp = [R_temp[0]]
    for fidx, f in enumerate(f_temp[1:], start=1):
        if abs(f - res_list[-1]) >= closeness_thresh:
            res_list.append(f)
            res_amp.append(R_temp[fidx])
        elif R_temp[fidx] > res_amp[-1]:
            res_list[-1] = f
            res_amp[-1] = R_temp[fidx]

    return np.array(res_list)
