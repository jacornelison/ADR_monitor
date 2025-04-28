import time
import numpy as np
import PyDAQmx as mx


class Driver():

    def performOpen(options={}):
        """Reset the DIO, and then set lines to low in this order: 1/1, 1/2, 1/0."""

        mx.DAQmxResetDevice('ADR_DIO')

        # The value to set
        setVal0 = np.array([0], dtype=np.uint8)

        # A placeholder to catch the return data of samples written
        sampsPer = mx.int32()

        # Set up the task
        channels = ['ADR_DIO/port1/line1',  # Lines 1 & 2 controls the heat switch relay -jz
                    'ADR_DIO/port1/line2',
                    'ADR_DIO/port1/line0']

        # Set the channels to low in the appropriate order
        for channel in channels:
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)
            writeChan.ClearTask()

    def performSetValue(quant, value, sweepRate=0.0, options={}):
        """Create task, set value, close task."""

        if quant == 'Heat Switch':
            if value == 'Open':
                channel = 'ADR_DIO/port1/line1'
                duration = 4.8  # seconds
            elif value == 'Close':
                channel = 'ADR_DIO/port1/line2'
                duration = 3.8  # seconds
            else:
                assert False, "Error, bad value"

            # Create a new task
            writeChan = mx.Task()
            writeChan.CreateDOChan(channel, '', mx.DAQmx_Val_ChanPerLine)

            setVal0 = np.array([0], dtype=np.uint8)
            setVal1 = np.array([1], dtype=np.uint8)
            sampsPer = mx.int32()

            # Send a 100 ms pulse to the appropriate channel (1 is on)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal1, mx.byref(sampsPer), None)
            time.sleep(0.1)

            # Set it back to low (0 is off)
            writeChan.WriteDigitalLines(1, mx.bool32(
                True), 0, mx.DAQmx_Val_GroupByScanNumber, setVal0, mx.byref(sampsPer), None)

            # Memory Management!
            writeChan.ClearTask()

            # Now set up a task to monitor the Opening/Closing lines (port0 lines 0,1)
            # We want to block the program until it is finished

            # Default to ones so that if it's already closed it will pick that up right away
            monVal = np.ones(2, dtype=np.uint8)
            sampsPer = mx.int32()
            numBytesPer = mx.int32()
            monitorToggle = mx.Task()
            monitorToggle.CreateDIChan(
                'ADR_DIO/port0/line0:1', '', mx.DAQmx_Val_ChanPerLine)

            isToggling = True
            startTime = time.time()
            while isToggling == True:
                monitorToggle.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, monVal, 2, mx.byref(
                    sampsPer), mx.byref(numBytesPer), None)
                if all(monVal):
                    isToggling = False
                time.sleep(0.2)

                # Report progress hates values greater than 1?
                if (time.time()-startTime)/duration < 1.0:
                    print((time.time()-startTime)/duration)

            monitorToggle.ClearTask()

        return value

    def performGetValue(quant, options={}):
        """Create task, get value, close task."""

        if quant == 'Touch 4K-1K':
            channel = 'ADR_DIO/port0/line2'
        elif quant == 'Touch 4K-50mK':
            channel = 'ADR_DIO/port0/line3'
        elif quant == 'Touch 1K-50mK':
            channel = 'ADR_DIO/port0/line4'
        else:
            assert False, "Error: unknown quantity"

        # Create some values to put things in
        retVal = np.zeros(1, dtype=np.uint8)
        sampsPer = mx.int32()
        numBytesPer = mx.int32()

        # Create a new task
        readChan = mx.Task()

        readChan.CreateDIChan(channel, '', mx.DAQmx_Val_ChanPerLine)

        # This does the measurement and updates the values created above
        readChan.ReadDigitalLines(1, 0, mx.DAQmx_Val_GroupByScanNumber, retVal, 1, mx.byref(
            sampsPer), mx.byref(numBytesPer), None)

        # Memory management!
        readChan.ClearTask()

        if retVal == [0]:
            value = "Touch"
        elif retVal == [1]:
            value = "No Touch"
        else:
            assert False, "Error: unexpected value returned "+repr(retVal)

        return value