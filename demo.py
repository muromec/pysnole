#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from PyQt4.QtCore import QTimer
from PyQt4.QtGui import QApplication, QTabWidget, QPushButton
from pyqterm import TerminalWidget



class TabbedTerminal(QTabWidget):

	
	def __init__(self, parent=None):
		super(TabbedTerminal, self).__init__(parent)
		self.setTabPosition(QTabWidget.South)
		self._new_button = QPushButton(self)
		self._new_button.setText("New")
		self._new_button.clicked.connect(self.new_terminal)
		self.setCornerWidget(self._new_button)
		self.setTabsClosable(True)
		self.setMovable(True)
		self.setWindowTitle("Terminal")
		self.resize(800, 600)
		self._terms = []
		self.tabCloseRequested[int].connect(self._on_close_request)
		QTimer.singleShot(0, self.new_terminal) # create lazy on idle

		
	def _on_close_request(self, idx):
		self._terms.remove(self.widget(idx))
		self.removeTab(idx)

		
	def new_terminal(self):
		term = TerminalWidget(self)
		self.addTab(term, "Terminal %s" % id(term))
		self._terms.append(term)
		self.setCurrentWidget(term)
		term.setFocus()
	


if __name__ == "__main__":
	app = QApplication(sys.argv)
	win = TabbedTerminal()
	win.show()
	app.exec_()

