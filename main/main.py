import pyopencl as cl
import queue
import threading

from frame_gen.frame_gen import create_images
from gui.gui import gui_display_images

class Flags:
    def __init__(self):
        self.exiting = False
        # So not a flag - just shared between threads.
        self.satrec_buf = None

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

