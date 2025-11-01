import pytest
import pyopencl as cl
import re
import tle

def test_building_tle_struct_definition():
    unaligned_tle_dtype = tle.build_tle_dtype()

    opencl_ctx = cl.create_some_context(interactive=False)
    _, tle_c_decl = cl.tools.match_dtype_to_c_struct(
        opencl_ctx.devices[0], "tle", unaligned_tle_dtype)
    
    assert _trim_whitespace(tle_c_decl) == _trim_whitespace("""
        typedef struct {
            char satnum[6];
            int epochyr;
            double epochdays;
            double ndot;
            double nddot;
            double bstar;
            double inclo;
            double nodeo;
            double ecco;
            double argpo;
            double mo;
            double no_kozai;
            int revnum;
        } tle;
    """)

def _trim_whitespace(str):
    return re.sub('\\s+', ' ', str.strip())

def test_parsing_tle_into_dict():

    tle_dict = tle.parse_tle('47966',
        '1 47966U 21023B   24172.45505936  .04045857  10158-4  18362-2 0  9997',
        '2 47966  44.9956 207.2793 0004403  32.9642 327.1551 16.21097541180119')

    assert tle_dict['satnum'].tobytes().decode() == '47966\x00'
    assert tle_dict['epochyr'] == 24
    assert tle_dict['epochdays'] == 172.45505936
    assert tle_dict['ndot'] == 0.04045857
    assert tle_dict['nddot'] == 0.10158E-4
    assert tle_dict['bstar'] == 0.0018362
    assert tle_dict['inclo'] == 44.9956
    assert tle_dict['nodeo'] == 207.2793
    assert tle_dict['ecco'] == 0.0004403
    assert tle_dict['argpo'] == 32.9642
    assert tle_dict['mo'] == 327.1551
    assert tle_dict['no_kozai'] == 16.21097541
    assert tle_dict['revnum'] == 18011

    tle_dict = tle.parse_tle('A8924',
        '1 A8924U 24024H   24 64.09407965  .00035856  00000+0  17249-2 0  9992',
        '2 A8924  97.4003 140.9504 0011795 183.5621 176.5532 15.18634114 41266')

    assert tle_dict['satnum'].tobytes().decode() == 'A8924\x00'
    assert tle_dict['epochyr'] == 24
    assert tle_dict['epochdays'] == 64.09407965
    assert tle_dict['ndot'] == 0.00035856
    assert tle_dict['nddot'] == 0.0
    assert tle_dict['bstar'] == 0.0017249
    assert tle_dict['inclo'] == 97.4003
    assert tle_dict['nodeo'] == 140.9504
    assert tle_dict['ecco'] == 0.0011795
    assert tle_dict['argpo'] == 183.5621
    assert tle_dict['mo'] == 176.5532
    assert tle_dict['no_kozai'] == 15.18634114
    assert tle_dict['revnum'] == 4126

