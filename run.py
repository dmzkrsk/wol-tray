from _socket import  SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
from socket import socket
import struct
import sys
from PyQt4.QtCore import QSettings, QAbstractListModel, Qt, QVariant, QModelIndex, pyqtSignal, QRegExp
from PyQt4.QtGui import QDialog, QMainWindow, QIcon, QSystemTrayIcon, QMenu, QApplication, QDesktopWidget, QTreeView, QItemSelectionModel, QMessageBox, QRegExpValidator, QValidator, QCursor, QWidgetAction, QLabel, QAction
from ui_settings import Ui_wolsettings as Ui_Settings

VENDOR, APP = "the-island.ru", "woltray"

class Server(object):
    MAC = '00:00:00:00:00:00'
    PORT = 9
    BROADCAST = True

    def __init__(self, alias, mac=MAC, port=PORT, broadcast=BROADCAST):
        self.alias = alias
        self.mac = mac
        self.port = port
        self.broadcast = True

    def save(self, settings):
        """
        :type settings: QSettings
        :rtype: None
        """

        settings.setValue('alias', self.alias)
        settings.setValue('mac', self.mac)
        settings.setValue('port', self.port)
        settings.setValue('broadcast', self.broadcast)

    @classmethod
    def fromSettings(cls, settings, alias=None):
        alias = settings.value('alias', alias).toString()
        mac = settings.value('mac', cls.MAC).toString()
        port, _ = settings.value('port', cls.PORT).toInt()
        broadcast = settings.value('broadcast', cls.BROADCAST).toBool()

        return cls(alias, mac, port, broadcast)

class ServersModel(QAbstractListModel):
    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.servers = {}
        self.order = []

    def append(self, server):
        """
        :param server:
        :type Server:
        """

        l = len(self.servers)
        self.beginInsertRows(QModelIndex(), l, l)
        self.servers[server.alias] = server
        self.order.append(server.alias)
        self.endInsertRows()

        return self.index(l)

    def contains(self, alias):
        return alias in self.servers

    def rowCount(self, QModelIndex_parent=None, *args, **kwargs):
        return len(self.servers)

    def data(self, index, role):
        if index.isValid() and role == Qt.DisplayRole:
            alias = self.order[index.row()]
            return QVariant(alias)
        else:
            return QVariant()

    def index(self, row, col=0, parent=QModelIndex(), *args, **kwargs):
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()

        if col > 0:
            return QModelIndex()

        if row >= len(self.servers):
            return QModelIndex()

        return self.createIndex(row, 0, id(self.servers[self.order[row]]))

    def headerData(self, section, orientation, role=None):
        """
        :type orientation Qt.Orientation
        """

        if role != Qt.DisplayRole:
            return QVariant()

        if orientation == Qt.Horizontal:
            return "Hosts"
        else:
            return ''

    def delete(self, index):
        row = index.row()
        self.beginRemoveRows(QModelIndex(), row, row)
        alias = self.order[row]
        del self.servers[alias]
        del self.order[row]
        self.endRemoveRows()

    def update(self, index, callback):
        row = index.row()
        server = self.servers[self.order[row]]
        alias = server.alias
        idx = self.order.index(alias)
        callback(server)
        self.servers[server.alias] = self.servers.pop(alias)
        self.order[idx] = server.alias

        self.dataChanged.emit(index, index)


def centerOnScreen(w):
    resolution = QDesktopWidget().screenGeometry()
    w.move((resolution.width() / 2) - (w.frameSize().width() / 2),
        (resolution.height() / 2) - (w.frameSize().height() / 2))

class ServersView(QTreeView):
    pass

class ConfigDialog(QDialog):
    wake = pyqtSignal(object)
    serversChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.ui = Ui_Settings()
        self.ui.setupUi(self)

        self.autoUpdate = False

        self.ui.newServer.clicked.connect(self.addServer)

        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, VENDOR, APP)

        mac_re = QRegExp("([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")
        self.ui.macText.setValidator(QRegExpValidator(mac_re, self.ui.macText))

        self.ui.aliasText.textChanged.connect(self.enableSave)
        self.ui.portText.textChanged.connect(self.enableSave)
        self.ui.macText.textChanged.connect(self.enableSave)
        self.ui.macText.textChanged.connect(self.dropStyle)
        self.ui.asBroadcastCheck.stateChanged.connect(self.enableSave)

        self.ui.saveServer.clicked.connect(self.updateServer)
        self.ui.resetServer.clicked.connect(self.resetServer)
        self.ui.deleteServer.clicked.connect(self.deleteServer)
        self.ui.wakeServer.clicked.connect(self.wakeServer)

        self.serversModel = ServersModel()
        self.ui.serversView.setModel(self.serversModel)
        self.ui.serversView.selectionModel().selectionChanged.connect(self.serverChanged)

        servers = self.settings.beginReadArray("servers")
        for d in range(servers):
            self.settings.setArrayIndex(d)
            s = Server.fromSettings(self.settings, self.alias(d))
            self.serversModel.append(s)
        self.settings.endArray()

    def dropStyle(self):
        self.sender().setStyleSheet('color: auto')

    @classmethod
    def alias(cls, d):
        return 'New server %d' % d

    def addServer(self):
        d = 1
        while True:
            alias = self.alias(d)
            if not self.serversModel.contains(alias):
                break

            d += 1

        alias = self.alias(d)
        index = self.serversModel.append(Server(alias))
        self.saveServers()
        if index.isValid():
            self.ui.serversView.setFocus()
            sm = self.ui.serversView.selectionModel()
            sm.clear()
            sm.select(index, QItemSelectionModel.Rows|QItemSelectionModel.Select)

    def serverSelected(self):
        selected = [x for x in self.ui.serversView.selectionModel().selectedIndexes() if x.column() == 0 and x.isValid()]
        if not selected:
            return None

        return selected[0]

    def serverChanged(self, set, unset):
        selection = self.serverSelected()
        if not selection:
            self.ui.aliasText.setText('')
            self.ui.portText.setText('')
            self.ui.macText.setText('')
            self.ui.asBroadcastCheck.setChecked(False)

            self.ui.groupBox.setEnabled(False)
            self.ui.saveServer.setEnabled(False)
            self.ui.resetServer.setEnabled(False)
            self.ui.deleteServer.setEnabled(False)
            self.ui.wakeServer.setEnabled(False)
            return

        self.ui.groupBox.setEnabled(True)
        self.ui.saveServer.setEnabled(False)
        self.ui.resetServer.setEnabled(False)
        self.ui.deleteServer.setEnabled(True)
        self.ui.wakeServer.setEnabled(True)

        server = selection.internalPointer()
        self.setServer(server)

    def setServer(self, server):
        self.autoUpdate = True

        self.ui.aliasText.setText(server.alias)
        self.ui.portText.setText('%d' % server.port)
        self.ui.macText.setText(server.mac)
        self.ui.asBroadcastCheck.setChecked(server.broadcast)

        self.autoUpdate = False

    def enableSave(self):
        if not self.autoUpdate and self.serverSelected():
            self.ui.saveServer.setEnabled(True)
            self.ui.resetServer.setEnabled(True)

    def deleteServer(self):
        selection = self.serverSelected()
        if not selection:
            return

        server = selection.internalPointer()
        if QMessageBox.Yes != QMessageBox.question(self, 'Confirm action', 'Do you want to remove server "%s" from the list?' % server.alias, QMessageBox.Yes|QMessageBox.No):
            return

        self.ui.deleteServer.setEnabled(False)
        self.ui.serversView.model().delete(selection)

        self.saveServers()

    def wakeServer(self):
        selection = self.serverSelected()
        if not selection:
            return

        server = selection.internalPointer()

        self.wake.emit(server)

    def updateServer(self):
        selection = self.serverSelected()
        if not selection:
            return

        validator = self.ui.macText.validator()
        mac = self.ui.macText.text()
        state, pos = validator.validate(mac, 0)

        if state != QValidator.Acceptable:
            self.ui.macText.setStyleSheet('color: red')
            self.ui.macText.setFocus()
            self.ui.macText.setCursorPosition(len(mac))
            return

        self.ui.saveServer.setEnabled(False)
        self.ui.resetServer.setEnabled(False)

        def updateServer(server):
            server.alias = self.ui.aliasText.text()
            server.port = int(self.ui.portText.text())
            server.mac = mac
            server.broadcast = bool(self.ui.asBroadcastCheck.isChecked())

        self.ui.serversView.model().update(selection, updateServer)

        self.saveServers()

    def resetServer(self):
        selection = self.serverSelected()
        if not selection:
            return

        self.ui.saveServer.setEnabled(False)
        self.ui.resetServer.setEnabled(False)

        server = selection.internalPointer()
        self.setServer(server)

    def saveServers(self):
        self.settings.beginWriteArray("servers")
        model = self.ui.serversView.model()
        for d in range(model.rowCount()):
            self.settings.setArrayIndex(d)
            server = model.index(d).internalPointer()
            server.save(self.settings)
        self.settings.endArray()

        self.serversChanged.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, VENDOR, APP)

        self.setup = ConfigDialog(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.setup.setModal(True)
        centerOnScreen(self.setup)
        self.setup.wake.connect(self.wake)
        self.setup.serversChanged.connect(self.updateMenu)

        self.menuServers = []

        self.trayIcon = QSystemTrayIcon(QIcon("res/power.png"), self)
        self.trayIcon.activated.connect(self.activated)

        menu = QMenu()

        self.populateMenuFromSettings(menu)

        menu.addSeparator()

        self.setupAction = menu.addAction(QIcon('res/setup.png'), "Configure")
        self.setupAction.triggered.connect(self.setup.show)

        menu.addSeparator()

        exitAction = menu.addAction("Exit")
        exitAction.triggered.connect(self.close)

        self.trayIcon.setContextMenu(menu)

        self.trayIcon.setToolTip("Wake on LAN")

        self.trayIcon.show()

        servers = self.settings.beginReadArray("servers")
        self.settings.endArray()

        if not servers:
            self.setup.show()

    def populateMenuFromSettings(self, menu):
        """
        :type menu: QMenu
        """
        actions = menu.actions()
        before = actions[0] if actions else None

        title = QWidgetAction(menu)
        label = QLabel("Hosts")
        font = label.font()
        px = font.pointSize()
        font.setBold(True)
        font.setPointSize(px * 1.5)
        label.setFont(font)
        label.setMargin(4)
        label.setIndent(10)
        #        label.setStyleSheet("font-weight: bold; margin: 4px 2px; border-bottom: 2px solid black")
        title.setDefaultWidget(label)

        menu.insertAction(before, title)
        self.menuServers.append(title)

        servers = self.settings.beginReadArray("servers")
        for d in range(servers):
            self.settings.setArrayIndex(d)
            server = Server.fromSettings(self.settings)
            action = QAction(QIcon("res/server.png"), server.alias, menu)
            menu.insertAction(before, action)
            action.setData(server)
            action.triggered.connect(self.wakeFromMenu)
            self.menuServers.append(action)
        self.settings.endArray()

    def activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.setup()
        elif reason == QSystemTrayIcon.Trigger:
            menu = QMenu()
            self.populateMenuFromSettings(menu)
            menu.exec_(QCursor.pos())

    def updateMenu(self):
        menu = self.trayIcon.contextMenu()
        for action in self.menuServers:
            action.setData(None)
            menu.removeAction(action)

        self.populateMenuFromSettings(menu)

    def wakeFromMenu(self):
        action = self.sender()
        server = action.data().toPyObject()
        self.wake(server)

    def wake(self, server):
        if QMessageBox.Yes == QMessageBox.question(self, "Wake on LAN", "Wake %s?" % server.alias, QMessageBox.Yes|QMessageBox.No):
            magic = '\xFF' * 6
            bits = str(server.mac).split(':')
            machex = ''.join([struct.pack('B', (int(x, 16))) for x in bits])
            magic += machex * 16

            sock = socket(type=SOCK_DGRAM)
            if server.broadcast:
                sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            sock.sendto(magic, ('<broadcast>', server.port))
            sock.close()

            self.trayIcon.showMessage("Wake on LAN", "Magic packet was sent to %s" % server.alias, msecs=3000)

    def close(self):
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wake on LAN")
    app.setQuitOnLastWindowClosed(False)
    m = MainWindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()