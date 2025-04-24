# -*- coding: utf-8 -*-
"""
Created on Sun Jul  3 18:10:49 2022

@author: detector-group
"""
# -*- coding: utf-8 -*-
"""
Created on Mon May 10 14:47:40 2021
​
@author: svc_csi359876
"""

import time
from pyvisa.resources.serial import SerialInstrument

from qcodes.instrument import (
    Instrument,
    VisaInstrument,
    ManualParameter,
    MultiParameter,
    InstrumentChannel,
    InstrumentModule
)

# Base class
class SIM9XX(VisaInstrument):

    """
    Initializes connection to the SIM900 main frame
    """

    # all instrument constructors should accept **kwargs and pass them on to
    # super().__init__
    def __init__(self, name, address, **kwargs):
        # supplying the terminator means you don't need to remove it from every response
        super().__init__(name, address, terminator='\n', **kwargs)

        assert isinstance(self.visa_handle, SerialInstrument)

        self.visa_handle.baud_rate = 115200
        self.visa_handle.write('TERM LF') # Set terminator

        # it's a good idea to call connect_message at the end of your constructor.
        # this calls the 'IDN' parameter that the base Instrument class creates for
        # every instrument (you can override the `get_idn` method if it doesn't work
        # in the standard VISA form for your instrument) which serves two purposes:
        # 1) verifies that you are connected to the instrument
        # 2) gets the ID info so it will be included with metadata snapshots later.
        self.connect_message()

    # Generic function to read a port/module
    def read_port(self, port):
        self.visa_handle.write(f'NINP? {port}')
        time.sleep(0.05)
        nbytes = self.visa_handle.read()
        # print(nbytes.encode())
        try:
            n = int(nbytes.strip())
            if n > 0:
                self.visa_handle.write(f'RAWN? {port},{n}')
                time.sleep(0.05)
                msg = self.visa_handle.read()
                return msg
        except:
            return None

    def idn_port(self, port):
        # self.visa_handle.write('FLSH {port}')
        # time.sleep(0.1)
        self.visa_handle.write(f'SNDT {port},"*IDN?"')
        time.sleep(0.1)
        idn = self.read_port(port)
        print(idn)
        return idn

    def get_TERM(self, port='D'): # D is host
        self.visa_handle.write(f'TERM? {port}')
        time.sleep(0.05)
        g = self.visa_handle.read()
        return g



# Main frame
# Make sure baud rate is set correctly for the COM port
SIM900 = SIM9XX(name='SIM900', address='ASRL7::INSTR')

# SIM 921
# !!! In stream mode, only one module can be connected at a time !!!
class SIM921_stream(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM921', port=1, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        SIM900.visa_handle.write(f"CONN {self.port},'AAA'") # AAA is arbitrary escape string
        self.idn()

    def idn(self):
        SIM900.visa_handle.write("*IDN?")
        idn = SIM900.visa_handle.read()
        print(idn)

    def close(self):
        SIM900.visa_handle.write('AAA')

# SIM 960
# PCTL(?) z -- Proportional action ON/OFF
# ICTL(?) z -- Integral action ON/OFF
# DCTL(?) z -- Derivative action ON/OFF
# OCTL(?) z -- Offset ON/OFF
# GAIN(?) {f } -- Proportional Gain
# APOL(?) z -- Controller Polarity
# INTG(?) {f } -- Integral Gain
# DERV(?) {f } -- Derivative Gain
# OFST(?) {f } -- Output Offset

class SIM960_stream(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM960', port=3, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        SIM900.visa_handle.write(f"CONN {self.port},'CCC'") # CCC is arbitrary escape string
        self.idn()

        self.add_parameter('GAIN',
                            set_cmd='GAIN {:f}',
                            get_cmd='GAIN?',
                            get_parser=float)

    def idn(self):
        SIM900.visa_handle.write("*IDN?")
        idn = SIM900.visa_handle.read()
        print(idn)

    def close(self):
        SIM900.visa_handle.write('CCC')


# SIM960, text based
class SIM960(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM960', port=3, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        # SIM900.visa_handle.write(f"CONN {self.port},'CCC'") # CCC is arbitrary escape string
        SIM900.visa_handle.write(f'TERM {self.port},LF')
        SIM900.visa_handle.write(f'FLSH {self.port}')
        SIM900.idn_port(self.port)

    # def read(self):
    #     SIM900.visa_handle.write(f'NINP? {self.port}')
    #     # time.sleep(0.1)
    #     nbytes = SIM900.visa_handle.read()
    #     # print(nbytes.encode())
    #     try:
    #         n = int(nbytes.strip())
    #         if n > 0:
    #             SIM900.visa_handle.write(f'RAWN? {self.port},{n}')
    #             # time.sleep(0.1)
    #             msg = SIM900.visa_handle.read()
    #             return msg
    #     except:
    #         return None

    # def idn(self):
    #     # SIM900.visa_handle.write('FLSH {self.port}')
    #     # time.sleep(0.1)
    #     SIM900.visa_handle.write(f'SNDT {self.port},"*IDN?"')
    #     time.sleep(0.1)
    #     idn = self.read()
    #     print(idn)
    #     return idn

    def get_GAIN(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"GAIN?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_GAIN(self, GAIN):
        SIM900.visa_handle.write(f'SNDT {self.port},"GAIN {GAIN:g}"')
        time.sleep(0.1)

    def get_INTG(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"INTG?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_INTG(self, INTG):
        SIM900.visa_handle.write(f'SNDT {self.port},"INTG {INTG:g}"')
        time.sleep(0.1)

    def get_DERV(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"DERV?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_DERV(self, DERV):
        SIM900.visa_handle.write(f'SNDT {self.port},"DERV {DERV:g}"')
        time.sleep(0.1)

    def get_AMAN(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"AMAN?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_AMAN(self, AMAN):
        SIM900.visa_handle.write(f'SNDT {self.port},"AMAN {AMAN}"')
        time.sleep(0.1)
        
    def get_PCTL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"PCTL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_PCTL(self, PCTL):
        SIM900.visa_handle.write(f'SNDT {self.port},"PCTL {PCTL}"')
        time.sleep(0.1)
        
    def get_ICTL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"ICTL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_ICTL(self, ICTL):
        SIM900.visa_handle.write(f'SNDT {self.port},"ICTL {ICTL}"')
        time.sleep(0.1)

    def get_DCTL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"DCTL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_DCTL(self, DCTL):
        SIM900.visa_handle.write(f'SNDT {self.port},"DCTL {DCTL}"')
        time.sleep(0.1)  
    def get_OCTL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"OCTL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_OCTL(self, OCTL):
        SIM900.visa_handle.write(f'SNDT {self.port},"OCTL {OCTL}"')
        time.sleep(0.1)

    def get_RAMP(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"RAMP?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_RAMP(self, RAMP):
        SIM900.visa_handle.write(f'SNDT {self.port},"RAMP {RAMP}"')
        time.sleep(0.1)

    def get_INPT(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"INPT?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_INPT(self, INPT):
        SIM900.visa_handle.write(f'SNDT {self.port},"INPT {INPT}"')
        time.sleep(0.1)

    def get_SETP(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"SETP?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_SETP(self, SETP):
        SIM900.visa_handle.write(f'SNDT {self.port},"SETP {SETP:g}"')
        time.sleep(0.1)

    def get_MOUT(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"MOUT?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_MOUT(self, MOUT):
        SIM900.visa_handle.write(f'SNDT {self.port},"MOUT {MOUT:g}"')
        time.sleep(0.1)

    def get_OMON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"OMON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_SMON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"SMON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_MMON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"MMON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_EMON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"EMON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_ULIM(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"ULIM?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_ULIM(self, ULIM):
        SIM900.visa_handle.write(f'SNDT {self.port},"ULIM {ULIM:g}"')
        time.sleep(0.1)

    def get_LLIM(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"LLIM?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_LLIM(self, LLIM):
        SIM900.visa_handle.write(f'SNDT {self.port},"LLIM {LLIM:g}"')
        time.sleep(0.1)

# SIM921, text based
class SIM921(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM921', port=1, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        # SIM900.visa_handle.write(f"CONN {self.port},'CCC'") # CCC is arbitrary escape string
        SIM900.visa_handle.write(f'TERM {self.port},LF')
        SIM900.visa_handle.write(f'FLSH {self.port}')
        SIM900.idn_port(self.port)

    def get_FREQ(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"FREQ?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def set_FREQ(self, FREQ):
        SIM900.visa_handle.write(f'SNDT {self.port},"FREQ {FREQ:g}"')
        time.sleep(0.1)

    def get_RANG(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"RANG?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_RANG(self, RANG):
        SIM900.visa_handle.write(f'SNDT {self.port},"RANG {RANG:d}"')
        time.sleep(0.1)

    def get_EXCI(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXCI?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_EXCI(self, EXCI):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXCI {EXCI:d}"')
        time.sleep(0.1)

    def get_CURV(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"CURV?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_CURV(self, CURV):
        SIM900.visa_handle.write(f'SNDT {self.port},"CURV {CURV:d}"')
        time.sleep(0.1)

    def get_EXON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_EXON(self, EXON):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXON {EXON}"')
        time.sleep(0.1)

    def get_MODE(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"MODE?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_MODE(self, MODE):
        SIM900.visa_handle.write(f'SNDT {self.port},"MODE {MODE}"')
        time.sleep(0.1)

    def get_IEXC(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"IEXC?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_VEXC(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"VEXC?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_RVAL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"RVAL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_TVAL(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"TVAL?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_PHAS(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"PHAS?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return float(g.strip())

    def get_DISP(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"DISP?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_DISP(self, DISP):
        SIM900.visa_handle.write(f'SNDT {self.port},"DISP {DISP:d}"')
        time.sleep(0.1)

    def get_AGAI(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"AGAI?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_AGAI(self, AGAI):
        SIM900.visa_handle.write(f'SNDT {self.port},"AGAI {AGAI}"')
        time.sleep(0.1)

    def get_ADIS(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"ADIS?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_ADIS(self, ADIS):
        SIM900.visa_handle.write(f'SNDT {self.port},"ADIS {ADIS}"')
        time.sleep(0.1)

    def get_TCON(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"TCON?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_TCON(self, TCON):
        SIM900.visa_handle.write(f'SNDT {self.port},"TCON {TCON:d}"')
        time.sleep(0.1)

# SIM922, text based
class SIM922(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM922', port=5, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        SIM900.visa_handle.write(f'TERM {self.port},LF')
        SIM900.visa_handle.write(f'FLSH {self.port}')
        SIM900.idn_port(self.port)

    def get_VOLT(self, c): # n = 1
        SIM900.visa_handle.write(f'SNDT {self.port},"VOLT? {c:d}"')
        time.sleep(0.5) # Need to wait long enough to take the reading
        g = SIM900.read_port(self.port)
        if c == 0:
            r = [float(_x) for _x in g.strip().split(',')]
        else:
            r = float(g.strip())
        return r

    def get_VOLT1(self, c, n=1): # n != 1 not implemented
        SIM900.visa_handle.write(f'SNDT {self.port},"VOLT? {c:d},{n:d}"')
        time.sleep(0.5)
        g = SIM900.read_port(self.port)
        if c == 0:
            r = [float(_x) for _x in g.strip().split(',')]
        else:
            r = float(g.strip())
        return r

    def get_VOLT2(self, c, n=1): # n != 1 not implemented
        SIM900.visa_handle.write(f'SNDT {self.port},"VOLT? {c:d},{n:d}"')
        time.sleep(0.5)
        SIM900.visa_handle.write(f'GETN? {self.port},80')
        g = SIM900.visa_handle.read()
        return g

    def get_TVAL(self, c, n=1): # n != 1 not implemented
        SIM900.visa_handle.write(f'SNDT {self.port},"TVAL? {c:d},{n:d}"')
        time.sleep(0.5)
        g = SIM900.read_port(self.port)
        if c == 0:
            r = [float(_x) for _x in g.strip().split(',')]
        else:
            r = float(g.strip())
        return r

    def get_EXON(self, c):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXON? {c:d}"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        if c == 0:
            r = g.strip().split(',')
        else:
            r = g.strip()
        return r

        return g.strip()

    def set_EXON(self, c, EXON):
        SIM900.visa_handle.write(f'SNDT {self.port},"EXON {c:d},{EXON}"')
        time.sleep(0.1)

    def get_DISX(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"DISX?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_DISX(self, DISX):
        SIM900.visa_handle.write(f'SNDT {self.port},"DISX {DISX}"')
        time.sleep(0.1)

    def get_DTEM(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"DTEM?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_DTEM(self, DTEM):
        SIM900.visa_handle.write(f'SNDT {self.port},"DTEM {DTEM}"')
        time.sleep(0.1)

    def get_CURV(self, c):
        SIM900.visa_handle.write(f'SNDT {self.port},"CURV? {c}"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_CURV(self, c, CURV):
        SIM900.visa_handle.write(f'SNDT {self.port},"CURV {c},{CURV}"')
        time.sleep(0.1)

    def get_TOKN(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"TOKN?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_TOKN(self, TOKN):
        SIM900.visa_handle.write(f'SNDT {self.port},"TOKN {TOKN}"')
        time.sleep(0.1)

    def get_LCME(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"LCME?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def get_LEXE(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"LEXE?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def get_TERM(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"TERM?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

# SIM925, text based
class SIM925(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM925', port=6, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        # SIM900.visa_handle.write(f"CONN {self.port},'CCC'") # CCC is arbitrary escape string
        SIM900.visa_handle.write(f'TERM {self.port},LF')
        SIM900.visa_handle.write(f'FLSH {self.port}')
        SIM900.idn_port(self.port)

    def get_MODE(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"MODE?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_MODE(self, MODE):
        SIM900.visa_handle.write(f'SNDT {self.port},"MODE {MODE}"')
        time.sleep(0.1)

    def get_BPAS(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"BPAS?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_BPAS(self, BPAS):
        SIM900.visa_handle.write(f'SNDT {self.port},"BPAS {BPAS}"')
        time.sleep(0.1)

    def get_BUFR(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"BUFR?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return g.strip()

    def set_BUFR(self, BUFR):
        SIM900.visa_handle.write(f'SNDT {self.port},"BUFR {BUFR}"')
        time.sleep(0.1)

    def get_CHAN(self):
        SIM900.visa_handle.write(f'SNDT {self.port},"CHAN?"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        return int(g.strip())

    def set_CHAN(self, CHAN):
        SIM900.visa_handle.write(f'SNDT {self.port},"CHAN {CHAN:d}"')
        time.sleep(0.1)


# SIM970, text based
class SIM970(InstrumentModule):
    def __init__(self, parent=SIM900, name='SIM970', port=7, **kwargs): # Make sure port is correct
        super().__init__(parent, name)
        self.port = port
        # SIM900.visa_handle.write(f"CONN {self.port},'CCC'") # CCC is arbitrary escape string
        SIM900.visa_handle.write(f'TERM {self.port},LF')
        SIM900.visa_handle.write(f'FLSH {self.port}')
        SIM900.idn_port(self.port)

    def get_VOLT(self, c, n=1): # n != 1 not implemented
        SIM900.visa_handle.write(f'SNDT {self.port},"VOLT? {c:d},{n:d}"')
        time.sleep(0.1)
        g = SIM900.read_port(self.port)
        if c == 0:
            r = [float(_x) for _x in g.strip().split(',')]
        else:
            r = float(g.strip())
        return r


#### Usage
if 0:
    from SRS_SIM9XX import SIM900, SIM960, SIM921, SIM922, SIM925
    sim921 = SIM921()
    sim921.set_RANG(6) # 20 kO
    sim921.set_MODE(2) # voltage
    sim921.set_EXCI(3) # 100 uV
    sim921.set_TCON(2) # 3s
    sim921.set_ADIS(1) # Autorange display
    # sim921.get_TCON()

    sim922 = SIM922()
    sim922.get_VOLT(0) # Channels 1-4
    sim922.get_VOLT(1) # Channel 1

    sim925 = SIM925()
    sim925.get_MODE()
    # sim925.set_MODE(0) # set mode to need
    sim925.get_CHAN()
    sim925.set_CHAN(1)

    sim960 = SIM960()
    sim960.set_AMAN(0) # manual mode
    sim960.set_INPT(0) # internal setpoint
    sim960.set_MOUT(0) # manual output value, in manual mode, PID disabled
    sim960.set_LLIM(-0.1)
    sim960.set_GAIN(16)
    sim960.set_INTG(0.2)

    # Close all modules
    SIM900.close()

if 0:
    SIM900.close()
    SIM900 = None
