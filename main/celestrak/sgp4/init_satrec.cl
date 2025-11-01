
#include "tle.h"
#include "celestrak/sgp4/SGP4.h"

/*
 * The original twoline2rv routine initialised the satrec struct directly
 * from the NORAD TLE (two line elements).
 * OpenCL does not support sscanf, so the tle struct provides the record items already parsed using Python.
 * Portions taken from original celestrak routine twoline2rv
 */
void init_satrec(elsetrec* satrec, __global const tle *tle) {
		const double deg2rad = pi / 180.0;         //   0.0174532925199433
		const double xpdotp = 1440.0 / (2.0 *pi);  // 229.1831180523293

		satrec->error = 0;

		for (int i=0; i <= sizeof(satrec->satnum)/sizeof(char); i++)
			satrec->satnum[i] = tle->satnum[i];
		satrec->epochyr = tle->epochyr;
		satrec->epochdays = tle->epochdays;
		satrec->ndot = tle->ndot / (xpdotp*1440.0);  //* ? * minperday
		satrec->nddot = tle->nddot / (xpdotp*1440.0 * 1440);
		satrec->bstar = tle->bstar;
		satrec->inclo = tle->inclo * deg2rad;
		satrec->nodeo = tle->nodeo * deg2rad;
		satrec->ecco = tle->ecco;
		satrec->argpo = tle->argpo * deg2rad;
		satrec->mo = tle->mo * deg2rad;
		satrec->no_kozai = tle->no_kozai / xpdotp; //* rad/min
		satrec->revnum = tle->revnum;

		// ---------------- temp fix for years from 1957-2056 -------------------
		// --------- correct fix will occur when year is 4-digit in tle ---------
		int year;
		if (satrec->epochyr < 57)
			year = satrec->epochyr + 2000;
		else
			year = satrec->epochyr + 1900;

		// Calculate julian date of satellite epoch.
		double sec;
		int mon, day, hr, minute;

		days2mdhms_SGP4(year, satrec->epochdays, &mon, &day, &hr, &minute, &sec);
		jday_SGP4(year, mon, day, hr, minute, sec, &satrec->jdsatepoch, &satrec->jdsatepochF);
}
