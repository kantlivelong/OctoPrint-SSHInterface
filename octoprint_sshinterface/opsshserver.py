# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 Shawn Bruce - Released under terms of the AGPLv3 License"

from twisted.conch import avatar, recvline
from twisted.conch.interfaces import IConchUser, ISession
from twisted.conch.ssh import factory, keys, session
from twisted.conch.insults import insults
from twisted.cred import portal, checkers, credentials
from twisted.internet import reactor, defer
from zope.interface import implementer
from base64 import decodebytes
import shlex


@implementer(portal.IRealm)
class OPSSHRealm(object):
    def __init__(self, commands):
        self.commands = commands

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IConchUser in interfaces:
            return interfaces[0], OPSSHAvatar(avatarId, self.commands), lambda: None
        else:
            raise NotImplementedError("No supported interfaces found.")


@implementer(checkers.ICredentialsChecker)
class OPSSHCredentialChecker(object):
    credentialInterfaces = (credentials.IUsernamePassword,)

    def __init__(self, plugin):
        self._OctoPrintSSH = plugin

    def requestAvatarId(self, credentials):
        username = credentials.username.decode()
        password = credentials.password.decode()

        if self._OctoPrintSSH._user_manager.check_password(username, password):
            user = self._OctoPrintSSH._user_manager.find_user(username)
            if user.is_active:
                self._OctoPrintSSH._logger.info("Accepted password for {} from xxx port xxx".format(username))
                return defer.succeed(credentials.username)

        self._OctoPrintSSH._logger.info("Failed password for {} from xxx port xxx".format(username))
        return defer.fail(credError.UnauthorizedLogin("Bad password"))

@implementer(checkers.ICredentialsChecker)
class OPSSHPublicKeyChecker(object):
    credentialInterfaces = (credentials.ISSHPrivateKey,)

    def __init__(self, plugin):
        self._OctoPrintSSH = plugin

    def requestAvatarId(self, credentials):
        username = credentials.username.decode()

        user = self._OctoPrintSSH._user_manager.find_user(username)
        if user.is_active:
            authorized_keys = self._OctoPrintSSH._user_manager.get_user_setting(username, ("plugins", "sshinterface", "authorized_keys"))

            for line in authorized_keys:
                key = line.split(' ')[1]
                key = bytes(key, 'ascii')

                try:
                    if decodebytes(key) == credentials.blob:
                        return defer.succeed(credentials.username)
                except:
                    continue

        return defer.fail(credError.UnauthorizedLogin("Invalid key"))

@implementer(ISession)
class OPSSHAvatar(avatar.ConchUser):
    def __init__(self, username, commands):
        avatar.ConchUser.__init__(self)
        self.username = username
        self.commands = commands
        self.windowSize = (0, 0, 0, 0)
        self.channelLookup.update({b'session': session.SSHSession})

    def openShell(self, protocol):
        serverProtocol = insults.ServerProtocol(OPSSHShell, self, self.commands)
        serverProtocol.makeConnection(protocol)
        protocol.makeConnection(session.wrapProtocol(serverProtocol))

    def getPty(self, terminal, windowSize, attrs):
        self.windowSize = windowSize
        return None

    def windowChanged(self, windowSize):
        self.windowSize = windowSize

    def execCommand(self, protocol, cmd):
        raise NotImplementedError()

    def closed(self):
        pass


class OPSSHShell(recvline.HistoricRecvLine):
    def __init__(self, avatar, commands):
        self._OctoPrintSSH = avatar.conn.transport._OctoPrintSSH
        self.avatar = avatar
        self.user = self._OctoPrintSSH._user_manager.find_user(avatar.username.decode())
        self.username = avatar.username
        self.pwd = '/'
        self.ps = '$'
        self.commands = {}
        for command in commands:
            self.commands[command._name_] = command
        self.running_command = None

    def handle_CTRL_C(self):
        if self.running_command:
            try:
                self.running_command.handle_CTRL_C()
            except NotImplementedError:
                pass

            self.killRunningCommand()
            self.showPrompt()

    def handle_CTRL_D(self):
        if self.running_command:
            try:
                self.running_command.handle_CTRL_D()
            except NotImplementedError:
                pass
        else:
            self.terminal.loseConnection()

    def handle_CTRL_L(self):
        if self.running_command:
            try:
                self.running_command.handle_CTRL_L()
            except NotImplementedError:
                pass
        else:
            self.terminal.reset()
            self.showPrompt()
            self.terminal.write(''.join(self.lineBuffer))

    def handle_CTRL_U(self):
        if self.running_command:
            try:
                self.running_command.handle_CTRL_U()
            except NotImplementedError:
                pass
        else:
            self.lineBuffer = []
            self.lineBufferIndex = 0
            self.terminal.eraseLine()
            self.terminal.cursorPos.x = 0
            self.terminal.cursorPosition(self.terminal.cursorPos.x, self.terminal.cursorPos.y)
            self.showPrompt()

    def connectionMade(self):
        recvline.HistoricRecvLine.connectionMade(self)

        self.keyHandlers.update({
            b'\x03': self.handle_CTRL_C,
            b'\x04': self.handle_CTRL_D,
            b'\x0c': self.handle_CTRL_L,
            b'\x15': self.handle_CTRL_U,
        })

    def connectionLost(self, reason):
        recvline.HistoricRecvLine.connectionLost(self, reason)

    def initializeScreen(self):
        self.terminal.reset()
        self.setInsertMode()
        self.terminal.write("Welcome!")
        self.terminal.nextLine()
        self.showPrompt()

    def showPrompt(self):
        self.terminal.write("[{}]{} ".format(self.pwd, self.ps))

    def lineReceived(self, line):
        line = line.decode()

        if self.running_command:
            try:
                self.running_command.lineReceived(line)
                return
            except NotImplementedError:
                pass

        args = shlex.split(line)
        if len(args):
            self.runCommand(args[0], *args)

        if not self.running_command:
            self.showPrompt()

    def keystrokeReceived(self, keyID, modifier):
        if self.running_command:
            try:
                self.running_command.keystrokeReceived(keyID, modifier)
                return
            except NotImplementedError:
                pass

        super(OPSSHShell, self).keystrokeReceived(keyID, modifier)

    def characterReceived(self, ch, moreCharactersComing):
        if self.running_command:
            try:
                self.running_command.characterReceived(ch, moreCharactersComing)
                return
            except NotImplementedError:
                pass

        super(OPSSHShell, self).characterReceived(ch, moreCharactersComing)

    def runCommand(self, command, *args):
        if command in self.commands:
            try:
                c = self.commands[command](self)
                r = c.main(*args)
                if r:
                    self.running_command = r
                    return
            except Exception as e:
                raise(e)
                self._OctoPrintSSH._logger.error("Exception while running command `{command}`.\n{e}".format(command=args[0], e=e))
                self.terminal.write("An unknown error occurred.")
                self.terminal.nextLine()
        else:
            self.terminal.write("No such command.")
            self.terminal.nextLine()

    def killRunningCommand(self):
        self.running_command.term()
        self.running_command = None
