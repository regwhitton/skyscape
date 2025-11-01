import pyopencl as cl
import numpy as np
from pytest import approx
import re
import itertools
import tle
import dtype as dt
from datetime import datetime

# From https://celestrak.org/NORAD/elements/gp.php?INTDES=1998-067&FORMAT=tle
# and https://www.orbtrack.org/#/?satName=ISS%20(ZARYA)
# Close to figures from https://www.astroviewer.net/iss/en/
def test_iss_zarya2():
    _astrolib_test(
        '1 25544U 98067A   25185.47485775  .00005492  00000+0  10282-3 0  9993',
        '2 25544  51.6344 221.3901 0002450 331.8120  28.2736 15.50368910517843',
        '2025-07-04 19:09:14.0',
        0, 4.1558, 12.70042, 414.72, 7.6645
        )

# From https://celestrak.org/NORAD/elements/gp.php?INTDES=1998-067&FORMAT=tle
# and https://www.orbtrack.org/#/?satName=ISS%20(ZARYA)
# Close to figures from https://www.astroviewer.net/iss/en/
def test_iss_zarya3():
    _astrolib_test(
        '1 25544U 98067A   25185.47485775  .00005492  00000+0  10282-3 0  9993',
        '2 25544  51.6344 221.3901 0002450 331.8120  28.2736 15.50368910517843',
        '2025-07-04 20:27:46.0',
        0, -37.18074, -47.19378, 426.14, 7.6563
        )

def _astrolib_test(tle_line1, tle_line2, utc_datetime, expected_error, expected_latitude_deg, expected_longitude_deg, expected_altitude_km, expected_velocity_kms):

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

    tle_dtype = dt.to_opencl_dtype(device, tle.build_tle_dtype(), 'tle', 'tle.h')

    location_dtype = dt.to_opencl_dtype(
        device,
        np.dtype([
            ('latitude', cl.cltypes.double),
            ('longitude', cl.cltypes.double),
            ('altitude', cl.cltypes.double),
            ('velocity', cl.cltypes.double),
            ('range', cl.cltypes.double),
            ('azimuth', cl.cltypes.double),
            ('elevation', cl.cltypes.double),
            ('range_rate', cl.cltypes.double),
            ('azimuth_rate', cl.cltypes.double),
            ('elevation_rate', cl.cltypes.double),
            ('error', cl.cltypes.int)
        ]),
        'location',
        'location.h'
    )

    program = cl.Program(
        opencl_ctx,
        '#include "celestrak/astrolib/test_astrolib_kernel.cl"'
    ).build(
        options=' -I main/ -I test/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
        cache_dir='caches/opencl_cachedir/'
    )

    input_array = np.empty(1, tle_dtype)
    tle_dict = tle.parse_tle(0, tle_line1, tle_line2)
    for key, value in tle_dict.items():
        input_array[0][key] = value

    output_array = np.empty(1, location_dtype)

    # Setup buffers to copy data to and from GPU device
    mf = cl.mem_flags
    input_buf = cl.Buffer(opencl_ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=input_array)
    output_buf = cl.Buffer(opencl_ctx, mf.WRITE_ONLY, size=output_array.nbytes)

    command_queue = cl.CommandQueue(opencl_ctx)
    program.test_coordfk5(command_queue, (1,), None, p_year, p_month, p_day, p_hour, p_min, p_sec, input_buf, output_buf)

    # Copy the result from the device to the host
    cl.enqueue_copy(command_queue, output_array, output_buf).wait()

    actual = output_array[0]

    #print("\nerror:    {}".format(actual['error']))
    #print(utc_datetime)
    #if actual['error'] == 0:
    #    print("altitude:  {}".format(actual['altitude']))
    #    print("velocity:  {}".format(actual['velocity']))
    #    print("latitude:  {}".format(actual['latitude']))
    #    print("longitude: {}".format(actual['longitude']))
    #    print("range:     {}".format(actual['range']))
    #    print("azimuth:   {}".format(actual['azimuth']))
    #    print("elevation: {}".format(actual['elevation']))
    #    print("range_rate:     {}".format(actual['range_rate']))
    #    print("azimuth_rate:   {}".format(actual['azimuth_rate']))
    #    print("elevation_rate: {}".format(actual['elevation_rate']))

    assert actual['error'] == expected_error, "error"
    if actual['error'] == 0:
        assert actual['altitude'] == approx(expected_altitude_km, abs=1.0), "altitude"
        assert actual['velocity'] == approx(expected_velocity_kms, abs=0.1), "velocity"
        assert actual['latitude'] == approx(expected_latitude_deg, abs=1.0), "latitude"
        assert actual['longitude'] == approx(expected_longitude_deg, abs=1.0), "longitude"
