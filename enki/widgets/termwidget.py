"""
termwidget --- Terminal emulator widget
=======================================

Shows intput and output text. Allows to enter commands. Supports history.

This widget only provides GUI, but does not implement any system terminal or other functionality
"""

import cgi

from PyQt5.QtCore import QEvent, QPoint, QSize
from PyQt5.QtWidgets import QLabel, \
                        QSizePolicy, QTextEdit, \
                        QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QKeySequence, QPalette, \
                        QTextCursor

from enki.core.core import core

from qutepart import Qutepart

class _TextEdit(Qutepart):
    """Text editor class, which implements good size hints
    """
    def __init__(self, parent, font):
        Qutepart.__init__(self, parent)
        self._sizeHintLabel = QLabel("asdf")
        self._sizeHintLabel.setFont(font)

    def minimumSizeHint(self):
        """QWidget.minimumSizeHint implementation
        """
        lineHeight = self._calculateLineHeight()
        return QSize(lineHeight * 2, lineHeight * 2)

    def sizeHint(self):
        """QWidget.sizeHint implementation
        """
        lineHeight = self._calculateLineHeight()
        return QSize(lineHeight * 6, lineHeight * 6)

    def _calculateLineHeight(self):
        """Calculate height of one line of text
        """
        return self._sizeHintLabel.sizeHint().height()


class TermWidget(QWidget):
    """Widget wich represents terminal. It only displays text and allows to enter text.
    All highlevel logic should be implemented by client classes
    """

    def __init__(self, font, *args):
        QWidget.__init__(self, *args)
        self._browser = QTextEdit(self)
        self._browser.setReadOnly(True)
        document = self._browser.document()
        document.setDefaultStyleSheet(document.defaultStyleSheet() +
                                      "span {white-space:pre;}")

        self._browser.setFont(font)
        self._edit = _TextEdit(self, font)

        lowLevelWidget = self._edit.focusProxy()
        if lowLevelWidget is None:
            lowLevelWidget = self._edit
        lowLevelWidget.installEventFilter(self)

        self._edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.setFocusProxy(self._edit)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)
        layout.addWidget(self._edit)

        self._history = ['']  # current empty line
        self._historyIndex = 0

        self._edit.setFocus()

    def terminate(self):
        self._edit.terminate()

    def eventFilter(self, obj, event):
        pass # suppress docsting for non-public method
        """QWidget.eventFilter implementation. Catches _edit key pressings. Processes some of them
        """
        if event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.MoveToNextLine):
                if self._edit.cursorPosition[0] == (len(self._edit.lines) - 1):
                    self._onHistoryNext()
                    return True
            elif event.matches(QKeySequence.MoveToPreviousLine):
                if self._edit.cursorPosition[0] == 0:
                    self._onHistoryPrev()
                    return True
            elif event.matches(QKeySequence.MoveToNextPage) or \
                 event.matches(QKeySequence.MoveToPreviousPage):
                self._browser.keyPressEvent(event)
                return True
            elif event.matches(QKeySequence.InsertParagraphSeparator):
                 return self._editNewLineEvent()

        return QWidget.eventFilter(self, obj, event)

    def _appendToBrowser(self, style, text):
        """Convert text to HTML for inserting it to browser. Insert the HTML
        """
        text = cgi.escape(text)

        text = text.replace('\n', '<br/>')

        defBg = self._browser.palette().color(QPalette.Base)

        h, s, v, a = defBg.getHsvF()

        if style == 'out':
            pass
        elif style == 'in':
            if v > 0.5:  # white background
                v = v - (v / 8)  # make darker
            else:
                v = v + ((1 - v) / 4)  # make ligher
        elif style == 'err':
            if v < 0.5:  # dark background
                v = v + ((1 - v) / 4)  # make ligher

            h = 0
            s = .4
        elif style == 'hint':
            if v < 0.5:  # dark background
                v = v + ((1 - v) / 4)  # make ligher

            h = 0.33
            s = .4
        else:
            assert 0

        bg = QColor.fromHsvF(h, s, v)
        text = '<span style="background-color: %s;">%s</span>' % (bg.name(), text)

        scrollBar = self._browser.verticalScrollBar()
        oldValue = scrollBar.value()

        if False:
            # hlamer: It seems, it is more comfortable, if text is always scrolled
            scrollAtTheEnd = oldValue == scrollBar.maximum()
        else:
            scrollAtTheEnd = True

        self._browser.moveCursor(QTextCursor.End)
        self._browser.insertHtml(text)

        if scrollAtTheEnd:
            scrollBar.setValue(scrollBar.maximum())
        else:
            scrollBar.setValue(oldValue)

        while self._browser.document().characterCount() > 1024 * 1024:
            cursor = self._browser.cursorForPosition(QPoint(0, 0))
            cursor.select(cursor.LineUnderCursor)
            if not cursor.selectedText():
                cursor.movePosition(cursor.Down, cursor.KeepAnchor)
                cursor.movePosition(cursor.EndOfLine, cursor.KeepAnchor)
            cursor.removeSelectedText()

    def setLanguage(self, language):
        """Set highlighting language for input widget
        """
        self._edit.detectSyntax(language=language)

    def execCommand(self, text):
        """Save current command in the history. Append it to the log. Execute child's method. Clear edit line.
        """
        self._appendToBrowser('in', text + '\n')

        if len(self._history) < 2 or\
           self._history[-2] != text:  # don't insert duplicating items
            self._history.insert(-1, text)

        self._historyIndex = len(self._history) - 1

        self._history[-1] = ''
        self._edit.text = ''

        if not text.endswith('\n'):
            text += '\n'

        self.childExecCommand(text)

    def childExecCommand(self, text):
        """Reimplement in the child classes to execute enterred commands
        """
        pass

    def appendOutput(self, text):
        """Appent text to output widget
        """
        self._appendToBrowser('out', text)

    def appendError(self, text):
        """Appent error text to output widget. Text is drawn with red background
        """
        self._appendToBrowser('err', text)

    def appendHint(self, text):
        """Appent error text to output widget. Text is drawn with red background
        """
        self._appendToBrowser('hint', text)

    def clear(self):
        """Clear the widget"""
        self._browser.clear()

    def isCommandComplete(self, text):
        """Executed when Enter is pressed to check if widget should execute the command, or insert newline.

        Implement this function in the child classes.
        """
        return True

    def _editNewLineEvent(self):
        """Handler of Enter pressing in the edit
        """
        text = self._edit.text

        if self.isCommandComplete(text):
            self.execCommand(text)
            return True # processing finished
        else:
            return False  # let the editor process the event

    def _onHistoryNext(self):
        """Down pressed, show next item from the history
        """
        if (self._historyIndex + 1) < len(self._history):
            self._historyIndex += 1
            self._edit.text = self._history[self._historyIndex]
            self._edit.absCursorPosition = len(self._edit.text)

    def _onHistoryPrev(self):
        """Up pressed, show previous item from the history
        """
        if self._historyIndex > 0:
            if self._historyIndex == (len(self._history) - 1):
                self._history[-1] = self._edit.text
            self._historyIndex -= 1
            self._edit.text = self._history[self._historyIndex]
            self._edit.absCursorPosition = len(self._edit.text)
