#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
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
		self.currentChanged[int].connect(self._on_current_changed)
		QTimer.singleShot(0, self.new_terminal) # create lazy on idle

		
	def _on_close_request(self, idx):
		self._terms.remove(self.widget(idx))
		self.removeTab(idx)
		widget = self.currentWidget()
		if widget:
			widget.setFocus()
		
			
	def _on_current_changed(self, idx):
		widget = self.currentWidget()
		if widget:
			self.setWindowTitle("Terminal %s" % (widget.cwd() or ""))

	
	def new_terminal(self):
		term = TerminalWidget(self)
		term.session_closed.connect(self._on_session_closed)
		term.return_pressed.connect(self._on_return_pressed)
		self.addTab(term, "Terminal")
		self._terms.append(term)
		self.setCurrentWidget(term)
		term.setFocus()
		QTimer.singleShot(500, lambda :self._update_title(term))
		

	def _on_return_pressed(self):
		term = self.sender()
		QTimer.singleShot(500, lambda :self._update_title(term))
		

	def _update_title(self, term):
		idx = self.indexOf(term)
		cwd = term.cwd()
		title = os.path.basename(cwd or "Terminal")
		self.setTabText(idx, title)
		self.setWindowTitle("Terminal %s" % (cwd or ""))

	def _on_session_closed(self):
		if self.count() == 1:
			return
		term = self.sender()
		self._terms.remove(term)
		self.removeTab(self.indexOf(term))
		widget = self.currentWidget()
		if widget:
			widget.setFocus()



if __name__ == "__main__":
	app = QApplication(sys.argv)
	win = TabbedTerminal()
	win.show()
	app.exec_()

