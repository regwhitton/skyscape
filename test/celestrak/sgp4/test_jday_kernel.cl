#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "celestrak/sgp4/SGP4.h"
#include "celestrak/sgp4/SGP4.cl"
#include "celestrak/mathtimelib/MathTimeLib.h"
#include "celestrak/mathtimelib/MathTimeLib.cl"


__kernel void test_jday(
    int p_year, int p_month, int p_day,
    int p_hour, int p_min, double p_sec,
    __global double *output_array)
{
    const size_t offset = get_global_id(0);

    double jd, jd_frac;
    jday_SGP4(p_year, p_month, p_day, p_hour, p_min, p_sec, &jd, &jd_frac);

    output_array[offset] = jd;
    output_array[offset+1] = jd_frac;

    //const double dut1 = -0.4399619;
    // UT1 - UTC = 29.6 ms on 2025-04-29
    double current_ut1_utc_delta_secs = 0.0296;
    const double dut1 = current_ut1_utc_delta_secs;
    const int dat = 32; // Used to calc tai which we don't use.
    const int timezone = 0;
    double ut1, tut1, jdut1, jdut1Frac, utc, tai;
    double tt, ttt, jdtt, jdttFrac, tcg, tdb;
    double ttdb, jdtdb, jdtdbFrac, tcb;

    convtime( p_year, p_month, p_day, p_hour, p_min, p_sec, timezone,
        dut1, dat,
        &ut1, &tut1, &jdut1, &jdut1Frac, &utc, &tai,
        &tt, &ttt, &jdtt, &jdttFrac, &tcg, &tdb,
        &ttdb, &jdtdb, &jdtdbFrac, &tcb);

    output_array[offset+2] = jdut1;
    output_array[offset+3] = jdut1Frac;
    output_array[offset+4] = ttt;
    output_array[offset+5] = tut1;
}
