#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "tle.h"
#include "celestrak/sgp4/SGP4.h"

__kernel void find_satrec_size(__global size_t *output_array)
{
    //printf("find_satrec_size: %d\n", sizeof(elsetrec));
    elsetrec satrec = {0};
    output_array[0] = sizeof(satrec);
}
