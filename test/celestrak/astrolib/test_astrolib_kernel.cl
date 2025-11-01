#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "tle.h"
#include "location.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/sgp4/SGP4.cl"
#include "celestrak/sgp4/init_satrec.cl"
#include "celestrak/mathtimelib/MathTimeLib.h"
#include "celestrak/mathtimelib/MathTimeLib.cl"
#include "celestrak/astrolib/AstroLib.h"
#include "celestrak/astrolib/AstroLib.cl"


__kernel void test_coordfk5(
    int p_year, int p_month, int p_day,
    int p_hour, int p_min, double p_sec,
    __global const tle *tle_array,
    __global location *location_array)
{
    const size_t offset = get_global_id(0);

    elsetrec satrec;
    init_satrec(&satrec, &tle_array[offset]);

    sgp4init(wgs72, 'a', satrec.satnum, (satrec.jdsatepoch + satrec.jdsatepochF) - 2433281.5, satrec.bstar,
            satrec.ndot, satrec.nddot, satrec.ecco, satrec.argpo, satrec.inclo, satrec.mo, satrec.no_kozai,
            satrec.nodeo, &satrec);

    //double jd, jd_frac; // julian date - days from 4713 bc, plus fractional part of day.
    //jday_SGP4(p_year, p_month, p_day, p_hour, p_min, p_sec, &jd, &jd_frac);
    //double time_since_sat_epoch = (jd - satrec.jdsatepoch) * 1440.0 + (jd_frac - satrec.jdsatepochF) * 1440.0;

    // UT1 - UTC = 29.6 ms on 2025-04-29
    const double current_ut1_utc_delta_secs = 0.0296; // Should also apply to utc -> sat epoch above 
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

    double time_since_sat_epoch = (jdut1 - satrec.jdsatepoch) * 1440.0 + (jdut1Frac - satrec.jdsatepochF) * 1440.0;

    double rteme[3], vteme[3], ateme[3];
    sgp4(&satrec, time_since_sat_epoch, rteme, vteme);

    if (satrec.error != 0) {
        location_array[offset].error = satrec.error;
        return;
    }

    // Converting TEME to latitude and longitude.
    // Using method suggested on https://celestrak.org/publications/AIAA/2006-6753/faq.php

    // Calculate teme acceleration vector
    // Taken from sgp4/cpp/testsgp4/TestSGP4mod.cpp in ZIP at https://celestrak.org/publications/AIAA/2006-6753/
    double magnitude_of_rteme = sqrt(pow(rteme[0],2) + pow(rteme[1],2) + pow(rteme[2],2));
    for (int i = 0; i < 3; i++) {
        // 9.81 m/s^2 is acceleration due to gravity
        ateme[i] = 9.81 * (-1 * rteme[i] / magnitude_of_rteme);
    }

    // Convert time

    //const double dut1 = -0.4399619;
    // UT1 - UTC = 29.6 ms on 2025-04-29
//    const double current_ut1_utc_delta_secs = 0.0296; // Should also apply to utc -> sat epoch above 
//    const double dut1 = current_ut1_utc_delta_secs;
//    const int dat = 32; // Used to calc tai which we don't use.
//    const int timezone = 0;
//    double ut1, tut1, jdut1, jdut1Frac, utc, tai;
//    double tt, ttt, jdtt, jdttFrac, tcg, tdb;
//    double ttdb, jdtdb, jdtdbFrac, tcb;
//
//    convtime( p_year, p_month, p_day, p_hour, p_min, p_sec, timezone,
//        dut1, dat,
//        &ut1, &tut1, &jdut1, &jdut1Frac, &utc, &tai,
//        &tt, &ttt, &jdtt, &jdttFrac, &tcg, &tdb,
//        &ttdb, &jdtdb, &jdtdbFrac, &tcb);

    // Rotate from the TEME to ECEF

    double conv = pi / (180.0*3600.0);
    int eqeterms = 2;  // terms for equation of the equinoxes
    double lod = 0.0015563; // sec
// Can we get these from https://eop2-external.jpl.nasa.gov/ ?
// Tool to do it? https://docs.astropy.org/en/stable/utils/iers.html
    double xp   = -0.140682 * conv;  // polar motion values in rad from arcsec
    double yp   =  0.333309 * conv;

    double recef[3], vecef[3], aecef[3];
    teme_ecef(rteme, vteme, ateme, eTo, recef, vecef, aecef, ttt, jdut1 + jdut1Frac, lod, xp, yp, eqeterms);

    // Next use ecef2llb to convert to lon/lat for testing.
    double latgc, latgd, lon, hellp;
    ecef2ll(recef, &latgc, &latgd, &lon, &hellp);

    double site_latgd = 51.477928 *pi/180.0, site_lon = -0.001545 *pi/180.0, site_alt = 0.068; // Royal Greenwich Observatory
    //double site_latgd = 53.966 *pi/180.0, site_lon = -1.074 *pi/180.0, site_alt = 0.013; // York

    // Convert lon/lat to direction for a particular site.
    double rho, az, el, drho, daz, del;
	rv_razel(recef, vecef, site_latgd, site_lon, site_alt, &rho, &az, &el, &drho, &daz, &del);

    double latgc_in_degree = latgc*(180/pi);
    double lon_in_degree = lon*(180/pi);
    double magnitude_of_velocity = sqrt(pow(vteme[0],2) + pow(vteme[1],2) + pow(vteme[2],2));

    double azimuth_in_degree = az*(180/pi);
    double elevation_in_degree = el*(180/pi);

    location loc;
    loc.latitude = latgc_in_degree;
    loc.longitude = lon_in_degree;
    loc.altitude = hellp;
    loc.velocity = magnitude_of_velocity;
    loc.range = rho;
    loc.azimuth = azimuth_in_degree;
    loc.elevation = elevation_in_degree;
    loc.range_rate = drho;
    loc.azimuth_rate = daz;
    loc.elevation_rate = del;
    loc.error = 0;

    location_array[offset] = loc;
}
