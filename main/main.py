import glob
import pyopencl as cl
import numpy as np
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageTk, ImageDraw
import os
import shutil
import queue
import time as tm
import threading
import PySimpleGUI as sg

import tle
import dtype as dt
import jtime

# Current difference between UT1 and UTC (UT1-UTC).
# https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds
# Also: https://www.iers.org/IERS/EN/DataProducts/tools/eop_of_today/eop_of_today_tool.html
#UT1_UTC_DIFF_SECS=0.0939  # 2025-10-31
UT1_UTC_DIFF_SECS=0.07024  # 2026-02-05

# RGBA - red, green, blue & alpha.
IMAGE_CHANNELS=4

# The size of each image
# Should get actual canvas size once gui rendered.
(SCREEN_WIDTH, SCREEN_HEIGHT) = sg.Window.get_screen_size()
LANDSCAPE=SCREEN_WIDTH > SCREEN_HEIGHT
if LANDSCAPE:
    IMAGE_HEIGHT=SCREEN_HEIGHT
    IMAGE_WIDTH=SCREEN_HEIGHT
else:
    IMAGE_HEIGHT=SCREEN_WIDTH
    IMAGE_WIDTH=SCREEN_WIDTH

# Period between each image/frame
FRAME_PERIOD_SECS=0.25  # 4 frames per second

# The number of images/frames generated in one pass.
# Processing of intermediate for a satellite is skipped if both the first and last are not in view.
# So the larger the number, the more efficient, but the greater danger of sats that should be in view
# getting missed out.  We can assume that sats take at least 5 mins to cross the sky.
IMAGE_FRAMES=4*15  # 15 seconds at 4 FPS.

class Flags:
    def __init__(self):
        self.exiting = False
        # So not a flag - just shared between threads.
        self.satrec_buf = None

def create_images(queue, flags, opencl_ctx):
    opencl = OpenCl(opencl_ctx)
    satrec_size = _find_satrec_size(opencl)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    start_time = now + timedelta(seconds=10)

    # TODO: loop back to here at intervals. Perhaps do every loop but skip if inode not changed.
    # Perhaps just update tle records that have changed.
    tle_array, sat_info = _read_tle_files(opencl)

    satrec_buf = _calc_satrecs(opencl, tle_array, satrec_size)
    flags.satrec_buf = satrec_buf
    n_tle = len(tle_array)

    n_jtimes = IMAGE_FRAMES
    n_jtimes_seconds = timedelta(seconds=n_jtimes * FRAME_PERIOD_SECS)
    jTimeCalculator = _JTimeCalculator(opencl, n_jtimes, FRAME_PERIOD_SECS)
    projectionsGenerator = _ProjectionsGenerator(opencl, n_jtimes, jTimeCalculator.jtime_buf, n_tle, satrec_buf)
    frame_delta = timedelta(seconds=FRAME_PERIOD_SECS)

    while not flags.exiting:
        # Don't work too far ahead.
        while not flags.exiting and start_time > datetime.now(timezone.utc) + (3 * n_jtimes_seconds):
            tm.sleep(1)
        if flags.exiting:
            break

        jtimes_event = jTimeCalculator.calc_jtimes(start_time)
        time = start_time
        frames, infos = projectionsGenerator.generate_projections(jtimes_event)
        for i_frame in range(n_jtimes):
            time += frame_delta
            frame = frames[i_frame]
            info = infos[i_frame]
            queue.put((time, frame, info, sat_info,))

        start_time += n_jtimes_seconds

class OpenCl:
    def __init__(self, opencl_ctx):
        self.ctx = opencl_ctx
        self.device = opencl_ctx.devices[0]
        #self.queue = cl.CommandQueue(opencl_ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
        self.queue = cl.CommandQueue(opencl_ctx)

def _read_tle_files(opencl):

    # Todo remove fix of size !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    tle_pathnames = sorted(glob.glob("./caches/tle/*.tle"))    ####[:49]

    tle_dtype = tle.build_tle_dtype()
    tle_dtype = dt.to_opencl_dtype(opencl.device, tle_dtype, 'tle', 'tle.h')

    tle_array = np.empty(len(tle_pathnames), tle_dtype)

    for i, tle_pathname in enumerate(tle_pathnames):
        with open(tle_pathname, 'r') as file:
            tle_lines = file.readlines()
            if len(tle_lines) != 2:
                raise Exception("{} does not have 2 lines".format(tle_pathname))

        tle_dict = tle.parse_tle(tle_pathname, tle_lines[0].strip(), tle_lines[1].strip())
        for key, value in tle_dict.items():
            tle_array[i][key] = value

    # return tle_array

    sat_info = []
    for i in range(0, len(tle_array)):
        sat_num = tle_array[i]['satnum']
        norad_id = ''
        for c in sat_num:
            if c < 1:
                break
            norad_id += chr(c)

        desc_path = "./caches/tle/{}.desc".format(norad_id)
        with open(desc_path, 'r') as file:
            name = file.readline()
            tags = ''
            for t in file.readlines():
                tags += t
        sat_info.append({'norad_id':norad_id,'name':name,'tags':tags})

    return (tle_array, sat_info,)

def _find_satrec_size(opencl):
    """ We don't know size of satrec struct for buffer, so we use opencl kernel to get it."""

    program = cl.Program(
        opencl.ctx, '#include "find_satrec_size_kernel.cl"'
    ).build(
        options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
        cache_dir='caches/opencl_cachedir/'
    )

    output_array = np.empty(1, cl.cltypes.uint)
    mf = cl.mem_flags
    output_buf = cl.Buffer(opencl.ctx, mf.WRITE_ONLY, size=output_array.nbytes)

    kernel = cl.Kernel(program, 'find_satrec_size')
    kernel.set_arg(0, output_buf)
    k_event = cl.enqueue_nd_range_kernel(opencl.queue, kernel, (1,), None)

    event = cl.enqueue_copy(opencl.queue, output_array, output_buf, wait_for=[k_event])
    event.wait()
    # _stats('find_satrec_size', event)

    return output_array[0]

def _calc_satrecs(opencl, tle_array, satrec_size):
    program = cl.Program(
        opencl.ctx, '#include "calc_satrecs_kernel.cl"'
    ).build(
        # https://registry.khronos.org/OpenCL/specs/3.0-unified/html/OpenCL_API.html#compiler-options
        options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
        cache_dir='caches/opencl_cachedir/'
    )

    n_tle = len(tle_array)

    mf = cl.mem_flags
    tle_buf = cl.Buffer(opencl.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=tle_array)
    satrec_buf = cl.Buffer(opencl.ctx, mf.READ_WRITE | mf.HOST_NO_ACCESS, size=n_tle * satrec_size)

    kernel = cl.Kernel(program, 'calc_satrecs')
    kernel.set_arg(0, tle_buf)
    kernel.set_arg(1, satrec_buf)
    event = cl.enqueue_nd_range_kernel(opencl.queue, kernel, (n_tle,), None)
    event.wait()
    # _stats('calc_satrecs', event)
    return satrec_buf

class _JTimeCalculator:
    def __init__(self, opencl, n_jtimes, frame_period_secs):
        self.opencl = opencl

        jtime_dtype = jtime.build_jtime_dtype()
        jtime_dtype = dt.to_opencl_dtype(opencl.device, jtime_dtype, 'jtime', 'jtime.h')

        program = cl.Program(
            opencl.ctx, '#include "calc_jtime_kernel.cl"'
        ).build(
            options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
            cache_dir='caches/opencl_cachedir/'
        )

        self.n_jtimes = n_jtimes
        self.frame_period_secs = frame_period_secs
        mf = cl.mem_flags
        self.jtime_buf = cl.Buffer(opencl.ctx, mf.READ_WRITE | mf.HOST_NO_ACCESS,
                                   size=jtime_dtype.itemsize * n_jtimes)
        self.kernel = cl.Kernel(program, 'calc_jtime')

    def calc_jtimes(self, start_time):

        p_year = cl.cltypes.int(start_time.year)
        p_month = cl.cltypes.int(start_time.month)
        p_day = cl.cltypes.int(start_time.day)
        p_hour = cl.cltypes.int(start_time.hour)
        p_min = cl.cltypes.int(start_time.minute)
        p_sec = cl.cltypes.double(start_time.second)
        p_frame_period_secs = cl.cltypes.double(self.frame_period_secs)
        p_ut1_utc_diff_secs = cl.cltypes.double(UT1_UTC_DIFF_SECS)

        self.kernel.set_arg(0, p_year)
        self.kernel.set_arg(1, p_month)
        self.kernel.set_arg(2, p_day)
        self.kernel.set_arg(3, p_hour)
        self.kernel.set_arg(4, p_min)
        self.kernel.set_arg(5, p_sec)
        self.kernel.set_arg(6, p_frame_period_secs)
        self.kernel.set_arg(7, p_ut1_utc_diff_secs)
        self.kernel.set_arg(8, self.jtime_buf)

        event = cl.enqueue_nd_range_kernel(self.opencl.queue, self.kernel, (self.n_jtimes,), None)
        return event

# Will need to re-use kernel and buffers.
class _ProjectionsGenerator:
    def __init__(self, opencl, n_jtimes, jtime_buf, n_tle, satrec_buf):
        self.opencl = opencl

        program = cl.Program(
            opencl.ctx, '#include "generate_projections_kernel.cl"'
        ).build(
            options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
            cache_dir='caches/opencl_cachedir/'
        )

        self.kernel = cl.Kernel(program, 'generate_projections')
        self.jtime_buf = jtime_buf
        self.n_jtimes = n_jtimes
        self.satrec_buf = satrec_buf
        self.n_tle = n_tle

        format = cl.ImageFormat(cl.channel_order.RGBA, cl.channel_type.UNSIGNED_INT8)

        mf = cl.mem_flags
        self.device_image_buf = cl.create_image(self.opencl.ctx, mf.WRITE_ONLY | mf.HOST_READ_ONLY, format,
                                                shape=(IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_FRAMES))

        dummy_output_info_array = np.empty([IMAGE_FRAMES, IMAGE_HEIGHT, IMAGE_WIDTH], cl.cltypes.uint)
        self.info_buf_size=dummy_output_info_array.nbytes
        self.device_info_buf = cl.Buffer(self.opencl.ctx, mf.WRITE_ONLY | mf.HOST_READ_ONLY, size=self.info_buf_size)

        # I can't make any sense of how the fill color works, but all 0's gives black.
        red = 0
        green = 0
        blue = 0
        alpha = 0
        self.fill_colour = np.array([red, green, blue, alpha], dtype=cl.cltypes.uint) 

        self.info_fill_pattern = cl.cltypes.uint(0)

    def generate_projections(self, jtimes_event):

        fill_image_event = cl.enqueue_fill_image(
            self.opencl.queue,
            self.device_image_buf,
            self.fill_colour,
            origin=(0,0,0),
            region=(IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_FRAMES)
        )
        
        fill_info_event = cl.enqueue_fill_buffer(
            self.opencl.queue,
            self.device_info_buf,
            self.info_fill_pattern,
            offset=0,
            size=self.info_buf_size
        )

        self.kernel.set_scalar_arg_dtypes([cl.cltypes.int, cl.cltypes.int, cl.cltypes.int, None, None, None, None])

        self.kernel.set_arg(0, cl.cltypes.int(IMAGE_WIDTH))
        self.kernel.set_arg(1, cl.cltypes.int(IMAGE_HEIGHT))
        # Use either IMAGE_FRAMES or passed number consistently.
        self.kernel.set_arg(2, cl.cltypes.int(self.n_jtimes))
        self.kernel.set_arg(3, self.jtime_buf)
        self.kernel.set_arg(4, self.satrec_buf)
        self.kernel.set_arg(5, self.device_image_buf)
        self.kernel.set_arg(6, self.device_info_buf)

        # Each work item is for a satrec and gets the current set of jtimes.
        projections_event = cl.enqueue_nd_range_kernel(self.opencl.queue, self.kernel, (self.n_tle,), None,
                                                        wait_for=[jtimes_event,fill_image_event,fill_info_event])
        
        # Copy the result from the device to the host
        (image_array,image_map_event,row_pitch,slice_pitch) = cl.enqueue_map_image(
            self.opencl.queue,
            self.device_image_buf,
            cl.map_flags.READ,
            origin=(0,0,0),
            region=(IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_FRAMES),
            shape=(IMAGE_FRAMES, IMAGE_HEIGHT, IMAGE_WIDTH),
            dtype=cl.cltypes.uint,
            is_blocking=False,
            wait_for=[projections_event]
        )
    
        (info_array,info_map_event) = cl.enqueue_map_buffer(
            self.opencl.queue,
            self.device_info_buf,
            cl.map_flags.READ,
            offset=0,
            shape=(IMAGE_FRAMES, IMAGE_HEIGHT, IMAGE_WIDTH),
            dtype=cl.cltypes.uint,
            is_blocking=False,
            wait_for=[projections_event]
        )

        image_map_event.wait()
        info_map_event.wait()

        # _stats('calc_jtimes', jtimes_event)
        # _stats('fill', fill_event)
        # _stats('generate_projections', projections_event)
        # _stats('copy_image', map_event)
        self.opencl.queue.finish()
        return (image_array, info_array,)

class _LatlongCalculator:
    def __init__(self, opencl, satrec_buf):
        self.opencl = opencl

        self.satrec_buf = satrec_buf

        program = cl.Program(
            opencl.ctx, '#include "calc_latlong_kernel.cl"'
        ).build(
            options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
            cache_dir='caches/opencl_cachedir/'
        )

        self.kernel = cl.Kernel(program, 'calc_latlong')
        
        mf = cl.mem_flags
        self.output_size = 5
        dummy_output_array = np.empty([self.output_size], cl.cltypes.double)
        self.output_buf = cl.Buffer(opencl.ctx, mf.READ_WRITE | mf.HOST_READ_ONLY,
                                    size=dummy_output_array.nbytes)

    def calculate_latlong(self, time, sat_idx):

        # TODO: check that indexed record has the expected norad id.

        p_year = cl.cltypes.int(time.year)
        p_month = cl.cltypes.int(time.month)
        p_day = cl.cltypes.int(time.day)
        p_hour = cl.cltypes.int(time.hour)
        p_min = cl.cltypes.int(time.minute)
        p_sec = cl.cltypes.double(time.second)
        p_ut1_utc_diff_secs = cl.cltypes.double(UT1_UTC_DIFF_SECS)

        self.kernel.set_scalar_arg_dtypes([
            cl.cltypes.int, cl.cltypes.int, cl.cltypes.int,
            cl.cltypes.int, cl.cltypes.int, cl.cltypes.double,
            cl.cltypes.double, cl.cltypes.long, None, None])

        self.kernel.set_arg(0, p_year)
        self.kernel.set_arg(1, p_month)
        self.kernel.set_arg(2, p_day)
        self.kernel.set_arg(3, p_hour)
        self.kernel.set_arg(4, p_min)
        self.kernel.set_arg(5, p_sec)
        self.kernel.set_arg(6, p_ut1_utc_diff_secs)
        self.kernel.set_arg(7, sat_idx)
        self.kernel.set_arg(8, self.satrec_buf)
        self.kernel.set_arg(9, self.output_buf)

        kernel_event = cl.enqueue_nd_range_kernel(self.opencl.queue, self.kernel, (1,), None)
        
        (output_array,map_event) = cl.enqueue_map_buffer(
            self.opencl.queue,
            self.output_buf,
            cl.map_flags.READ,
            offset=0,
            shape=(self.output_size,),
            dtype=cl.cltypes.double,
            is_blocking=False,
            wait_for=[kernel_event]
        )

        map_event.wait()
        self.opencl.queue.finish()
        return output_array

# def _stats(event_name, event):
#     print(event_name)
#     print("queued  : {}".format(event.profile.queued))
#     print("submit  : {}, {} ns".format(event.profile.submit, event.profile.submit - event.profile.queued))
#     print("start   : {}, {} ns".format(event.profile.start, event.profile.start - event.profile.submit))
#     print("end     : {}, {} ns".format(event.profile.end, event.profile.end - event.profile.start))
#     print("complete: {}, {} ns".format(event.profile.complete, event.profile.complete - event.profile.end))
#     print("total   : {} ns".format(event.profile.complete - event.profile.queued))

def gui_display_images(queue, flags, opencl_ctx):
    
    latlong_calc = None
    latlong = [np.nan]
    
    sg.theme('Black')
    sg.set_options(element_padding=(0,0),margins=(0,0))
    if SCREEN_WIDTH == 1024 and SCREEN_HEIGHT == 768:
        font_size=8
        title_font_size=30
        url_font_size=8
        space_size=20
    else:
        font_size=16
        title_font_size=30
        url_font_size=20
        space_size=20
        
    font=("Calibri", font_size)

    img = sg.Image(
        key='frame',
        size=(IMAGE_HEIGHT,IMAGE_WIDTH,),
        enable_events=True
    )
    title_txt = sg.Text(
        'Skyspace',
        font=("Calibri", title_font_size),
        expand_x=True
    )
    url_txt = sg.Text(
        'https://github.com/regwhitton/skyscape',
        font=("Calibri", url_font_size),
        expand_x=True
    )
    time_txt = sg.Text(
        key='time',
        font=font,
        expand_x=True
    )
    norad_id_txt = sg.Text(
        key='norad_id',
        font=font,
        expand_x=True
    )
    name_txt = sg.Text(
        key='name',
        font=font,
        expand_x=True
    )
    altitude_txt = sg.Text(
        key='altitude',
        font=font,
        expand_x=True
    )
    longitude_txt = sg.Text(
        key='longitude',
        font=font,
        expand_x=True
    )
    latitude_txt = sg.Text(
        key='latitude',
        font=font,
        expand_x=True
    )
    velocity_txt = sg.Text(
        key='velocity',
        font=font,
        expand_x=True
    )
    tags_txt = sg.Text(
        key='tags',
        font=font,
        expand_x=True
    )

    info_panel = sg.Column([
            [title_txt],
            [url_txt],
            [time_txt],
            [sg.Sizer(space_size, space_size)],
            [norad_id_txt],
            [name_txt],
            [altitude_txt],
            [longitude_txt],
            [latitude_txt],
            [velocity_txt],
            [sg.Sizer(space_size, space_size)],
            [tags_txt],
            [sg.VPush()]
        ],
        expand_x=True,
        expand_y=True,
        pad=(10,2)
    )
    spacer = sg.Sizer(space_size, space_size)
    if LANDSCAPE:
        layout = [[ img, spacer, info_panel ]]
    else:
        layout = [[ img ], [spacer], [ info_panel ]]

    window = sg.Window('', layout,
        return_keyboard_events=True,
        location=(0,0),
        size=sg.Window.get_screen_size(),
        # keep_on_top=True,
        # modal=True,
        finalize=True
    )
    window.set_cursor('center_ptr')
    window['frame'].widget.bind("<Motion>", drag_handler)
    window['frame'].widget.bind("<Button-1>", click_handler)

    max_wait_millis = 1000
    max_wait_delta = timedelta(milliseconds=max_wait_millis)

    tracked_sat_found = False

    while not flags.exiting:
        ftime, frame, info, sat_info = queue.get()

        if latlong_calc == None:
            latlong_calc = _LatlongCalculator(OpenCl(opencl_ctx), flags.satrec_buf)

        image = Image.fromarray(frame)
        if tracked_sat_found:
            tracked_sat_found,tracked_sat_y,tracked_sat_x = search_for_sat(sat_idx, info, tracked_sat_y, tracked_sat_x, 150)
            if tracked_sat_found:
                ImageDraw.Draw(image).circle((tracked_sat_x,tracked_sat_y,), 10, outline=80)
                latlong = latlong_calc.calculate_latlong(ftime, sat_idx)
        tk_frame = ImageTk.PhotoImage(image=image)

        waiting_for_frame_time=True
        while waiting_for_frame_time:
            now = datetime.now(timezone.utc)
            if ftime <= now:
                millisec_wait = 0
                waiting_for_frame_time=False
            elif ftime > now + max_wait_delta:
                millisec_wait = max_wait_millis
            else:
                wait_delta = ftime - now
                millisec_wait = wait_delta.seconds * 1000 + wait_delta.microseconds / 1000 

            event, values = window.read(timeout=millisec_wait)
        
            if event == sg.WINDOW_CLOSED:
                flags.exiting=True
                break
            key = event.split(':',1)[0].lower()
            if key == 'q' or key == 'escape':
                flags.exiting=True
                break

        window['frame'].update(data=tk_frame)
        window['time'].update(value=ftime.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))
        
        if pos.clicked:
            found,y,x = search_for_nonzero_near_click(info, pos.y, pos.x, 30)
            if not found:
                window['norad_id'].update('')
                window['name'].update('')
                window['tags'].update('')
                tracked_sat_found = False
                latlong = [np.nan]
            else:
                sat_idx = info[y, x] - 1
                latlong = latlong_calc.calculate_latlong(ftime, sat_idx)
                window['norad_id'].update(value="NORAD id: {}".format(sat_info[sat_idx]['norad_id']))
                window['name'].update(value="Name:        {}".format(sat_info[sat_idx]['name']))
                window['tags'].update(value=sat_info[sat_idx]['tags'])
                tracked_sat_found = True
                tracked_sat_x = x
                tracked_sat_y = y
            pos.clicked = False

        if not np.isnan(latlong[0]):
            window['altitude'].update(value="Altitude:     {:-3,.0f} km".format(latlong[1]))
            window['longitude'].update(value="Longitude:  {:-3,.2f}".format(latlong[4]))
            window['latitude'].update(value="Latitude:     {:-3,.2f}".format(latlong[3]))
            window['velocity'].update(value="Velocity:      {:-3,.1f} km/s".format(latlong[0]))
        else:
            window['altitude'].update("")
            window['longitude'].update("")
            window['latitude'].update("")
            window['velocity'].update("")

        queue.task_done()

    window.close()

class Pos:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.clicked = False
        self.mx = 0
        self.my = 0

pos = Pos()

def drag_handler(event):
    pos.mx = event.x
    pos.my = event.y

def click_handler(event):
    pos.x = event.x
    pos.y = event.y
    pos.clicked = True

def search_for_nonzero_near_click(info, click_y, click_x, max_search_distance):
    matcher = lambda y, x: info[y, x] != 0
    height, width = info.shape
    return search_box(matcher, click_y, click_x, height, width, max_search_distance)

def search_for_sat(sat_idx, info, last_known_y, last_known_x, max_search_distance):
    matcher = lambda y, x: info[y, x] == sat_idx + 1
    height, width = info.shape
    return search_box(matcher, last_known_y, last_known_x, height, width, max_search_distance)

def search_box(matcher, start_y, start_x, height, width, max_search_distance):
    if matcher(start_y, start_x):
        return (True, start_y, start_x,)

    # Search increasing larger pixel boxes around point.
    for dist_from_click in range(1, max_search_distance + 1):
        top_y = max(start_y - dist_from_click, 0)
        bot_y = min(start_y + dist_from_click, height - 1)
        left_x = max(start_x - dist_from_click, 0)
        right_x = min(start_x + dist_from_click, width - 1)

        # Search left and right sides of pixel box.
        for y in range(top_y, bot_y + 1):
            if matcher(y, left_x):
                return (True, y, left_x,)
            if matcher(y, right_x):
                return (True, y, right_x,)
        
        # Search top and bottom sides of pixel box.
        # No need to do first and last pixels again.
        for x in range(left_x + 1, right_x):
            if matcher(top_y, x):
                return (True, top_y, x,)
            if matcher(bot_y, x):
                return (True, bot_y, x,)
            
    return (False,None,None,)

def main():
    flags = Flags()
    q = queue.Queue()
    opencl_ctx = cl.create_some_context(interactive=False)
    create_images_thread = threading.Thread(target=create_images, args=(q, flags, opencl_ctx,))
    create_images_thread.start()
    gui_display_images(q, flags, opencl_ctx)
    create_images_thread.join()

if __name__ == "__main__":
    main()

