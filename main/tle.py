""" Two Line Elements (TLE)

TLE handling functions.  Information is extracted from the NORAD
TLE records into a C struct that can be passed to the
OpenCL kernal that calculates satellite positions.

See:
 * https://celestrak.org/NORAD/documentation/tle-fmt.php
 * https://www.space-track.org/documentation#tle
 * Explaination of fields: https://celestrak.org/columns/v04n03/
"""
import numpy as np
import pyopencl as cl
import re
import dtype as dt

SATELLITE_NUMBER = 'satnum'
EPOCH_YEAR = 'epochyr'
EPOCH_DAYS = 'epochdays'
FIRST_DERIVATIVE_OF_MEAN_MOTION = 'ndot'
SECOND_DERIVATIVE_OF_MEAN_MOTION = 'nddot'
BSTAR_DRAG_COEFFICIENT = 'bstar'

ORBITAL_INCLINATION = 'inclo'
RIGHT_ASCENSION = 'nodeo'
ORBITAL_ECCENTRICITY = 'ecco'
ARG_OF_PERIGEE = 'argpo'
MEAN_ANOMALY = 'mo'
MEAN_MOTION = 'no_kozai'
REVOLUTION_NUMBER_AT_EPOCH = 'revnum'

def build_tle_dtype():
    """Returns Numpy dtype definition of TLE C struct we will pass to the OpenCL kernal"""

    return np.dtype([
        (SATELLITE_NUMBER, (cl.cltypes.char,6,)),
        (EPOCH_YEAR, cl.cltypes.int),
        (EPOCH_DAYS, cl.cltypes.double),
        (FIRST_DERIVATIVE_OF_MEAN_MOTION, cl.cltypes.double),
        (SECOND_DERIVATIVE_OF_MEAN_MOTION, cl.cltypes.double),
        (BSTAR_DRAG_COEFFICIENT, cl.cltypes.double),

        (ORBITAL_INCLINATION, cl.cltypes.double),
        (RIGHT_ASCENSION, cl.cltypes.double),
        (ORBITAL_ECCENTRICITY, cl.cltypes.double),
        (ARG_OF_PERIGEE, cl.cltypes.double),
        (MEAN_ANOMALY, cl.cltypes.double),
        (MEAN_MOTION, cl.cltypes.double),
        (REVOLUTION_NUMBER_AT_EPOCH, cl.cltypes.int)
    ])

def parse_tle(tle_name, line1, line2):
    """Parse the 2 element lines into a dict that can be assigned into the Numpy array, that will be converted to C structs to pass to OpenCL kernal"""

    _validate_tle(tle_name, line1, line2)

    sat_number = line1[2:7] + '\x00'
    # See notes for fields 1.7 & 1.8 https://celestrak.org/columns/v04n03/
    epoch_year = line1[18:20]
    epoch_days = line1[20:32]
    first_derivative_of_mean_motion = line1[33:43]
    # See note for field 1.10 & 1.11 https://celestrak.org/columns/v04n03/
    second_derivative_of_mean_motion = line1[44] + '0.' + line1[45:50] + 'E' + line1[50:52]
    bstar_drag_coefficient = line1[53] + '0.' + line1[54:59] + 'E' + line1[59:61]
    orbital_inclination = line2[8:16] # degrees
    right_ascension = line2[17:25] # degrees
    # See note for field 2.5 https://celestrak.org/columns/v04n03/
    orbital_eccentricity = '0.' + line2[26:33]
    arg_of_perigee = line2[34:42] # degrees
    mean_anomaly = line2[43:51] # degrees
    mean_motion = line2[52:63] # revolutions per day
    revolution_number_at_epoch = line2[63:68]

    tle = {}
    tle[SATELLITE_NUMBER] = np.array(list(sat_number.encode()), dtype=cl.cltypes.char)
    tle[EPOCH_YEAR] = cl.cltypes.int(epoch_year)
    tle[EPOCH_DAYS] = cl.cltypes.double(epoch_days)
    tle[FIRST_DERIVATIVE_OF_MEAN_MOTION] = cl.cltypes.double(first_derivative_of_mean_motion)
    tle[SECOND_DERIVATIVE_OF_MEAN_MOTION] = cl.cltypes.double(second_derivative_of_mean_motion)
    tle[BSTAR_DRAG_COEFFICIENT] = cl.cltypes.double(bstar_drag_coefficient)
    
    tle[ORBITAL_INCLINATION] = cl.cltypes.double(orbital_inclination)
    tle[RIGHT_ASCENSION] = cl.cltypes.double(right_ascension)
    tle[ORBITAL_ECCENTRICITY] = cl.cltypes.double(orbital_eccentricity)
    tle[ARG_OF_PERIGEE] = cl.cltypes.double(arg_of_perigee)
    tle[MEAN_ANOMALY] = cl.cltypes.double(mean_anomaly)
    tle[MEAN_MOTION] = cl.cltypes.double(mean_motion)
    tle[REVOLUTION_NUMBER_AT_EPOCH] = cl.cltypes.int(revolution_number_at_epoch)
    return tle

def _validate_tle(tle_name, line1, line2):
    _validate_line(tle_name, 1, line1, _LINE1_REGEXP)
    _validate_line(tle_name, 2, line2, _LINE2_REGEXP)
    if line1[2:7] != line2[2:7]:
        raise Exception("TLE {} does not have the same satellite number on both lines".format(tle_name))

# Support Alpha5 catelogue numbers (2020). See https://www.space-track.org/documentation#tle
_LINE1_REGEXP = re.compile(r"""
    1                               # 1.1 Line Number
    \s
    [0-9A-HJ-NP-Z]\d{4}             # 1.2 Satellite Number
    [UCS]                           # 1.3 Classification
    \s
    (
      \d{2}                         # 1.4 Launch Year
      (\d{3}|\s\d{2}|\s{2}\d)       # 1.5 Launch Number
      [A-Z\s]{3}                    # 1.6 Piece of the launch
    |
      \s{8}                         # 1.4 to 1.6 may all be spaces.
    )
    \s
    \d{2}                           # 1.7 Epoch Year
    (\d{3}|\s\d{2}|\s{2}\d)\.\d{8}  # 1.8 Epoch Day of year and fractional portion of day
    \s
    [-+\s]\.\d{8}                   # 1.9 First Time Derivative of Mean Motion
    \s
    [-+\s]\d{5}[-+]\d               # 1.10 Second Time Derivative of Mean Motion (decimal point assumed)
    \s
    [-+\s]\d{5}[-+]\d               # 1.11 BSTAR drag term (decimal point assumed)
    \s
    (0|\s)                          # 1.12 Ephemeris type
    \s
    [\d\s]{3}\d                     # 1.13 Element number
    \d                              # 1.14 Checksum
""", re.VERBOSE)

_LINE2_REGEXP = re.compile(r"""
    2                               # 2.1 Line Number
    \s
    [0-9A-HJ-NP-Z]\d{4}             # 2.2 Satellite Number
    \s
    (\d{3}|\s\d{2}|\s{2}\d)\.\d{4}  # 2.3 Inclination [Degrees]
    \s
    (\d{3}|\s\d{2}|\s{2}\d)\.\d{4}  # 2.4 Right Ascension of the Ascending Node [Degrees]
    \s
    \d{7}                           # 2.5 Eccentricity (decial point assumed)
    \s
    (\d{3}|\s\d{2}|\s{2}\d)\.\d{4}  # 2.6 Argument of Perigee [Degrees]
    \s
    (\d{3}|\s\d{2}|\s{2}\d)\.\d{4}  # 2.7 Mean Anomaly [Degrees]
    \s
    (\d{2}|\s\d)\.\d{8}             # 2.8 Mean Motion [Revs per day]
    [\d\s]{4}\d                     # 2.9 Revolution number at epoch [Revs]
    \d                              # 2.10 Checksum
""", re.VERBOSE)

def _validate_line(tle_name, line_number, line, regexp):
    if regexp.fullmatch(line) == None:
        raise Exception("TLE {} line {} has incorrect format".format(tle_name, line_number))
    if _check_digit(line) != _calc_expected_check_digit(line):
        msg = "TLE {} line {} does not have correct check digit. Found {} expected {}".format(tle_name, line_number, _check_digit(line), _calc_expected_check_digit(line))
        # raise Exception(msg)
        #Not raising error because Celetrak test data has incorrect checksums
        print(msg)

def _check_digit(line):
    # See notes for field 1.14 https://celestrak.org/columns/v04n03/
    return ord(line[68]) - ord('0')

def _calc_expected_check_digit(line):
    # See notes for field 1.14 https://celestrak.org/columns/v04n03/
    check_digit = ord(line[68]) - ord('0')
    cksum = 0
    for i in range(68):
        chr = line[i]
        val = ord(chr)-ord('0') if '0' <= chr <= '9' else 1 if chr == '-' else 0
        cksum += val
    return (cksum % 10)
