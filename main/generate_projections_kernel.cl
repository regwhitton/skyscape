#pragma OPENCL EXTENSION cl_khr_fp64 : enable

#include "jtime.h"
#include "celestrak/mathtimelib/MathTimeLib.h"
#include "celestrak/astrolib/AstroLib.h"
#include "celestrak/sgp4/SGP4.h"
#include "celestrak/mathtimelib/MathTimeLib.cl"
#include "celestrak/astrolib/AstroLib.cl"
#include "celestrak/sgp4/SGP4.cl"

bool calc_razel(elsetrec *satrec, __global const jtime *jt, double *range, double *azimuth, double *elevation);
void project(__write_only image3d_t image, int frame, double range, double azimuth, double elevation, int image_width, int image_height, char* satnum, size_t satrec_index, __global uint *info);

__kernel void generate_projections(
    int image_width,
    int image_height,
    int n_jtimes,
    __global const jtime *jtimes,
    __global const elsetrec *satrec_array,
    __write_only image3d_t image,
    __global uint *info
)
{        
    double first_range, first_azimuth, first_elevation;
    double range, azimuth, elevation;
    double last_range, last_azimuth, last_elevation;

    size_t satrec_index = get_global_id(0);
    elsetrec satrec = satrec_array[satrec_index];

    bool first_visible = calc_razel(&satrec, &jtimes[0], &first_range, &first_azimuth, &first_elevation);

    bool only_one_point = n_jtimes < 2;
    bool last_visible = only_one_point ? first_visible :
        calc_razel(&satrec, &jtimes[n_jtimes-1], &last_range, &last_azimuth, &last_elevation);

    if (!first_visible && !last_visible) {
        // Go no further if both first and last points are not visible
        return;
    }

    if (first_visible) {
        project(image, 0, first_range, first_azimuth, first_elevation, image_width, image_height, satrec.satnum, satrec_index, info);
    }
    for (int frame = 1; frame < n_jtimes-1; frame++) {
        bool visible = calc_razel(&satrec, &jtimes[frame], &range, &azimuth, &elevation);
        if (visible) {
            project(image, frame, range, azimuth, elevation, image_width, image_height, satrec.satnum, satrec_index, info);
        }
    }
    if (last_visible && !only_one_point) {
        project(image, n_jtimes-1, last_range, last_azimuth, last_elevation, image_width, image_height, satrec.satnum, satrec_index, info);
    }
}

bool calc_razel(
    elsetrec *satrec,
    __global const jtime *jt,
    double *range,
    double *azimuth,
    double *elevation
)
{
    double time_since_sat_epoch = (jt->jdut1 - satrec->jdsatepoch) * 1440.0 + (jt->jdut1Frac - satrec->jdsatepochF) * 1440.0;

    double rteme[3], vteme[3], ateme[3];
    sgp4(satrec, time_since_sat_epoch, rteme, vteme);

    if (satrec->error != 0) {
        return false;
    }

    // Converting TEME to latitude and longitude.
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
    double xp   = -0.140682 * conv;  // polar motion values in rad from arcsec
    double yp   =  0.333309 * conv;

    double recef[3], vecef[3], aecef[3];
    teme_ecef(rteme, vteme, ateme, eTo, recef, vecef, aecef, jt->ttt, jt->jdut1 + jt->jdut1Frac, lod, xp, yp, eqeterms);

    // Next use ecef2llb to convert to lon/lat for testing.
    // double latgc, latgd, lon, hellp;
    // ecef2ll(recef, &latgc, &latgd, &lon, &hellp);
 
    //double site_latgd = 53.7965 *pi/180.0, site_lon = -1.54785 *pi/180.0, site_alt = 0.096; // Cloth Hall Leeds
    double site_latgd = 51.477928 *pi/180.0, site_lon = -0.001545 *pi/180.0, site_alt = 0.068; // Royal Greenwich Observatory
    //double site_latgd = 53.966 *pi/180.0, site_lon = -1.074 *pi/180.0, site_alt = 0.013; // York

    // Convert lon/lat to direction for a particular site.
    double rho, az, el, drho, daz, del;
	rv_razel(recef, vecef, site_latgd, site_lon, site_alt, &rho, &az, &el, &drho, &daz, &del);

    *range = rho;
    *azimuth = az;
    *elevation = el;

    return el > 0;
}

// Which way around these should be?
void project(__write_only image3d_t image, int frame, double range, double azimuth, double elevation, int image_width, int image_height, char* satnum, size_t satrec_index, __global uint *info) {
    // Range doesn't come into it, just the direction.
    const double r0w = image_width/2.0;
    const double rw = cos(elevation) * r0w;
    const int x = (int)(r0w - sin(azimuth) * rw);

    const double r0 = image_height/2.0;
    const double r = cos(elevation) * r0;
    const int y = (int)(r0 - cos(azimuth) * r);

    // printf("%3d %s - range=%lf, azimuth=%lf, elevation=%lf, x=%d, y=%d\n", frame, satnum, range, azimuth, elevation, x, y);
    // int4 coords = 0;
    // coords.s0 = frame;
    // coords.s1 = y;
    // coords.s2 = x;
    //write_imageui(image, coords, 0xffffffff);

    // float4 color = (float4)(
    //     255.0f,    // R
    //     255.0f,    // G
    //     255.0f,    // B
    //     1.0f       // A
    // );
    // write_imagef(image, (int4)(x, y, frame, 0), color);

    int4 coords = (int4)(x, y, frame, 0);
    uint4 color = (uint4)(
        255,    // R
        255,    // G
        255,    // B
        0     // A
    );
    write_imageui(image, coords, color);

    // Perhaps should use separate buffer with diff size, don't get byte order issues.
    // int4 sat_index_coords = (int4)(x, y, 2*frame + 1, 0);
    // uint4 fake_color = (uint4)(
    //     satrec_index | 255,    // R
    //     (satrec_index >> 8) | 255,    // G
    //     (satrec_index >> 16) | 255,    // B
    //     0     // A
    // );
    // // printf("x=%d, y=%d, idx=%d\n", x, y, satrec_index);
    // write_imageui(image, sat_index_coords, fake_color);

    int info_frame_offset = frame * image_width * image_height;
    int info_row_offset = y * image_width;
    info[info_frame_offset + info_row_offset + x] = satrec_index + 1;
}
