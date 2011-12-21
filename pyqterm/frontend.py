# -*- coding: utf-8 -*-
import sys, os
import time

from PyQt4.QtCore import QRect, Qt, pyqtSignal, QByteArray
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

    class Screen(object):
        def __init__(self, widget):
            self.widget = widget

        def draw(self, char):
            self.widget.update()

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
        self._draw_screen = self.Screen(self)
        self.setupPainters()
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
        self._session.stream.attach(self._draw_screen)

        self._session.start()
        self._screen = self._session.screen

            
    def send(self, s):
        self._session.write(s)

    def stop(self):
        self._session.stop()

    def pid(self):
        return self._session.pid()


    def setFont(self, font):
        super(TerminalWidget, self).setFont(font)
        self._update_metrics()

        
    def resizeEvent(self, event):
        self._columns, self._rows = self._pixel2pos(self.width(), self.height())
        self._session.resize(self._columns, self._rows)

        self._margins = [
            QRect(
                0,
                self._rows * self._char_height,
                self.width(),
                self._char_height,
            ),
            QRect(
                self._columns * self._char_width,
                0,
                self._char_width,
                self.height(),
            ),
        ]

        # XXX: should pyte handle this for me?
        self._screen.dirty.update(range(self._rows))



    def closeEvent(self, event):
        self._session.proc_bury()

    def _update_metrics(self):
        fm = self.fontMetrics()
        self._char_height = fm.height()
        self._char_width = fm.width("W")

    def update_screen(self):
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        if self._screen.dirty:
            self._paint_screen(painter, self._screen.dirty)

        if self._margins:
            bot, right = self._margins
            painter.fillRect(right, self.brash('default'))
            painter.fillRect(bot, self.brash('default'))
            self._margins = []


    def _pixel2pos(self, x, y):
        col = int(round(x / self._char_width))
        row = int(round(y / self._char_height))
        return col, row


    def _pos2pixel(self, col, row):
        x = col * self._char_width
        y = row * self._char_height
        return x, y

    def _paint_screen(self, painter, lines):
        # Speed hacks: local name lookups are faster
        vars().update(QColor=QColor, QBrush=QBrush, QPen=QPen, QRect=QRect)
        char_width = self._char_width
        char_height = self._char_height
        painter_drawText = painter.drawText
        painter_fillRect = painter.fillRect
        painter_setPen = painter.setPen
        align = Qt.AlignTop | Qt.AlignLeft
        # set defaults
        while lines:
            line = lines.pop()

            if line >= len(self._screen):
                continue

            y = char_height * line
            for col,item in enumerate(self._screen[line]):
                x = col * char_width

                if item.fg and item.fg.startswith('img:'):
                    self.draw_Image(painter, x, y+char_height, item.fg)
                    continue

                painter_setPen(self.pen(item.fg))

                rect = QRect(x, y, char_width, char_height)
                painter_fillRect(rect, self.brash(item.bg))
                painter_drawText(rect, align, item.data)


    def draw_Image(self, painter, x, y, img):
        import base64
        _head, img = img.split('\n',1)
        data = base64.b64decode(img)
        qimg = QImage.fromData(data)
        painter.drawImage(x, y, qimg)


    return_pressed = pyqtSignal()

    def keyPressEvent(self, event):
        text = unicode(event.text())
        key = event.key()

        if text and key != Qt.Key_Backspace:
            self.send(text.encode("utf-8"))
        else:
            s = self.keymap.get(key)
            if s:
                self.send(s.encode("utf-8"))

        event.accept()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.return_pressed.emit()
