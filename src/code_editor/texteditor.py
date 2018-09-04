
from . import syntax
from .text_partition import Lines, Selection
from ngsgui.widgets import ArrangeH, ArrangeV, ButtonArea
from .utils import LineNumberArea, PythonFileButtonArea
from ngsgui.thread import inmain_decorator, inthread

from PySide2 import QtWidgets, QtGui, QtCore


class CodeEditor(QtWidgets.QPlainTextEdit):
    def __init__(self, filename=None, gui=None, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.gui = gui
        self.filename = filename
        if filename:
            self.setWindowTitle(filename)
        else:
            self.setWindowTitle("unsaved file")

        # create ButtonArea
        self.buttonArea = PythonFileButtonArea(code_editor=self, parent=self)

        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.lineNumberArea.updateWidth)
        self.updateRequest.connect(self.lineNumberArea.update)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self._lines = Lines(self)
        if filename:
            with open(filename,"r") as f:
                txt = f.read()
        else:
            txt = ""
        self.highlighter = syntax.PythonHighlighter(self.document())
        self.text = txt
        self.highlightCurrentLine()
        def setTitleAsterix():
            if self.windowTitle()[0] != "*":
                self.setWindowTitle("* " + self.windowTitle())
        self.textChanged.connect(setTitleAsterix)

        self.comment_action = QtWidgets.QAction("Comment/Uncomment")
        def _comment():
            try:
                Selection(self).commentOrUncomment()
            except ValueError:
                self.selectCurrentLine()
                Selection(self).commentOrUncomment()
        self.comment_action.triggered.connect(_comment)
        self.comment_action.setShortcut(QtGui.QKeySequence("Ctrl+d"))
        self.addAction(self.comment_action)
        self.active_thread = None

    def search(self):
        TextFinder(self).show()

    def __getstate__(self):
        return (self.text,)

    def __setstate__(self,state):
        self.__init__()
        self.text = state[0]

    @property
    @inmain_decorator(wait_for_return=True)
    def text(self):
        return self.toPlainText()
    @text.setter
    @inmain_decorator(wait_for_return=True)
    def text(self, text):
        self.setPlainText(text)

    @property
    def lines(self):
        return self._lines

    def selectCurrentLine(self):
        cursor = self.textCursor()
        cursor.movePosition(cursor.StartOfLine)
        cursor.movePosition(cursor.EndOfLine, cursor.KeepAnchor)
        self.setTextCursor(cursor)

    def isGLWindow(self):
        return False

    @inmain_decorator(wait_for_return=False)
    def show_exception(self, e, lineno):
        self.gui.window_tabber.setCurrentWidget(self)
        self.setTextCursor(QtGui.QTextCursor(self.document().findBlock(self.computation_started_at)))
        for i in range(lineno-1):
            self.moveCursor(QtGui.QTextCursor.Down)
        self.msgbox = QtWidgets.QMessageBox(text = type(e).__name__ + ": " + str(e))
        self.msgbox.setWindowTitle("Exception caught!")
        self.msgbox.show()
        if self.gui._dontCatchExceptions:
            raise e

    def contextMenuEvent(self, event):
        # is there a selection
        menu = self.createStandardContextMenu()
        run_selection = menu.addAction("Run selection")
        try:
            selection = Selection(self)
        except ValueError:
            run_selection.setDisabled(True)
        run_selection.triggered.connect(lambda : self.run(str(selection), reset_exec_locals=False, computation_started_at=selection.start))
        menu.addAction(self.comment_action)
        menu.exec_(event.globalPos())

    def save(self):
        if not self.filename:
            self.saveAs()
            return
        if self.windowTitle()[0] == "*":
            with open(self.filename,"w") as f:
                f.write(self.text)
            self.setWindowTitle(self.windowTitle()[2:])

    def saveAs(self):
        filename, filt = QtWidgets.QFileDialog.getSaveFileName(caption="Save as",
                                                               filter=".py")
        self.filename = filename
        self.save()

    def run(self, code=None, reset_exec_locals = True, computation_started_at = 0):
        self.computation_started_at = computation_started_at
        if code is None:
            code = self.text
        if reset_exec_locals:
            self.clear_locals()
        def _run():
            try:
                exec(code,self.exec_locals)
            except Exception as e:
                import sys
                count_frames = 0
                tbc = sys.exc_info()[2]
                while tbc is not None:
                    tb = tbc
                    tbc = tb.tb_next
                self.show_exception(e,tb.tb_frame.f_lineno)
            self.active_thread = None
            self.gui.console.pushVariables(self.exec_locals)
        if self.active_thread:
            self.msgbox = QtWidgets.QMessageBox(text="Already running, please stop the other computation before starting a new one!")
            self.msgbox.setWindowTitle("Multiple computations error")
            self.msgbox.show()
            return
        self.active_thread = inthread(_run)

    def clear_locals(self):
        self.exec_locals = { "__name__" : "__main__" }

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QtCore.QRect(cr.left(), cr.top() + self.buttonAreaHeight(), self.lineNumberArea.width(), cr.height()))
        self.buttonArea.setGeometry(QtCore.QRect(cr.left(), cr.top(), cr.right(), self.buttonAreaHeight()))

    def buttonAreaHeight(self):
        return 35

    def highlightCurrentLine(self):
        selection = QtWidgets.QTextEdit.ExtraSelection()
        lineColor = QtGui.QColor(QtCore.Qt.yellow).lighter(160)
        selection.format.setBackground(lineColor)
        selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])
