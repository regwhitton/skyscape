import pyopencl as cl
import numpy as np
from pytest import approx

def test_setup():

    print()
    opencl_ctx = cl.create_some_context(interactive=False)
    device = opencl_ctx.devices[0]
    print()
    print("Platform            : {}".format(device.platform.name))
    print("Device              : {}".format(device.name))
    print("Address width       : {}".format(device.address_bits))
    print("Max compute units   : {}".format(device.max_compute_units))
    print("Max work group size : {}".format(device.max_work_group_size))
    print("Max work item dims  : {}".format(device.max_work_item_dimensions))
    print("Max work item sizes : {}".format(device.max_work_item_sizes))
    print("Pref wk group sz mlt: {}".format(device.preferred_work_group_size_multiple))
    #print("Supported image formats: {}".format(cl.get_supported_image_formats(opencl_ctx,0,cl.mem_object_type.IMAGE3D)))
    #print("Image2d max height: {}".format(device.image2d_max_height))
    #print("Image2d max width : {}".format(device.image2d_max_width))
    #print("Image3d max height: {}".format(device.image3d_max_height))
    #print("Image3d max width : {}".format(device.image3d_max_width))
    #print("Image3d max depth : {}".format(device.image3d_max_depth))
    #print("Extensions        : {}".format(device.extensions))

    program = cl.Program(
        opencl_ctx,
        '#include "opencl_setup/test_setup_kernel.cl"'
    ).build(
        options=' -I main/ -I test/ ',
        cache_dir='caches/opencl_cachedir/'
    )

    input_array = np.empty(1, cl.cltypes.double)
    output_array = np.empty(1, cl.cltypes.double)

    multiplier = cl.cltypes.double(2.0)
    input_array[0] = cl.cltypes.double(4.0)

    mf = cl.mem_flags
    input_buf = cl.Buffer(opencl_ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=input_array)
    output_buf = cl.Buffer(opencl_ctx, mf.WRITE_ONLY, size=output_array.nbytes)

    command_queue = cl.CommandQueue(opencl_ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)

    #program.test_setup(command_queue, (1,), None, multiplier, input_buf, output_buf)
    # Copy the result from the device to the host
    #event = cl.enqueue_copy(command_queue, output_array, output_buf)
    #event.wait()

    # Same as ...
    kernel = cl.Kernel(program, 'test_setup')
    kernel.set_arg(0, multiplier)
    kernel.set_arg(1, input_buf)
    kernel.set_arg(2, output_buf)
    k_event = cl.enqueue_nd_range_kernel(command_queue, kernel, (1,), None)

    # Copy the result from the device to the host
    #  Is wait_for needed - not often shown.
    event = cl.enqueue_copy(command_queue, output_array, output_buf, wait_for=[k_event])
    event.wait()

    print()
    print("queued  : {}".format(event.profile.queued))
    print("submit  : {}, {} ns".format(event.profile.submit, event.profile.submit - event.profile.queued))
    print("start   : {}, {} ns".format(event.profile.start, event.profile.start - event.profile.submit))
    print("end     : {}, {} ns".format(event.profile.end, event.profile.end - event.profile.start))
    print("complete: {}, {} ns".format(event.profile.complete, event.profile.complete - event.profile.end))
    print("total   : {} ns".format(event.profile.complete - event.profile.queued))

    actual = output_array[0]

    assert actual == approx(2.0 * 4.0)
