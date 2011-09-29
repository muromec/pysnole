# -*- coding: utf-8 -*-
import sys
import time

from PyQt4.QtCore import QRect, Qt
from PyQt4.QtGui import (
       QApplication, QWidget, QPainter, QFont, QBrush, QColor, 
       QPen, QPixmap, QImage, QContextMenuEvent)

from .backend import Session


foreground_color_map = {
    0: "#000000",
    1: "#c00006",
    2: "#1bc806",
    3: "#c3c609",
    4: "#0000c2",
    5: "#bf00c2",
    6 : "#19c4c2",
    7 : "#f2f2f2",
    12: "transparent", #  Concealed
    14: "#000000",     # Negative fg
    15: "#ffffff",     # Default fg
}
background_color_map = {
    0: "#000000",
    1: "#cc2300",
    2: "#00cc00",
    3: "#cccc00",
    4: "#0e2acc",
    5: "#cc34cc",
    6: "#00cccc",
    7: "#f5f5f5",
    12: "#555555",     # Cursor
    14: "transparent", # Default bg
    15: "#ffffff",     # Negative bg
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




class TerminalWidget(QWidget):


    def __init__(self, parent=None):
        super(TerminalWidget, self).__init__(parent)
        self.parent().setTabOrder(self, self)
        self.setFocusPolicy(Qt.WheelFocus)
        self._timer_id = None
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setCursor(Qt.IBeamCursor)
        font = QFont("Monospace")
        self.setFont(font)
        self._last_update = None
        self._screen = []
        self._cursor_rect = None
        self._cursor_col = 0
        self._cursor_row = 0
        self._dirty = False
        self._blink = False
        self._press_pos = None
        self._selection = None
        self._sel_widget = None
        self._session = Session()
        self._session.start("/bin/bash")
        QApplication.instance().lastWindowClosed.connect(Session.close_all)
        self._timer_id = None
        if self.hasFocus():
            self.focusInEvent(None)
        else:
            self.focusOutEvent(None)
        #self._session.write("ls -lR")


    def setFont(self, font):
        super(TerminalWidget, self).setFont(font)
        self._update_metrics()

        
    def focusNextPrevChild(self, next):
        return False


    def focusInEvent(self, event):
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(250)
        self._dirty = True
        self.update()


    def focusOutEvent(self, event):
        # reduced update interval 
        # -> slower screen updates
        # -> but less load on main app which results in better responsiveness
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(750)


    def resizeEvent(self, event):
        w, h = self._pixel2pos(self.width(), self.height())
        self._session.resize(w, h)


    def closeEvent(self, event):
        self._session.close()


    def timerEvent(self, event):
        last_change = self._session.last_change()
        if not last_change:
            return
        if not self._last_update or last_change > self._last_update:
            self._last_update = last_change
            old_screen = self._screen
            (self._cursor_col, self._cursor_row), self._screen = self._session.dump()
            self._update_cursor_rect()
            if old_screen != self._screen:
                self._dirty = True
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
        background_color = "#000"
        brush = QBrush(QColor(background_color))
        painter.fillRect(self.rect(), brush)
        foreground_color = "#fff"
        pen = QPen(QColor(foreground_color))
        painter.setPen(pen)
        y = 0
        char_width = self._char_width
        char_height = self._char_height
        painter_drawText = painter.drawText
        painter_fillRect = painter.fillRect
        painter_setPen = painter.setPen
        align = Qt.AlignTop | Qt.AlignLeft
        for row, line in enumerate(self._screen):
            col = 0
            for item in line:
                if isinstance(item, basestring):
                    x = col * char_width
                    length = len(item)
                    new_col = col + length
                    rect = QRect(x, y, x + char_width * length, y + char_height)
                    painter_fillRect(rect, brush)
                    painter_drawText(rect, align, item)
                    col = new_col
                else:
                    foreground_color_idx, background_color_idx, underline_flag = item
                    foreground_color = foreground_color_map[foreground_color_idx]
                    background_color = background_color_map[background_color_idx]
                    pen = QPen(QColor(foreground_color))
                    brush = QBrush(QColor(background_color))
                    painter_setPen(pen)
                    #painter.setBrush(brush)
            y += char_height


    def _paint_selection(self, painter):
        start_pos, end_pos = self._selection
        start_col, start_row = self._pixel2pos(start_pos.x(), start_pos.y())
        end_col, end_row = self._pixel2pos(end_pos.x(), end_pos.y())
        x, y = self._pos2pixel(start_col, start_row)
        width, height = self._pos2pixel(end_col - start_col, end_row - start_row)
        rect = QRect(x, y, width, height)

        pcol = QColor(200, 200, 200, 50)
        pen = QPen(pcol)
        bcol = QColor(230, 230, 230, 50)
        brush = QBrush(bcol)
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRect(rect)

        
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
        

    def keyPressEvent(self, event):
        print "keypress", event.key(), repr(unicode(event.text()))
        text = unicode(event.text())
        key = event.key()
        modifiers = event.modifiers()
        ctrl = modifiers == Qt.ControlModifier
        if ctrl and key == Qt.Key_Plus:
            self.zoom_in()
        elif ctrl and key == Qt.Key_Minus:
                self.zoom_out()
        else:
            if text:
                self._session.write(text.encode("utf-8"))
            else:
                s = keymap.get(key)
                if s:
                    self._session.write(s.encode("utf-8"))
        event.accept()
    

    def mousePressEvent(self, event):
        button = event.button()
        if button == Qt.RightButton:
            ctx_event = QContextMenuEvent(QContextMenuEvent.Mouse, event.pos())
            self.contextMenuEvent(ctx_event)
        elif button == Qt.LeftButton:
            self._press_pos = event.pos()
            self.update()


    def mouseReleaseEvent(self, QMouseEvent):
        self._press_pos = None
        self._selection = None
        self._dirty = True
        self.update()



    def mouseMoveEvent(self, event):
        move_pos = event.pos()
        self._selection = (self._press_pos, move_pos)
        self._dirty = True
        self.update()

