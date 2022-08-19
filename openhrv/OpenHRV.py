import sys
from PySide6.QtWidgets import QApplication
from view import View
from model import Model


class Application(QApplication):
    def __init__(self, sys_argv):
        super(Application, self).__init__(sys_argv)
        self._model = Model()
        self._view = View(self._model)

def main():
    app = Application(sys.argv)
    app._view.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
