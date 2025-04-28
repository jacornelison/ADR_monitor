import numpy as np
import PyDAQmx as mx
import time


class Driver():

    def performSetValue( quant, value, sweepRate=0.0, options={}):
        """Create task, set value, close task."""

        if quant == 'Relay Position':
            if value == 'Mag Cycle':
                channel = 'ADR_RESISTOR_BOX/port1/line0'
            elif value == 'Regulate':
                channel = 'ADR_RESISTOR_BOX/port1/line1'
            else:
                assert False, "Error, bad value"

            #Create a new task
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)

            setVal0 = np.array([0], dtype=np.uint8)
            setVal1 = np.array([1], dtype=np.uint8)
            sampsPer = mx.int32()

            #Send a 100 ms pulse to the appropriate channel (0 is on)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)
            time.sleep(0.1)

            #Set it back to low (1 is off)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal1, mx.byref(sampsPer), None)

            #Memory Management!
            writeChan.ClearTask()
        elif quant == '5 Ohm Resistor':
            if value == '5 Ohm in':
                channel = 'ADR_RESISTOR_BOX/port1/line2'
            elif value == '5 Ohm out':
                channel = 'ADR_RESISTOR_BOX/port1/line3'
            else:
                assert False, "Error, bad value"

            #Create a new task
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)

            setVal0 = np.array([0], dtype=np.uint8)
            setVal1 = np.array([1], dtype=np.uint8)
            sampsPer = mx.int32()

            #Send a 100 ms pulse to the appropriate channel (0 is on)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)
            time.sleep(0.1)

            #Set it back to low (1 is off)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal1, mx.byref(sampsPer), None)

            #Memory Management!
            writeChan.ClearTask()
        elif quant == '10 Ohm Resistor':
            if value == '10 Ohm in':
                channel = 'ADR_RESISTOR_BOX/port1/line4'
            elif value == '10 Ohm out':
                channel = 'ADR_RESISTOR_BOX/port1/line5'
            else:
                assert False, "Error, bad value"

            #Create a new task
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)

            setVal0 = np.array([0], dtype=np.uint8)
            setVal1 = np.array([1], dtype=np.uint8)
            sampsPer = mx.int32()

            #Send a 100 ms pulse to the appropriate channel (0 is on)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)
            time.sleep(0.1)

            #Set it back to low (1 is off)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal1, mx.byref(sampsPer), None)

            #Memory Management!
            writeChan.ClearTask()
        elif quant == '25 Ohm Resistor':
            if value == '25 Ohm in':
                channel = 'ADR_RESISTOR_BOX/port1/line6'
            elif value == '25 Ohm out':
                channel = 'ADR_RESISTOR_BOX/port1/line7'
            else:
                assert False, "Error, bad value"

            #Create a new task
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)

            setVal0 = np.array([0], dtype=np.uint8)
            setVal1 = np.array([1], dtype=np.uint8)
            sampsPer = mx.int32()

            #Send a 100 ms pulse to the appropriate channel (0 is on)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)
            time.sleep(0.1)

            #Set it back to low (1 is off)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal1, mx.byref(sampsPer), None)

            #Memory Management!
            writeChan.ClearTask()
        else:
            assert False, "Requesting unknown quantity"

        return value

    def performGetValue( quant, options={}):
        """Create task, get value, close task."""

        if quant == 'Relay Position':
            #Create some values to put things in
            retVal = np.zeros(2, dtype=np.uint8)
            sampsPer = mx.int32()
            numBytesPer = mx.int32()

            #Create a new task
            readChan = mx.Task()
            readChan.CreateDIChan(
                'ADR_RESISTOR_BOX/port2/line0:1', '', mx.DAQmx_Val_ChanPerLine)

            #This does the measurement and updates the values created above
            readChan.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, retVal, 2, mx.byref(
                sampsPer), mx.byref(numBytesPer), None)

            #Memory management!
            readChan.ClearTask()

            assert not all(retVal) and any(
                retVal), "Both channels should not be the same!"

            if all(retVal == [0, 1]):
                value = "Mag Cycle"
            elif all(retVal == [1, 0]):
                value = "Regulate"
            else:
                assert False, "Error: unexpected value returned "+repr(retVal)

        elif quant == '5 Ohm Resistor':
            #Create some values to put things in
            retVal = np.zeros(2, dtype=np.uint8)
            sampsPer = mx.int32()
            numBytesPer = mx.int32()

            #Create a new task
            readChan = mx.Task()
            readChan.CreateDIChan(
                'ADR_RESISTOR_BOX/port2/line2:3', '', mx.DAQmx_Val_ChanPerLine)

            #This does the measurement and updates the values created above
            readChan.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, retVal, 2, mx.byref(
                sampsPer), mx.byref(numBytesPer), None)

            #Memory management!
            readChan.ClearTask()

            assert not all(retVal) and any(
                retVal), "Both channels should not be the same!"

            if all(retVal == [0, 1]):
                value = "5 Ohm in"
            elif all(retVal == [1, 0]):
                value = "5 Ohm out"
            else:
                assert False, "Error: unexpected value returned "+repr(retVal)

        elif quant == '10 Ohm Resistor':
            #Create some values to put things in
            retVal = np.zeros(2, dtype=np.uint8)
            sampsPer = mx.int32()
            numBytesPer = mx.int32()

            #Create a new task
            readChan = mx.Task()
            readChan.CreateDIChan(
                'ADR_RESISTOR_BOX/port2/line4:5', '', mx.DAQmx_Val_ChanPerLine)

            #This does the measurement and updates the values created above
            readChan.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, retVal, 2, mx.byref(
                sampsPer), mx.byref(numBytesPer), None)

            #Memory management!
            readChan.ClearTask()

            assert not all(retVal) and any(
                retVal), "Both channels should not be the same!"

            if all(retVal == [0, 1]):
                value = "10 Ohm in"
            elif all(retVal == [1, 0]):
                value = "10 Ohm out"
            else:
                assert False, "Error: unexpected value returned "+repr(retVal)

        elif quant == '25 Ohm Resistor':
            #Create some values to put things in
            retVal = np.zeros(2, dtype=np.uint8)
            sampsPer = mx.int32()
            numBytesPer = mx.int32()

            #Create a new task
            readChan = mx.Task()
            readChan.CreateDIChan(
                'ADR_RESISTOR_BOX/port2/line6:7', '', mx.DAQmx_Val_ChanPerLine)

            #This does the measurement and updates the values created above
            readChan.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, retVal, 2, mx.byref(
                sampsPer), mx.byref(numBytesPer), None)

            #Memory management!
            readChan.ClearTask()

            assert not all(retVal) and any(
                retVal), "Both channels should not be the same!"

            if all(retVal == [0, 1]):
                value = "25 Ohm in"
            elif all(retVal == [1, 0]):
                value = "25 Ohm out"
            else:
                assert False, "Error: unexpected value returned "+repr(retVal)
        else:
            assert False, "Error: Unknown quantity"

        return value
