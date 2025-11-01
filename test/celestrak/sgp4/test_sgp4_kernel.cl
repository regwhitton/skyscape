#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "tle.h"
#include "test_sgp4_input.h"
#include "test_sgp4_output.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/sgp4/SGP4.cl"
#include "celestrak/sgp4/init_satrec.cl"

test_sgp4_output calc_sgp4(double time_since_epoch, elsetrec* satrec) {
    test_sgp4_output out = {0};

    sgp4(satrec, time_since_epoch, out.position, out.velocity);

    out.epoch_mins = time_since_epoch;
    out.error = satrec->error;
    return out;
}

__kernel void test_sgp4(
    __global const test_sgp4_input *input_array,
    __global test_sgp4_output *output_array)
{
    const size_t offset = get_global_id(0);
    __global const test_sgp4_input *input = &input_array[offset];

    double start_epoch_mins = input->start_epoch_mins;
    double stop_epoch_mins = input->stop_epoch_mins;
    double delta_mins = input->delta_mins;

    elsetrec satrec;
    init_satrec(&satrec, &input->tle);

    sgp4init(wgs72, 'a', satrec.satnum, (satrec.jdsatepoch + satrec.jdsatepochF) - 2433281.5, satrec.bstar,
            satrec.ndot, satrec.nddot, satrec.ecco, satrec.argpo, satrec.inclo, satrec.mo, satrec.no_kozai,
            satrec.nodeo, &satrec);

    bool error_found = false;
    double tsince = start_epoch_mins;
    int i = 0;
    while (tsince < stop_epoch_mins) {

        test_sgp4_output out = calc_sgp4(tsince, &satrec);
        output_array[i] = out;

        tsince += delta_mins;
        i++;
        if (out.error != 0) {
            error_found = true;
            break;
        }
    }

    if (!error_found) {
        // Not sure why some test cases have short last intervals.
        // Duplicated because these are the times we have expected results for.
        if (tsince > stop_epoch_mins) {
           tsince = stop_epoch_mins; 
        }

        test_sgp4_output out = calc_sgp4(tsince, &satrec);
        output_array[i] = out;
    }
}
