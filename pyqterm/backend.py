# -*- coding: utf-8 -*-
# This code is based on AjaxTerm/Web-Shell which included a fairly complete
# vt100 implementation as well as a stable process multiplexer.
# I made some small fixes, improved some small parts and added a Session class
# which can be used by the widget.
# License: GPL2
import os
import fcntl
import threading
import time
import termios
import pty
import signal
import struct
import select
import subprocess

import pyte

__version__ = "0.1"

def synchronized(func):
    def wrapper(self, *args, **kwargs):
        try:
            self.lock.acquire()
        except AttributeError:
            self.lock = threading.RLock()
            self.lock.acquire()
        try:
            result = func(self, *args, **kwargs)
        finally:
            self.lock.release()
        return result
    return wrapper


import cStringIO

class TagStream(pyte.ByteStream):
    def __init__(self,):
        super(TagStream, self).__init__()
        self.handlers['annotation'] = self._ann

    def _ann(self, char):

        if char == u'\ufffa':
            self.annotation.seek(0)
            self.dispatch("annotate", self.annotation.read())
            self.state = 'stream'
            return

        self.annotation.write(char)

    def _stream(self, char):

        if char == u'\ufff9':
            self.state = 'annotation'
            self.annotation = cStringIO.StringIO()
            return
        if char == u'\ufffb':
            self.dispatch("annotate", None)

        super(TagStream, self)._stream(char)

class TagScreen(pyte.Screen):
    def annotate(self, text):
        self.cursor.attrs = self.cursor.attrs._replace(fg=text or 'default')

class Session(object):

    class Screen(TagScreen, pyte.DiffScreen):
        pass


    def __init__(self, cmd="/bin/bash", env_term = "linux", timeout=60*60*24, size=(80,24)):
        # Session
        self.session = {}
        self.cmd = cmd
        self.env_term = env_term
        self.timeout = timeout
        self.size = size

        # pyte
        self.stream = TagStream()
        self.screen = self.Screen(*self.size)
        self.stream.attach(self.screen)

        # Supervisor thread
        self.signal_stop = 0
        self.thread = threading.Thread(target = self.proc_thread)


    def stop(self):
        # Stop supervisor thread
        self.signal_stop = 1
        self.thread.join()

    def resize(self, w, h):
        self.screen.resize(h,w)
        try:
            fcntl.ioctl(self.fd,
                struct.unpack('i',
                    struct.pack('I', termios.TIOCSWINSZ)
                )[0],
                struct.pack("HHHH", h, w, 0, 0))
        except (IOError, OSError):
            pass

    @synchronized
    def start(self):
        # Start a new session
        return self.proc_spawn()

    def proc_spawn(self,):
        # Session
        w, h = self.size

        # Fork new process
        pid, fd = pty.fork()

        if pid == 0:
            # Safe way to make it work under BSD and Linux
            try:
                ls = os.environ['LANG'].split('.')
            except KeyError:
                ls = []
            if len(ls) < 2:
                ls = ['en_US', 'UTF-8']
            try:
                os.putenv('COLUMNS', str(w))
                os.putenv('LINES', str(h))
                os.putenv('TERM', self.env_term)
                os.putenv('PATH', os.environ['PATH'])
                os.putenv('LANG', ls[0] + '.UTF-8')
                p = subprocess.Popen(self.cmd, shell=False)
                child_pid, sts = os.waitpid(p.pid, 0)
            except (IOError, OSError):
                pass
            # self.proc_finish(sid)
            os._exit(0)
        else:
            # Store session vars
            self.pid = pid
            self.fd = fd
            # Set file control
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            # Set terminal size
            self.resize(w, h)

            self.thread.start()

            return True


    def proc_waitfordeath(self):
        try:
            os.close(self.fd)
        except (KeyError, IOError, OSError):
            pass
        try:
            os.waitpid(self.fd, 0)
        except (KeyError, IOError, OSError):
            pass
        return True


    @synchronized
    def proc_bury(self):
        try:
            os.kill(self.pid, signal.SIGTERM)
        except (IOError, OSError):
            pass

        self.proc_waitfordeath()
        return True


    @synchronized
    def proc_read(self):
        """
        Read from process
        """
        try:
            d = os.read(self.fd, 65536)
            if not d:
                # Process finished, BSD
                self.proc_waitfordeath()
                return False
        except (IOError, OSError):
            # Process finished, Linux
            self.proc_waitfordeath()
            return False

        self.stream.feed(d)

    @synchronized
    def write(self, d):
        """
        Write to process
        """
        try:
            os.write(self.fd, d)
        except (IOError, OSError):
            return False
        return True


    def proc_thread(self):
        """
        Supervisor thread
        """
        while not self.signal_stop:
            fds = [self.fd]
            try:
                i, o, e = select.select(fds, [], [], 1.0)
            except (IOError, OSError):
                i = []
            except select.error:
                break

            if i:
                self.proc_read()
                time.sleep(0.002)

        self.proc_bury()

        self.stream.feed('\n[ exited ]')
