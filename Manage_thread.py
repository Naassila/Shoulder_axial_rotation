import queue
import threading
import time

class threadingClient(object):
    def __init__(self, master, gui):
        self.master = master
        self.queue=queue.Queue()

        self.gui =  gui

        self.running = True
        self.thread1 = threading.Thread(target=self.worker_thread1)
        self.thread1.start()

        self.periodic_call()

    def periodic_call(self):
        self.master.after(50, self.periodic_call)
        self.gui.processIncoming()
        if not self.running:
            import sys
            sys.exit(1)

    def worker_thread1(self):
        while self.running:
            self.queue.put('')

    def end_application(self):