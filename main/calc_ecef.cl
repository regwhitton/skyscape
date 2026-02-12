#include "jtime.h"
#include "celestrak/mathtimelib/MathTimeLib.h"
#include "celestrak/astrolib/AstroLib.h"
#include "celestrak/sgp4/SGP4.h"

bool calc_ecef(
    elsetrec *satrec,
    const jtime *jt,
    double recef[3], double vecef[3], double aecef[3]
)
{
    double time_since_sat_epoch = (jt->jdut1 - satrec->jdsatepoch) * 1440.0 + (jt->jdut1Frac - satrec->jdsatepochF) * 1440.0;

    double rteme[3], vteme[3], ateme[3];
    sgp4(satrec, time_since_sat_epoch, rteme, vteme);

    if (satrec->error != 0) {
        return false;
    }

    // Converting TEME to ECEF and then latitude and longitude, or range/azmuth/elevation.
    // Using method suggested on https://celestrak.org/publications/AIAA/2006-6753/faq.php

    // Calculate teme acceleration vector
    // Taken from sgp4/cpp/testsgp4/TestSGP4mod.cpp in ZIP at https://celestrak.org/publications/AIAA/2006-6753/
    double magnitude_of_rteme = sqrt(pow(rteme[0],2) + pow(rteme[1],2) + pow(rteme[2],2));
    for (int i = 0; i < 3; i++) {
        // 9.81 m/s^2 is acceleration due to gravity
        ateme[i] = 9.81 * (-1 * rteme[i] / magnitude_of_rteme);
    }

    // Rotate from the TEME to ECEF

    double conv = pi / (180.0*3600.0);
    int eqeterms = 2;  // terms for equation of the equinoxes
    double lod = 0.0015563; // sec
    // Can we get these from https://eop2-external.jpl.nasa.gov/ ?
    // Tool to do it? https://docs.astropy.org/en/stable/utils/iers.html
    // double xp   = -0.140682 * conv;  // polar motion values in rad from arcsec
    // double yp   =  0.333309 * conv;
    double xp   = 0.0782 * conv;  // polar motion values in rad from arcsec
    double yp   = 0.3566 * conv;  // 2026-02-05 https://www.iers.org/IERS/EN/DataProducts/tools/eop_of_today/eop_of_today_tool.html

    teme_ecef(rteme, vteme, ateme, eTo, recef, vecef, aecef, jt->ttt, jt->jdut1 + jt->jdut1Frac, lod, xp, yp, eqeterms);

    return true;
}
