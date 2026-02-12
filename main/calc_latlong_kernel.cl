#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "jtime.h"
#include "calculate_jtime.cl"
#include "celestrak/mathtimelib/MathTimeLib.h"
#include "celestrak/astrolib/AstroLib.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/mathtimelib/MathTimeLib.cl"
#include "celestrak/astrolib/AstroLib.cl"
#include "celestrak/sgp4/SGP4.cl"
#include "calc_ecef.cl"

__kernel void calc_latlong(
    int p_year, int p_month, int p_day,
    int p_hour, int p_min, double p_sec,
    double p_ut1_utc_diff_secs,
    int satrec_index,
    __global const elsetrec *satrec_array,
    __global double *output_info)
{
    jtime jtime = calculate_jtime(
        p_year, p_month, p_day, p_hour, p_min, p_sec, p_ut1_utc_diff_secs);

    elsetrec satrec = satrec_array[satrec_index];

    double recef[3], vecef[3], aecef[3];
    if (!calc_ecef(&satrec, &jtime, recef, vecef, aecef)) {
        output_info[0] = NAN;
        return;
    }
    // printf("index: %d, label: %s\n", satrec_index, satrec.satnum);

    double velocity = sqrt(pow(vecef[0],2) + pow(vecef[1],2) + pow(vecef[2],2));

    // Next use ecef2llb to convert to lon/lat.
    double latgc, latgd, lon, hellp;
    ecef2ll(recef, &latgc, &latgd, &lon, &hellp);

    output_info[0] = velocity; // km/s
    output_info[1] = hellp; // Altitude km
    output_info[2] = latgc * 180.0/pi; // latitude geocentric
    output_info[3] = latgd * 180.0/pi; // latitude geodetic, normally used.
    output_info[4] = lon * 180.0/pi; // longitude
}
