#include "jtime.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/mathtimelib/MathTimeLib.h"

jtime calculate_jtime(
    int p_year, int p_month, int p_day,
    int p_hour, int p_min, double p_sec,
    double p_ut1_utc_diff_secs)
{
    jtime out = {0};
    
    double jd, jd_frac;
    jday_SGP4(p_year, p_month, p_day, p_hour, p_min, p_sec, &jd, &jd_frac);

    out.jd = jd;
    out.jd_frac = jd_frac;

    const double dut1 = p_ut1_utc_diff_secs;
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

    out.jdut1 = jdut1;
    out.jdut1Frac = jdut1Frac;
    out.ttt = ttt;

    // printf("offset=%03d, jd=%lf, jd_frac=%lf, jdut1=%lf, jdut1Frac=%lf, ttt=%lf\n", offset, out.jd, out.jd_frac, out.jdut1, out.jdut1Frac, out.ttt);
    return out;
}
