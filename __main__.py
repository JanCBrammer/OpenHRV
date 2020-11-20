import sys
#from PySide2.QtWidgets import QApplication
from PyQt5.QtWidgets import QApplication
from view import View
from model import Model
from pacer import Pacer


class Application(QApplication):
    def __init__(self, sys_argv):
        super(Application, self).__init__(sys_argv)
        self._model = Model()
        self._pacer = Pacer(self._model)
        self._view = View(self._model, self._pacer)


def main():
    app = Application(sys.argv)
    app._view.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
