import numpy as np
import pyopencl as cl
import dtype as dt

# Assuming this must julian dates in UTC
JULIAN_DATE = 'jd'
JULIAN_FRACTION_INTO_DAY = 'jd_frac'
# UT1 is close to UTC, but leap seconds apart.
JULIAN_DATE_UT1 = 'jdut1'
JULIAN_DATE_UT1_FRACTION_INTO_DAY = 'jdut1Frac'
# Comments in code make it unclear if this is the correct time system's century,
# but they are probably all the same.
JULIAN_CENTRURIES_OF_DYNAMIC_TIME = 'ttt'

def build_jtime_dtype():
    """Returns Numpy dtype definition of jtime C struct we will pass to the OpenCL kernal"""

    return np.dtype([
        (JULIAN_DATE, cl.cltypes.double),
        (JULIAN_FRACTION_INTO_DAY, cl.cltypes.double),
        (JULIAN_DATE_UT1, cl.cltypes.double),
        (JULIAN_DATE_UT1_FRACTION_INTO_DAY, cl.cltypes.double),
        (JULIAN_CENTRURIES_OF_DYNAMIC_TIME, cl.cltypes.double)
    ])

