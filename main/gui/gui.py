import numpy as np
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageTk, ImageDraw
import PySimpleGUI as sg
import pyopencl as cl
import dtype as dt

# Current difference between UT1 and UTC (UT1-UTC).
# https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds
# Also: https://www.iers.org/IERS/EN/DataProducts/tools/eop_of_today/eop_of_today_tool.html
#UT1_UTC_DIFF_SECS=0.0939  # 2025-10-31
UT1_UTC_DIFF_SECS=0.07024  # 2026-02-05

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

def gui_display_images(queue, flags, opencl_ctx):
    
    latlong_calc = None
    latlong = [np.nan]
    norad_id_str = None
    
    sg.theme('Black')
    sg.set_options(element_padding=(0,0),margins=(0,0))
    if SCREEN_WIDTH == 1280 and ( SCREEN_HEIGHT == 800 or SCREEN_HEIGHT == 1024):
        font_size=14
        title_font_size=30
        space_size=20
    else:
        font_size=16
        title_font_size=30
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
    time_txt = sg.Text(
        key='time',
        font=font,
        expand_x=True
    )
    norad_id_txt = sg.Text(
        key='norad_id',
        font=font,
        expand_x=False
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
    copy_but = sg.Button(
        'copy',
        key='copy_norad_clipboard',
        button_color=('white','black'),
        font=("Calibri", round(font_size/2)),
        visible=False
    )

    info_panel = sg.Column([
            [title_txt],
            [time_txt],
            [sg.Sizer(space_size, space_size)],
            [norad_id_txt, sg.Sizer(30, 10), copy_but],
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
        #size=sg.Window.get_screen_size(),
        size=(SCREEN_WIDTH,SCREEN_HEIGHT),
        #no_titlebar=True,
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
            latlong_calc = _LatlongCalculator(opencl_ctx, flags.satrec_buf)

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
            if key == 'copy_norad_clipboard' and norad_id_str != None:
                sg.clipboard_set(norad_id_str)

        window['frame'].update(data=tk_frame)
        window['time'].update(value=ftime.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))
        
        if pos.clicked:
            found,y,x = search_for_nonzero_near_click(info, pos.y, pos.x, 30)
            if not found:
                norad_id_str = None
                window['norad_id'].update('')
                window['copy_norad_clipboard'].update(visible=False)
                window['name'].update('')
                window['tags'].update('')
                tracked_sat_found = False
                latlong = [np.nan]
            else:
                sat_idx = info[y, x] - 1
                latlong = latlong_calc.calculate_latlong(ftime, sat_idx)
                norad_id_str = sat_info[sat_idx]['norad_id']
                window['norad_id'].update(value="NORAD id: {}".format(norad_id_str))
                window['copy_norad_clipboard'].update(visible=True)
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

class _LatlongCalculator:
    def __init__(self, opencl_ctx, satrec_buf):
        self.open_ctx = opencl_ctx
        #self.opencl_queue = cl.CommandQueue(opencl_ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
        self.opencl_queue = cl.CommandQueue(opencl_ctx)

        self.satrec_buf = satrec_buf

        program = cl.Program(
            opencl_ctx, '#include "calc_latlong_kernel.cl"'
        ).build(
            options=' -I main/ -I ' + dt.GENERATED_HEADER_DIR + ' ',
            cache_dir='caches/opencl_cachedir/'
        )

        self.kernel = cl.Kernel(program, 'calc_latlong')
        
        mf = cl.mem_flags
        self.output_size = 5
        dummy_output_array = np.empty([self.output_size], cl.cltypes.double)
        self.output_buf = cl.Buffer(opencl_ctx, mf.READ_WRITE | mf.HOST_READ_ONLY,
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

        kernel_event = cl.enqueue_nd_range_kernel(self.opencl_queue, self.kernel, (1,), None)
        
        (output_array,map_event) = cl.enqueue_map_buffer(
            self.opencl_queue,
            self.output_buf,
            cl.map_flags.READ,
            offset=0,
            shape=(self.output_size,),
            dtype=cl.cltypes.double,
            is_blocking=False,
            wait_for=[kernel_event]
        )

        map_event.wait()
        self.opencl_queue.finish()
        return output_array
