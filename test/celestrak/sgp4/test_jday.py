import pyopencl as cl
import numpy as np
from pytest import approx
from datetime import datetime
import tle
import dtype as dt

# Test data calculated using https://aa.usno.navy.mil/data/JulianDate

def test_whole_days_since_noon_jan_1st_4713bc():
    _jday_test(
        '2025-07-05 00:00:00.000',
        2460861.5, 0.0
        )

def test_partial_days_since_noon_jan_1st_4713bc():
    _jday_test(
        '2025-07-05 19:28:05.100',
        2460861.5, 0.811170
        )

def _jday_test(utc_datetime, expected_julian_date, expected_fraction):

    date = datetime.strptime(utc_datetime, '%Y-%m-%d %H:%M:%S.%f')
    p_year = cl.cltypes.int(date.year)
    p_month = cl.cltypes.int(date.month)
    p_day = cl.cltypes.int(date.day)
    p_hour = cl.cltypes.int(date.hour)
    p_min = cl.cltypes.int(date.minute)
    p_sec = cl.cltypes.double(date.second + (date.microsecond/1000000.0))

    print()
    opencl_ctx = cl.create_some_context(interactive=False)
    device = opencl_ctx.devices[0]

    # tle.h not used by test, but used in included header
    tle_dtype = dt.to_opencl_dtype(device, tle.build_tle_dtype(), 'tle', 'tle.h')

    program = cl.Program(
        opencl_ctx,
        '#include "celestrak/sgp4/test_jday_kernel.cl"'
    ).build(
        options=' -I main/ -I test/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
        cache_dir='caches/opencl_cachedir/'
    )

    output_array = np.empty(6, cl.cltypes.double)

    # Setup buffers to copy data to and from GPU device
    mf = cl.mem_flags
    output_buf = cl.Buffer(opencl_ctx, mf.WRITE_ONLY, size=output_array.nbytes)

    command_queue = cl.CommandQueue(opencl_ctx)
    program.test_jday(command_queue, (1,), None, p_year, p_month, p_day, p_hour, p_min, p_sec, output_buf)

    # Copy the result from the device to the host
    cl.enqueue_copy(command_queue, output_array, output_buf).wait()

    jd = output_array[0]
    jd_frac = output_array[1]
    jdut1 = output_array[2]
    jdut1Frac = output_array[3]
    ttt = output_array[4]
    tut1 = output_array[5]

    print("jd        {}".format(jd))
    print("jd_frac   {}".format(jd_frac))
    print("jdut1     {}".format(jdut1))
    print("jdut1Frac {}".format(jdut1Frac))
    print("ttt       {}".format(ttt))
    print("tut1      {}".format(tut1))

    assert jd == approx(expected_julian_date), "julian date"
    assert jd_frac == approx(expected_fraction), "julian fraction of day"
