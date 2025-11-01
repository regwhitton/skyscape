#pragma OPENCL EXTENSION cl_khr_fp64 : enable

__kernel void test_setup(
    double multiplier,
    __global const double *input_array,
    __global double *output_array)
{
    const size_t offset = get_global_id(0);
    double input = input_array[offset];
    output_array[offset] = input * multiplier;
}
