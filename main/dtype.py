import pyopencl as cl
import os

GENERATED_HEADER_DIR="caches/generated_headers"

def to_opencl_dtype(opencl_device, dtype, struct_name, source_filename, include_files=None):

    aligned_dtype, c_decl = cl.tools.match_dtype_to_c_struct(opencl_device, struct_name, dtype)

    registered_dtype = cl.tools.get_or_register_dtype(struct_name, aligned_dtype)

    if not os.path.exists(GENERATED_HEADER_DIR):
        os.makedirs(GENERATED_HEADER_DIR)

    with open(GENERATED_HEADER_DIR + "/" + source_filename, "w") as f:
        f.write("#ifndef _" + struct_name + "_\n")
        f.write("#define _" + struct_name + "_\n")
        if include_files != None:
            for inc in include_files:
                f.write("#include \"" + inc + "\"\n")
        f.write("\n")
            
        f.write(c_decl)
        f.write("\n#endif // _" + struct_name + "_\n")    
    
    return registered_dtype
