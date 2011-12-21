# -*- coding: utf-8 -*-
import sys
import time

from PyQt4.QtCore import QRect, Qt, pyqtSignal
from PyQt4.QtGui import (
       QApplication, QClipboard, QWidget, QPainter, QFont, QBrush, QColor, 
       QPen, QPixmap, QImage, QContextMenuEvent)

from .backend import Session



DEBUG = False



class TerminalWidget(QWidget):

    
    foreground_color_map = {
      0: "#000",
      1: "#b00",
      2: "#0b0",
      3: "#bb0",
      4: "#00b",
      5: "#b0b",
      6: "#0bb",
      7: "#bbb",
      8: "#666",
      9: "#f00",
      10: "#0f0",
      11: "#ff0",
      12: "#00f", # concelaed
      13: "#f0f", 
      14: "#000", # negative
      15: "#fff", # default
      'default': "#fff",
    }
    background_color_map = {
      0: "#000",
      1: "#b00",
      2: "#0b0",
      3: "#bb0",
      4: "#00b",
      5: "#b0b",
      6: "#0bb",
      7: "#bbb",
      12: "#aaa", # cursor
      14: "#000", # default
      'default': "#000",
      15: "#fff", # negative
    }
    keymap = {
       Qt.Key_Backspace: chr(127),
       Qt.Key_Escape: chr(27),
       Qt.Key_AsciiTilde: "~~",
       Qt.Key_Up: "~A",
       Qt.Key_Down: "~B",
       Qt.Key_Left: "~D", 
       Qt.Key_Right: "~C", 
       Qt.Key_PageUp: "~1", 
       Qt.Key_PageDown: "~2", 
       Qt.Key_Home: "~H", 
       Qt.Key_End: "~F", 
       Qt.Key_Insert: "~3",
       Qt.Key_Delete: "~4", 
       Qt.Key_F1: "~a",
       Qt.Key_F2: "~b", 
       Qt.Key_F3:  "~c", 
       Qt.Key_F4:  "~d", 
       Qt.Key_F5:  "~e", 
       Qt.Key_F6:  "~f", 
       Qt.Key_F7:  "~g", 
       Qt.Key_F8:  "~h", 
       Qt.Key_F9:  "~i", 
       Qt.Key_F10:  "~j", 
       Qt.Key_F11:  "~k", 
       Qt.Key_F12:  "~l", 
    }


    session_closed = pyqtSignal()


    def __init__(self, parent=None, command="/bin/bash", 
                 font_name="Monospace", font_size=18):
        super(TerminalWidget, self).__init__(parent)
        self.setFocusPolicy(Qt.WheelFocus)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setCursor(Qt.IBeamCursor)
        font = QFont(font_name)
        font.setPixelSize(font_size)
        self.setFont(font)
        self._session = None
        self._last_update = None
        self._screen = []
        self._text = []
        self._cursor_rect = None
        self._cursor_col = 0
        self._cursor_row = 0
        self._dirty = False
        self._blink = False
        self._press_pos = None
        self._selection = None
        self._clipboard = QApplication.clipboard()
        self.setupPainters()
        if command:
            self.execute()

    def setupPainters(self):
        self._pen, self._brash = {}, {}
        for idx,color in self.foreground_color_map.items():
            self._pen[idx] = QPen(QColor(color))

        for idx,color in self.background_color_map.items():
            self._brash[idx] = QBrush(QColor(color))

    def pen(self, color):
        if color in self._pen:
            return self._pen[color]

        _color = self.foreground_color_map.get(color, color)
        pen = QPen(QColor(_color))
        self._pen[color] = pen
        return pen

    def brash(self, color):
        if color in self._brash:
            return self._brash[color]

        _color = self.background_color_map.get(color, color)
        brash = QBrush(QColor(_color))
        self._brash[color] = brash
        return brash
        
    def execute(self, command="/bin/bash"):
        self._session = Session(cmd=command)
        self._session.start()
        self._screen = self._session.screen
        self._timer_id = None
        # start timer either with high or low priority
        if self.hasFocus():
            self.focusInEvent(None)
        else:
            self.focusOutEvent(None)
            
            
    def send(self, s):
        self._session.write(s)

        
    def stop(self):
        self._session.stop()

        
    def pid(self):
        return self._session.pid()


    def setFont(self, font):
        super(TerminalWidget, self).setFont(font)
        self._update_metrics()

        
    def focusNextPrevChild(self, next):
        if not self._session.is_alive():
            return True
        return False


    def focusInEvent(self, event):
        if not self._session.is_alive():
            return
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(250)
        self.update_screen()


    def focusOutEvent(self, event):
        if not self._session.is_alive():
            return
        # reduced update interval 
        # -> slower screen updates
        # -> but less load on main app which results in better responsiveness
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(750)


    def resizeEvent(self, event):
        if not self._session.is_alive():
            return
        self._columns, self._rows = self._pixel2pos(self.width(), self.height())
        self._session.resize(self._columns, self._rows)


    def closeEvent(self, event):
        if not self._session.is_alive():
            return
        self._session.close()


    def timerEvent(self, event):
        if not self._session.is_alive():
            if self._timer_id is not None:
                self.killTimer(self._timer_id)
                self._timer_id = None
            if DEBUG:
                print "Session closed"
            self.session_closed.emit()
            return

        self._dirty = bool(self._screen.dirty)
        if self._dirty:
            self._cursor_col = self._screen.cursor.x
            self._cursor_row = self._screen.cursor.y
            self._update_cursor_rect()

        if self.hasFocus():
            self._blink = not self._blink

        self.update()


    def _update_metrics(self):
        fm = self.fontMetrics()
        self._char_height = fm.height()
        self._char_width = fm.width("W")


    def _update_cursor_rect(self):
        cx, cy = self._pos2pixel(self._cursor_col, self._cursor_row)
        self._cursor_rect = QRect(cx, cy, self._char_width, self._char_height)

        
    def _reset(self):
        self._update_metrics()
        self._update_cursor_rect()
        self.resizeEvent(None)
        self.update_screen()


    def update_screen(self):
        self._dirty = True
        self.update()

        
    def paintEvent(self, event):
        painter = QPainter(self)
        if self._dirty:
            self._dirty = False
            self._paint_screen(painter)
        else:
            if self._cursor_rect and not self._selection:
                self._paint_cursor(painter)
        if self._selection:
            self._paint_selection(painter)
            self._dirty = True


    def _pixel2pos(self, x, y):
        col = int(round(x / self._char_width))
        row = int(round(y / self._char_height))
        return col, row


    def _pos2pixel(self, col, row):
        x = col * self._char_width
        y = row * self._char_height
        return x, y


    def _paint_cursor(self, painter):
        if self._blink:
            color = "#aaa"
        else:
            color = "#fff"
        painter.setPen(QPen(QColor(color)))
        painter.drawRect(self._cursor_rect)


    def _paint_screen(self, painter):
        # Speed hacks: local name lookups are faster
        vars().update(QColor=QColor, QBrush=QBrush, QPen=QPen, QRect=QRect)
        char_width = self._char_width
        char_height = self._char_height
        painter_drawText = painter.drawText
        painter_fillRect = painter.fillRect
        painter_setPen = painter.setPen
        align = Qt.AlignTop | Qt.AlignLeft
        # set defaults
        dirty = set(self._screen.dirty)
        for line in dirty:
            y = char_height * line
            for col,item in enumerate(self._screen[line]):
                
                painter_setPen(self.pen(item.fg))

                x = col * char_width
                rect = QRect(x, y, x + char_width, y + char_height)
                painter_fillRect(rect, self.brash(item.bg))
                painter_drawText(rect, align, item.data)


        if dirty == self._screen.dirty:
            self._screen.dirty.clear()


    def zoom_in(self):
        font = self.font()
        font.setPixelSize(font.pixelSize() + 2)
        self.setFont(font)
        self._reset()

        
    def zoom_out(self):
        font = self.font()
        font.setPixelSize(font.pixelSize() - 2)
        self.setFont(font)
        self._reset()
        

    return_pressed = pyqtSignal()

    def keyPressEvent(self, event):
        text = unicode(event.text())
        key = event.key()
        modifiers = event.modifiers()
        ctrl = modifiers == Qt.ControlModifier
        if ctrl and key == Qt.Key_Plus:
            self.zoom_in()
        elif ctrl and key == Qt.Key_Minus:
                self.zoom_out()
        else:
            if text and key != Qt.Key_Backspace:
                self.send(text.encode("utf-8"))
            else:
                s = self.keymap.get(key)
                if s:
                    self.send(s.encode("utf-8"))
                elif DEBUG:
                    print "Unkonwn key combination"
                    print "Modifiers:", modifiers
                    print "Key:", key
                    for name in dir(Qt):
                        if not name.startswith("Key_"):
                            continue
                        value = getattr(Qt, name)
                        if value == key:
                            print "Symbol: Qt.%s" % name
                    print "Text: %r" % text
        event.accept()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.return_pressed.emit()


    def column_count(self):
        return self._columns
    
    
    def row_count(self):
        return self._rows
    
        
    def is_alive(self):
        return (self._session and self._session.is_alive()) or False
