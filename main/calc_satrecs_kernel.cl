#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "tle.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/sgp4/SGP4.cl"
#include "celestrak/sgp4/init_satrec.cl"

__kernel void calc_satrecs(
    __global const tle *tle_array,
    __global elsetrec *satrec_array)
{
    const size_t offset = get_global_id(0);
    __global const tle *p_tle = &tle_array[offset];

    elsetrec satrec;
    init_satrec(&satrec, p_tle);

    sgp4init(wgs72, 'a', satrec.satnum, (satrec.jdsatepoch + satrec.jdsatepochF) - 2433281.5, satrec.bstar,
            satrec.ndot, satrec.nddot, satrec.ecco, satrec.argpo, satrec.inclo, satrec.mo, satrec.no_kozai,
            satrec.nodeo, &satrec);

    satrec_array[offset] = satrec;
}
