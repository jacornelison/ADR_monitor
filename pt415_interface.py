"""
Code used to interact with the pt415 pulse-tube cooler via a serial port.

To query the pt415, invoke the following:
>>> import pt415_reader
>>> pt415_status = pt415_reader.readPT415Status()

This module is laid out as follows:
    Exception(s)
    The PT415DictEntry class, which formats inquiries to the pt415 dictionary via
predefined hash codes, and parses the pt415's replies.
    pt415_fields, a list of pt415 hash codes of interest.
    readPT415Status, a function which uses a socket connection to the pt415 to
read out information from all of the pt415_fields.

References:
   data_doc.pdf
"CP2800 Data Dictionary + Serial Communication Supplement"
Lists hash codes and contents.

   Sycon Multi Drop Protocol II.pdf
"Sycon Multi Drop Protocol
 DOC VERSION 1.5
 2008-10-09"
Defines the communications protocol with the pt415.

Stephen Hoover, 18 Jan 2012
"""


import serial
import struct
import sys
import time

import numpy as np

com_port = 'COM4'
baudrate = 115200

# PySerial no longer has a read until method, so need to make our own
def read_until(ser, term=0x0D, timeout=2):
    if type(term) != int:
        term = ord(term)
    response = bytearray()
    next_byte = b'\x00'
    start = time.time()
    while ord(next_byte) != term:
        next_byte = ser.read(1)
        if next_byte != b'':
            response.append(ord(next_byte))
        if time.time() - start > 2.0:
            raise Exception("Serial read timed out")

    return response


# Bytes which have special significance in communicating with the pt415.
# See "Sycon Multi Drop Protocol, DOC VERSION 1.5, 2008-10-09"
pt415_bytes  = {'STX':0x02, # Start text
                'PT415_ADDR':0x10, # Address of pt415
                'CR':0x0D, # Carriage Return
                'DATA_READ':0x63,
                'DATA_WRITE':0x61,
                'CMD':0x80,  # This is the CMD for the pt415 protocol implementation
                'CMD_OK':0x89 # This is returned if the CMD was understood and data filled.
                }

####################################################################
####################################################################
class PT415Error(IOError):
    """
    An exception which signifies an error in communications with the pt415.
    """
    def __init__(self, *args, **kwds):
        super(PT415Error,self).__init__(*args, **kwds)

####################################################################
####################################################################
class PT415DictEntry:
    """
    Knows how to communicate with the pt415, using the
    Sycon Multi-Drop Protocol (SMDP) as defined in the document
    "Sycon Multi Drop Protocol, DOC VERSION 1.5, 2008-10-09".

    The pt415 stores data in a dictionary, addressed by preset hash codes.
    The PT415DictEntry object stores one hash code. It can form a
    string which interrogates the pt415 about the value of that particular
    hash code, and can understand the response.
    """

    ####################################################################
    @staticmethod
    def getChecksumBytes(byte_list):
        """
        Calculates the checksums which go into the communicatons string.
        Assume that the input byte list contains all the bytes which
        go into the checksum, and no extra bytes.

        Defined in the SMDP.

        INPUTS
            byte_list: A list of bytes or a string.

        OUTPUT
            A tuple of the two checksum bytes used by the SMDP, created by
            summing together every byte in the input.
        """
        cksum = sum([b for b in bytearray(byte_list)])
        check_byte1 = ((cksum & 0xF0) >> 4) + 0x30
        check_byte2 = (cksum & 0x0F) + 0x30

        return bytearray([check_byte1, check_byte2])

    ####################################################################
    @staticmethod
    def stuffEscapeChars(byte_list):
        """
        Do some byte stuffing as specified in the Sycon Multi-Drop Protocol.
        The characters 0x02, 0x0D, and 0x07 are reserved.
        The SMDP states that:
        0x02 -> 0x07 0x30
        0x0D -> 0x07 0x31
        0x07 -> 0x07 0x32

        INPUTS
            byte_list: May be either a list of bytes or a string.

        OUTPUT
            A list of bytes, in which reserved characters in the input byte_list
            have been translated to an escape character followed by another character.
        """
        stuffed_list = bytearray()
        for byte in bytearray(byte_list):
            if byte == 0x02:
                stuffed_list.append(0x07)
                stuffed_list.append(0x30)
            elif byte == 0x0D:
                stuffed_list.append(0x07)
                stuffed_list.append(0x31)
            elif byte == 0x07:
                stuffed_list.append(0x07)
                stuffed_list.append(0x32)
            else:
                stuffed_list.append(byte)

        return stuffed_list

    ####################################################################
    @staticmethod
    def destuffEscapeChars(byte_list):
        """
        Takes a string transformed by the function "stuffEscapeChars" and
        returns it to its original form.

        INPUTS
            _bytes: May be anything handled in by "convertByteList", including
                a list of bytes or a string.

        OUTPUT
            A string containing the information in the input "_bytes", with
            escaped characters returned to their original, non-escaped versions.
        """
        # First, make sure that we have the input in terms of a string.
        stuffed_bytes = bytearray(byte_list)
        # Replace the escape sequences with the characters they represent.
        destuffed_list = stuffed_bytes.replace(b'\x07\x30', b'\x02').replace(b'\x07\x31',b'\x0D').replace(b'\x07\x32',b'\x07')
        return destuffed_list


    ####################################################################
    def __init__(self, _id, code, units="", increment=0.1,
                 data_type=float, default_value=0, permission='read'):
        """
        INPUTS
            _id: (string) The name of this data type.

            hash_bytes: Should be a list containing two bytes. This
                tells the pt415 which data we're addressing.

            index: A single byte, denoting the index of this value
                in the pt415's data output.

            units [""]: (string) The units of the data (e.g., Amperes, Kelvin).

            increment [0.1]: (float) Multiply the pt415's data value by
                this number to obtain the value of the data in "units".

            data_type [float]: The data type - usually float, but sometimes bool.

            default_value [0]: Default value returned for this dictionary entry,
                if the data read fails.
        """
        self.id = _id
        self.code = code
        self.units = units
        self.data_type = data_type
        self.increment = self.data_type(increment)
        self.default_value = self.data_type(default_value)

        # Can we read from this dictionary entry?
        self.permission = permission


    ####################################################################
    def getReadRequest(self, verbose=False):
        """
        Assembles the string of bytes that tell the pt415 to send information
        on the data in this dictionary entry.
        """
        if self.permission != 'read':
            raise PT415Error((-10,"Cannot read from pt415 dictionary entry "+self.id+"."))

        # Assemble the data read request, minus the start byte
        read_request = bytearray([pt415_bytes['PT415_ADDR'],pt415_bytes['CMD'],pt415_bytes['DATA_READ']]+self.code)

        # Calculate the checksum for this read request.
        check_bytes = self.getChecksumBytes(read_request)

        if verbose: print('check_byte1: %d, check_byte2: %d'%check_bytes)

        # Escape out the stuff that needs it
        read_request = self.stuffEscapeChars(read_request)

        # Append the two check bytes.
        read_request += check_bytes

        # Close the read request with a carraige return.
        read_request.append(pt415_bytes['CR'])

        # Prepend the list with the start packet byte
        read_request.insert(0, pt415_bytes['STX'])

        if verbose: print(read_request)
        return read_request

    def getWriteRequest(self, verbose=False):
        """
        Assembles the string of bytes that tell the pt415 to send information
        on the data in this dictionary entry.
        """
        if self.permission != 'write':
            raise PT415Error((-10,"Cannot write to pt415 dictionary entry "+self.id+"."))

        #Pack the single integer into a list of four bytes in big-endian order
        packed_data = list(np.array([self.default_value], dtype='>i').view('uint8'))

        # Assemble the data read request, minus the start byte
        write_request = bytearray([pt415_bytes['PT415_ADDR'],pt415_bytes['CMD'],pt415_bytes['DATA_WRITE']]+self.code+packed_data)

        # Calculate the checksum for this read request.
        check_bytes = self.getChecksumBytes(write_request)

        if verbose: print('check_byte1: %d, check_byte2: %d'%check_bytes)

        # Escape out the stuff that needs it
        write_request = self.stuffEscapeChars(write_request)

        # Append the two check bytes.
        write_request += check_bytes

        # Close the read request with a carraige return.
        write_request.append(pt415_bytes['CR'])

        # Prepend the list with the start packet byte
        write_request.insert(0, pt415_bytes['STX'])

        if verbose: print(write_request)
        return write_request

    ####################################################################
    def parseOutput(self, output_array):
        """
        Parses an output string from the pt415, assuming that it's a response
        to a query for the dictionary entry represented by this hash.

        The pt415 only sends a return value in response to a data read request,
        so we will never get an output string after a write.

        This function performs several checks to make sure that the string
        it receives has the expected form. It will raise a PT415Error exception if
        it sees anything that looks wrong.
        """
        # First, verify that the bytearray we received has the correct form.
        if (output_array[0]!=pt415_bytes['STX'] or
            output_array[-1]!=pt415_bytes['CR'] or
            output_array[3]!=pt415_bytes['DATA_READ']):
            raise PT415Error((-1, "Invalid return data ("+output_array+")."))

        # Verify the device address.
        if output_array[1]!=pt415_bytes['PT415_ADDR']:
            raise PT415Error((-2, "Unexpected pt415 address ("+repr(output_array[1])+")."))

        # Examine the "command received" byte to see if the pt415 itself
        # has indicated an error with the data read.
        if output_array[2]!=pt415_bytes['CMD_OK']:
            raise PT415Error(( bytearray(output_array[2])[0] & 0x07, "Command error!"))

        # Compute the check bytes and compare to the check bytes in the received string.
        destuffed_array = self.destuffEscapeChars(output_array[1:-3])
        check_bytes = self.getChecksumBytes(destuffed_array)
        if check_bytes != output_array[-3:-1]:
            raise PT415Error((-4, "Invalid checksum!"))

        # Look at the echo of the dictionary location to make sure
        # that we're getting the correct dictionary entry.
        if destuffed_array[3:3+len(self.code)]!=bytearray(self.code):
            raise PT415Error((-3, "This output string ("+repr(output_array)+
                               ") is for a different command!"))

        # Pull out the data. The data should be a 4-byte, big-endian long integer.
        # The call to struct.unpack will complain if the size is wrong.
        data_bytes = self.destuffEscapeChars(output_array)[4+len(self.code):-3]
        data = self.increment*self.data_type(struct.unpack(">l",data_bytes)[0])
        data = self.data_type(data) # Mostly used when data_type is bool. Can't hurt other data_types.

        return data
####################################################################
####################################################################

# Hash values for accessing the pt415's data dictionary.
# This list will be converted to a dictionary immediately
# after we finish defining it.
pt415_fields = [PT415DictEntry('cpu_temp',[0x35,0x74,0x00],"Celcius",0.1),
                PT415DictEntry('compressor_hours',[0x45,0x4C,0x00],"Hours",1./60),
                PT415DictEntry('motor_current',[0x63,0x8B,0x00],'Amps',1.),

                # Temperatures
                PT415DictEntry('temp_water_in',[0x0D,0x8F,0x00],"Celcius",0.1),
                PT415DictEntry('temp_water_out',[0x0D,0x8F,0x01],"Celcius",0.1),
                PT415DictEntry('temp_helium',[0x0D,0x8F,0x02],"Celcius",0.1),
                PT415DictEntry('temp_oil',[0x0D,0x8F,0x03],"Celcius",0.1),
                PT415DictEntry('min_temp_water_in',[0x6E,0x58,0x00],"Celcius",0.1),
                PT415DictEntry('min_temp_water_out',[0x6E,0x58,0x01],"Celcius",0.1),
                PT415DictEntry('min_temp_helium',[0x6E,0x58,0x02],"Celcius",0.1),
                PT415DictEntry('min_temp_oil',[0x6E,0x58,0x03],"Celcius",0.1),
                PT415DictEntry('max_temp_water_in',[0x8A,0x1C,0x00],"Celcius",0.1),
                PT415DictEntry('max_temp_water_out',[0x8A,0x1C,0x01],"Celcius",0.1),
                PT415DictEntry('max_temp_helium',[0x8A,0x1C,0x02],"Celcius",0.1),
                PT415DictEntry('max_temp_oil',[0x8A,0x1C,0x03],"Celcius",0.1),
                PT415DictEntry('temp_error',[0x6E,0x2D,0x00],data_type=bool),

                # Pressures
                # PSIA=Pounds per Square Inch (Absolute)-i.e., includes atmosphereic pressure.
                # 1 psi approximately equals 6,894.757 Pa
                PT415DictEntry('pressure_high_side',[0xAA,0x50,0x00],"PSIA",0.1),
                PT415DictEntry('pressure_low_side',[0xAA,0x50,0x01],"PSIA",0.1),
                PT415DictEntry('min_pressure_high_side',[0x5E,0x0B,0x00],"PSIA",0.1),
                PT415DictEntry('min_pressure_low_side',[0x5E,0x0B,0x01],"PSIA",0.1),
                PT415DictEntry('max_pressure_high_side',[0x7A,0x62,0x00],"PSIA",0.1),
                PT415DictEntry('max_pressure_low_side',[0x7A,0x62,0x01],"PSIA",0.1),
                PT415DictEntry('pressure_error',[0xF8,0x2B,0x00],data_type=bool),
                PT415DictEntry('avg_pressure_low_side',[0xBB,0x94,0x00],"PSIA",0.1),
                PT415DictEntry('avg_pressure_high_side',[0x7E,0x90,0x00],"PSIA",0.1),
                PT415DictEntry('avg_pressure_delta',[0x31,0x9C,0x00],"PSIA",0.1),
                PT415DictEntry('pressure_high_side_deriv',[0x66,0xFA,0x00],"PSIA",0.1),

                # Cryo diode temperatures
                PT415DictEntry('diodes_uv',[0x8E,0xEA,0x00],"V",1e-6),
                PT415DictEntry('diode1_temp',[0x58,0x13,0x00],"Kelvin",0.01),
                PT415DictEntry('diode2_temp',[0x58,0x13,0x01],"Kelvin",0.01),
                PT415DictEntry('diode1_error',[0xD6,0x44,0x00],data_type=bool),
                PT415DictEntry('diode2_error',[0xD6,0x44,0x01],data_type=bool),
                PT415DictEntry('diodes_using_custom_cal_curve',[0x99,0x65,0x00],data_type=bool),

                # Compressor control and status
                PT415DictEntry('compressor_on',[0x5F,0x95,0x00],data_type=bool),
                PT415DictEntry('error_code',[0x65,0xA4,0x00],data_type=int),

                # Commands to control the compressor
                PT415DictEntry('turn_on', [0xd5,0x01,0x00], default_value=1, permission='write'),
                PT415DictEntry('turn_off', [0xc5,0x98,0x00], default_value=0, permission='write'),
                PT415DictEntry('reset_min_max', [0xd3,0xdb,0x00], default_value=1, permission='write')
                ]

pt415_dict = dict( [(_field.id, _field)
                          for _field in pt415_fields] )
pt415_names = [_field.id for _field in pt415_fields if _field.permission=='read']

####################################################################

def readPT415Status_Serial(port=com_port, baudrate = baudrate, errfile=sys.stderr):
    """
    Open a socket connection to the pt415 and read out the values of
    every dictionary entry in the "pt415_fields" variable.

    Always return a dictionary filled with values, no matter what happens.
    If we receive an exception when trying to read from a particular field,
    that field will receive a default entry in the dictionary.

    INPUTS
        ip [moxabox_ip]: (string) The IP address of the Moxa box.

        port [pt415_port]: (int) The port of the pt415 on the Moxa box.

        errfile [sys.stderr]: (opened file) Where to send error messages.

    OUTPUT
        A dictionary containing the status of the pt415. The same dictionary
        will be returned regardless of any read errors: fields which encounter
        a read error will be filled with a default value.
    """
    # Create an empty dict in which to store the pt415 status that we'll read out.
    # Default to every field being zero.
    pt415_status = dict( [(_field.id, _field.default_value)
                          for _field in pt415_fields if _field.permission == 'read'] )
    
    connection = None
    try:
        # Establish a connection to the pt415 via the Moxa box.
        connection = serial.Serial(port, baudrate, timeout = 2)
        assert connection.isOpen(), "Serial port connection error"

        # Query the pt415 about the value of each field.
        for _field in pt415_fields:
            if _field.permission =='read':
                try:
                    # Send the inquiry and get a response.
                    connection.write(_field.getReadRequest())
                    pt415_response = read_until(connection, '\r', 2)
    
                except Exception as err:
                    errfile.write("Field "+_field.id+": got error "+str(err)+'.\n')
                    continue
    
                try:
                    # Parse the response and store it in the output dictionary.
                    pt415_status[_field.id] = _field.parseOutput(pt415_response)
                except PT415Error as err:
                    errfile.write("Field "+_field.id+": got error "+str(err)+
                                     " from response string "+repr(pt415_response)+".\n")
                    continue
    except Exception as err:
        # Don't let an exception crash the function, but do let the
        # user know that something bad happened.
        errfile.write("Got an unexpected error! "+str(err)+'\n')
    finally:
        # Make sure to close the socket connection.
        if connection.isOpen(): connection.close()

    return pt415_status


def status_read_simple(port=com_port, baudrate = baudrate, errfile=sys.stderr):
    status = readPT415Status_Serial(port=port, baudrate = baudrate, errfile=errfile)
    status_data = []
    for k in status.keys():
        status_data.append(float(status[k]))
    return status_data

#%% Turns pt415 on and off remotely
# >>> import pt415_interface
# >>> pt415_status = pt415_interface.readPT415Status_Serial(port=com_port, baudrate = baudrate)
# >>> value = pt415_interface.performSetValue('turn_on', port=com_port, baudrate=baudrate, errfile='pt415.log')
# >>> value = pt415_interface.performSetValue('turn_off', port=com_port, baudrate=baudrate, errfile='pt415.log')
import time
def performSetValue(quant, port=com_port, baudrate=baudrate, errfile='pt415.log'):
    # quant is one of 'turn_on', 'turn_off', 'reset_min_max'
    assert quant in pt415_dict.keys(), "Error: Unknown quantity"

    with serial.Serial(port, baudrate, timeout = 2) as conn:
        key = quant
        request = pt415_dict[key].getWriteRequest()
        # Commented out for pyserial 3.4, which explicitly opens. Should test with 2.7
        # conn.open()
        conn.flushInput()
        conn.write(request)

        #Make sure to do a read so it flushes out the buffer for the next cmd
        response = read_until(conn, '\r', 2)
    with open(errfile, 'a') as f:
        f.write(time.ctime() + ', ' + quant + '\n')

    return quant

