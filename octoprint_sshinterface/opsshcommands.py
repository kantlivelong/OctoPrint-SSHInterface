# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 Shawn Bruce - Released under terms of the AGPLv3 License"

import os
import asciichartpy
from octoprint.access.permissions import Permissions
from twisted.conch.insults import insults
from .opsshserver import OPSSHShell

class OPSSHCommand(object):
    _name_ = "commandname"
    _short_description_ = "Short helpful description"
    _description_ = """
    Detailed usage information.
    """

    def __init__(self, shell):
        self.shell = shell
        self.terminal = shell.terminal

    def help(self):
        self.terminal.write("{} - {}".format(self._name_, self._short_description_))
        self.terminal.nextLine()
        self.terminal.write("{}".format(self._description_))
        self.terminal.nextLine()

    def main(self, *args):
        self.help()

    def term(self):
        raise NotImplementedError()

    def handle_CTRL_C(self):
        raise NotImplementedError()

    def handle_CTRL_D(self):
        raise NotImplementedError()

    def handle_CTRL_L(self):
        raise NotImplementedError()

    def handle_CTRL_U(self):
        raise NotImplementedError()

    def lineReceived(self, line):
        raise NotImplementedError()

    def keystrokeReceived(self, keyID, modifier):
        raise NotImplementedError()

    def characterReceived(self, ch, moreCharactersComing):
        raise NotImplementedError()
available_commands = []


class OPSSHCommand_help(OPSSHCommand):
    _name_ = "help"
    _short_description_ = "Provides a list of available commands."
    _description_ = """
    help [command]
    """

    def main(self, *args):
        if len(args) == 2:
            if self.shell.commands.has_key(args[1]):
                commands = {args[1]: self.shell.commands[args[1]]}
            else:
                self.terminal.write("No help entry for {}".format(args[1]))
                self.terminal.nextLine()
                return
        else:
            commands = self.shell.commands

        padding = len(max(commands.keys(), key=len)) + 1
        for n in sorted(commands.keys()):
            self.terminal.write("{name: <{padding}}- {short_description}".format(name=commands[n]._name_, padding=padding, short_description=commands[n]._short_description_))
            self.terminal.nextLine()

        if len(args) == 2:
            self.terminal.write("{description}".format(description=commands[args[1]]._description_))
            self.terminal.nextLine()
available_commands.append(OPSSHCommand_help)


class OPSSHCommand_quit(OPSSHCommand):
    _name_ = "quit"
    _short_description_ = "Disconnect from the current session."
    _description_ = ""

    def main(self, *args):
        self.terminal.loseConnection()
available_commands.append(OPSSHCommand_quit)


class OPSSHCommand_exit(OPSSHCommand_quit):
    _name_ = "exit"
available_commands.append(OPSSHCommand_exit)


class OPSSHCommand_logoff(OPSSHCommand_quit):
    _name_ = "logoff"
available_commands.append(OPSSHCommand_logoff)


class OPSSHCommand_version(OPSSHCommand):
    _name_ = "version"
    _short_description_ = "Displays the current OctoPrint and OctoPrint-SSH version."
    _description_ = ""

    def main(self, *args):
        from octoprint.server import DISPLAY_VERSION as OCTOPRINT_VERSION
        self.terminal.write("OctoPrint: %s" % OCTOPRINT_VERSION)
        self.terminal.nextLine()
        self.terminal.write("OctoPrint-SSH: %s" % self.shell._OctoPrintSSH._plugin_version)
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_version)


class OPSSHCommand_whoami(OPSSHCommand):
    _name_ = "whoami"
    _short_description_ = "Print effective userid"
    _description_ = ""

    def main(self, *args):
        self.terminal.write(self.shell.username)
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_whoami)


class OPSSHCommand_echo(OPSSHCommand):
    _name_ = "echo"
    _short_description_ = "Display a line of text"
    _description_ = """
    echo [STRING]
    """

    def main(self, *args):
        self.terminal.write(' '.join(args[1::]))
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_echo)


class OPSSHCommand_clear(OPSSHCommand):
    _name_ = "clear"
    _short_description_ = "Clear the terminal screen"
    _description_ = ""

    def main(self, *args):
        self.terminal.reset()
available_commands.append(OPSSHCommand_clear)


class OPSSHCommand_pwd(OPSSHCommand):
    _name_ = "pwd"
    _short_description_ = "print name of current/working directory"
    _description_ = ""

    def main(self, *args):
        self.terminal.write(self.shell.pwd)
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_pwd)


class OPSSHCommand_cd(OPSSHCommand):
    _name_ = "cd"
    _short_description_ = "change the current working directory"
    _description_ = """
    cd [DIRECTORY]
    """

    def main(self, *args):
        if len(args) == 1:
            path = self.shell.pwd
        elif len(args) == 2:
            path = args[1]
        elif len(args) > 2:
            self.terminal.write("cd: too many arguments")
            self.terminal.nextLine()
            return

        #FIXME: setting to unicode makes work on py2 but still breaks on py3. whats the best way?
        #path = unicode(path)

        if path[0] != '/':
            path = os.path.join(self.shell.pwd, path)

        if self.shell._OctoPrintSSH.vfs.isdir(path):
            self.shell.pwd = self.shell._OctoPrintSSH.vfs.validatepath(path)
        else:
            self.terminal.write("cd: no such file or directory: {}".format(path))
            self.terminal.nextLine()
available_commands.append(OPSSHCommand_cd)


class OPSSHCommand_ls(OPSSHCommand):
    _name_ = "ls"
    _short_description_ = "list directory contents"
    _description_ = """
    ls [FILE]
    """

    def main(self, *args):
        if len(args) == 1:
            paths = [self.shell.pwd]
        elif len(args) >= 2:
            paths = list(args[1::])

        for path in paths:
            #FIXME: setting to unicode makes work on py2 but still breaks on py3. whats the best way?
            #path = unicode(path)

            if path[0] != '/':
                path = os.path.join(self.shell.pwd, path)

            if self.shell._OctoPrintSSH.vfs.isdir(path):
                if len(args) > 2:
                    self.terminal.write("{}:".format(path))
                    self.terminal.nextLine()
                for i in self.shell._OctoPrintSSH.vfs.listdir(path):
                    self.terminal.write(i)
                    self.terminal.nextLine()
            elif self.shell._OctoPrintSSH.vfs.isfile(path):
                self.terminal.write(path)
                self.terminal.nextLine()
            else:
                self.terminal.write("ls: cannot access '{}': No such file or directory".format(path))
                self.terminal.nextLine()

            if len(paths) > 1:
                self.terminal.nextLine()
available_commands.append(OPSSHCommand_ls)


class OPSSHCommand_cat(OPSSHCommand):
    _name_ = "cat"
    _short_description_ = "concatenate files and print to output"
    _description_ = """
    cat [FILE]
    """

    def main(self, *args):
        if len(args) == 1:
            paths = [self.shell.pwd]
        elif len(args) >= 2:
            paths = list(args[1::])

        for path in paths:
            #FIXME: setting to unicode makes work on py2 but still breaks on py3. whats the best way?
            #path = unicode(path)

            if path[0] != '/':
                path = os.path.join(self.shell.pwd, path)

            if self.shell._OctoPrintSSH.vfs.isdir(path):
                self.terminal.write("cat: {}: Is a directory".format(path))
                self.terminal.nextLine()
            else:
                try:
                    with self.shell._OctoPrintSSH.vfs.open(path) as f:
                        self.terminal.write(f.read())
                except Exception:
                    self.terminal.write("cat: {}: No such file".format(path))
                    self.terminal.nextLine()
available_commands.append(OPSSHCommand_cat)


class OPSSHCommand_terminal(OPSSHCommand):
    _name_ = "terminal"
    _short_description_ = "Enter the OctoPrint terminal interface."
    _description_ = ""

    def __init__(self, protocol):
        self.ps = '>'
        super(OPSSHCommand_terminal, self).__init__(protocol)

    def main(self, *args):
        if not Permissions.MONITOR_TERMINAL in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        self.terminal.reset()
        self.terminal.write("Entering terminal mode. Press CTRL+C to exit.")
        self.terminal.nextLine()
        self.showPrompt()
        self.terminal.write(''.join(self.shell.lineBuffer))

        with self.shell._OctoPrintSSH._terminal_cbs_mutex:
            self.shell._OctoPrintSSH._terminal_cbs[self.shell.avatar.conn.transport.transport.sessionno] = self._write_printer_log

        return self

    def term(self):
        self.shell.lineBuffer = []
        self.shell.lineBufferIndex = 0
        self.terminal.eraseLine()
        self.terminal.cursorPos.y = self.shell.avatar.windowSize[0] - 1
        self.terminal.cursorPos.x = 0
        self.terminal.cursorPosition(self.terminal.cursorPos.x, self.terminal.cursorPos.y)
        with self.shell._OctoPrintSSH._terminal_cbs_mutex:
            try:
                self.shell._OctoPrintSSH._terminal_cbs.pop(self.shell.avatar.conn.transport.transport.sessionno, None)
            except:
                pass

    def handle_CTRL_L(self):
        self.terminal.reset()
        self.terminal.cursorPos.y = self.shell.avatar.windowSize[0] - 1
        self.terminal.cursorPosition(self.terminal.cursorPos.x, self.terminal.cursorPos.y)
        self.showPrompt()
        self.terminal.write(''.join(self.shell.lineBuffer))

    def handle_CTRL_U(self):
        self.shell.lineBuffer = []
        self.shell.lineBufferIndex = 0
        self.terminal.eraseLine()
        self.terminal.cursorPos.x = 0
        self.showPrompt()

    def lineReceived(self, line):
        if not Permissions.CONTROL in self.shell.user.effective_permissions:
            return

        self.terminal.eraseLine()
        self.terminal.write('\r')
        self.shell._OctoPrintSSH._printer.commands(line)

    def keystrokeReceived(self, keyID, modifier):
        if not Permissions.CONTROL in self.shell.user.effective_permissions and keyID == u'\r':
            return

        super(OPSSHShell, self.shell).keystrokeReceived(keyID, modifier)

    def characterReceived(self, ch, moreCharactersComing):
        if not Permissions.CONTROL in self.shell.user.effective_permissions:
            return

        super(OPSSHShell, self.shell).characterReceived(ch, moreCharactersComing)

    def showPrompt(self):
        self.terminal.saveCursor()
        self.terminal.cursorPos.y = self.shell.avatar.windowSize[0] - 1
        self.terminal.cursorPosition(self.terminal.cursorPos.x, self.terminal.cursorPos.y)
        self.terminal.write("{} ".format(self.ps))

    def _write_printer_log(self, line):
        self.terminal.eraseLine()
        self.terminal.nextLine()
        self.terminal.cursorUp()
        self.terminal.write(line)
        self.terminal.nextLine()
        self.terminal.write('> ' + ''.join(self.shell.lineBuffer))
available_commands.append(OPSSHCommand_terminal)


class OPSSHCommand_status(OPSSHCommand):
    _name_ = "status"
    _short_description_ = "Displays the current OctoPrint status information."
    _description_ = ""

    def main(self, *args):
        if not Permissions.STATUS in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        data = self.shell._OctoPrintSSH._printer.get_current_data()

        self.terminal.write("State: {}".format(data['state']['text']))
        self.terminal.nextLine()

        self.terminal.write("File: {}".format(data['job']['file']['name']))
        self.terminal.nextLine()

        if data['progress']['printTime']:
            progress_printTime = data['progress']['printTime']
        else:
            progress_printTime = '-'
        self.terminal.write("Print Time: {}".format(progress_printTime))
        self.terminal.nextLine()

        if data['progress']['printTimeLeft']:
            progres_printTimeLeft = data['progress']['printTimeLeft']
        else:
            progres_printTimeLeft = '-'
        self.terminal.write("Print Time Left: {}".format(progres_printTimeLeft))
        self.terminal.nextLine()

        if data['progress']['filepos']:
            progress_filepos = data['progress']['filepos']
        else:
            progress_filepos = '-'
        if data['job']['file']['size']:
            job_file_filepos = data['job']['file']['size']
        else:
            job_file_filepos = '-'
        self.terminal.write("Printed: {} / {}".format(progress_filepos, job_file_filepos))
        self.terminal.nextLine()

        self.terminal.nextLine()
available_commands.append(OPSSHCommand_status)


class OPSSHCommand_print(OPSSHCommand):
    _name_ = "print"
    _short_description_ = "Print specified gcode file."
    _description_ = """
    print [FILE]
    """

    def main(self, *args):
        if not Permissions.PRINT in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        if len(args) == 1:
            self.help()
            return
        elif len(args) == 2:
            path = args[1]
        elif len(args) > 2:
            self.terminal.write("print: too many arguments")
            self.terminal.nextLine()
            return

        #FIXME: setting to unicode makes work on py2 but still breaks on py3. whats the best way?
        #path = unicode(path)

        if path[0] != '/':
            path = os.path.join(self.shell.pwd, path)

        if not self.shell._OctoPrintSSH.vfs.isfile(path):
            self.terminal.write("print: {}: No such file".format(path))
            self.terminal.nextLine()
            return


        data = self.shell._OctoPrintSSH._printer.get_current_data()

        #TODO: Reevaluate the logic here.
        if data['state']['flags']['printing'] or data['state']['flags']['paused']:
            self.terminal.write("Already printing.")
            self.terminal.nextLine()
            return

        try:
            self.shell._OctoPrintSSH._printer.select_file(self.shell._OctoPrintSSH.vfs.getsyspath(path), False, printAfterSelect=True)
        except Exception:
            self.terminal.write("Error printing.")
            self.terminal.nextLine()
available_commands.append(OPSSHCommand_print)


class OPSSHCommand_cancel(OPSSHCommand):
    _name_ = "cancel"
    _short_description_ = "Cancels running print job."
    _description_ = ""

    def main(self, *args):
        if not Permissions.PRINT in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        data = self.shell._OctoPrintSSH._printer.get_current_data()

        #TODO: Reevaluate the logic here.
        if data['state']['flags']['printing'] or data['state']['flags']['paused']:
            self.shell._OctoPrintSSH._printer.cancel_print()
            self.terminal.write("ok")
        else:
            self.terminal.write("not printing")

        self.terminal.nextLine()
available_commands.append(OPSSHCommand_cancel)


class OPSSHCommand_pause(OPSSHCommand):
    _name_ = "pause"
    _short_description_ = "Pauses running print job."
    _description_ = ""

    def main(self, *args):
        if not Permissions.PRINT in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        data = self.shell._OctoPrintSSH._printer.get_current_data()

        #TODO: Reevaluate the logic here.
        if data['state']['flags']['printing']:
            self.shell._OctoPrintSSH._printer.pause_print()
            self.terminal.write("ok")
        elif data['state']['flags']['paused']:
            self.terminal.write("already paused")
        else:
            self.terminal.write("not printing")

        self.terminal.nextLine()
available_commands.append(OPSSHCommand_pause)


class OPSSHCommand_resume(OPSSHCommand):
    _name_ = "resume"
    _short_description_ = "Resumes a paused print job."
    _description_ = ""

    def main(self, *args):
        if not Permissions.PRINT in self.shell.user.effective_permissions:
            self.terminal.write("Access denied.")
            self.terminal.nextLine()
            return

        data = self.shell._OctoPrintSSH._printer.get_current_data()

        #TODO: Reevaluate the logic here.
        if data['state']['flags']['paused']:
            self.shell._OctoPrintSSH._printer.resume_print()
            self.terminal.write("ok")
        elif data['state']['flags']['printing']:
            self.terminal.write("already printing")
        else:
            self.terminal.write("not paused")

        self.terminal.nextLine()
available_commands.append(OPSSHCommand_resume)

'''
class OPSSHCommand_gettemp(OPSSHCommand):
    _name_ = "gettemp"
    _short_description_ = "Get current temperature information."
    _description_ = ""

    #TODO: This should respect printer profile settings and should be displayed a bit nicer.
    def main(self, *args):
        output_format = u"|{name: ^10}|{actual: ^8}|{target: ^7}|{offset: ^7}|"
        self.terminal.write(output_format.format(name='Name', actual='Actual', target='Target', offset='Offset'))
        self.terminal.nextLine()
        for name, data in self.shell._OctoPrintSSH._printer.get_current_temperatures().items():
            if not data['actual']:
                continue

            try:
                self.terminal.write(output_format.format(name=name,
                                                         actual=u"{}°C".format(data['actual']),
                                                         target=u"{}°C".format(data['target']),
                                                         offset=u"{}°C".format(data['offset'])))
            except Exception as e:
                raise(e)

            self.terminal.nextLine()
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_gettemp)
'''

'''
class OPSSHCommand_settemp(OPSSHCommand):
    _name_ = "settemp"
    _short_description_ = "Set target temperature for a given heater."
    _description_ = """
    settemp [TOOL] [TARGET]
    """

    def main(self, *args):
        self.terminal.write("NOT YET IMPLEMENTED")
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_settemp)
'''

'''
class OPSSHCommand_graphtemp(OPSSHCommand):
    _name_ = "graphtemp"
    _short_description_ = "Display temperature history graph."
    _description_ = ""

    def main(self, *args):
        temps = (self.shell._OctoPrintSSH._printer.get_temperature_history())._data

        default_symbols = ['┼', '┤', '╶', '╴', '─', '╰', '╭', '╮', '╯', '│']
        symbols = []
        series = []
        for temp in temps:
            for s in default_symbols:
                symbols.append(b'\x1b[35m{}\x1b[0m'.format(s))
            series.append(temp['bed']['actual'])


        self.terminal.write(asciichartpy.plot(series[-50::], {'height': 12, 'format': '{:3.1f}', 'symbols': symbols}))
        #self.terminal.write(b'\x1b[0m')
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_graphtemp)
'''

'''
class OPSSHCommand_control(OPSSHCommand):
    _name_ = "control"
    _short_description_ = "Interactive control of printer movement."
    _description_ = ""

    def main(self, *args):
        self.terminal.reset()
        self.terminal.write("Axis Movement Amount: 10")
        self.terminal.nextLine()
        self.terminal.write("Tool Movement Amount: 5mm")
        self.terminal.nextLine()
        self.terminal.nextLine()
        self.terminal.nextLine()
        self.terminal.write("X <        : A | Left Arrow")
        self.terminal.nextLine()
        self.terminal.write("X >        : D | Right Arrow")
        self.terminal.nextLine()
        self.terminal.write("Y <        : S | Down Arrow")
        self.terminal.nextLine()
        self.terminal.write("Y >        : W | UP Arrow")
        self.terminal.nextLine()
        self.terminal.write("Home X     : X")
        self.terminal.nextLine()
        self.terminal.write("Home Y     : Y")
        self.terminal.nextLine()
        self.terminal.write("Home Z     : Z")
        self.terminal.nextLine()
        self.terminal.write("Home All   : H | Home")
        self.terminal.nextLine()
        self.terminal.write("Toggle Fan : F")
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_control)
'''

'''
class OPSSHCommand_useradd(OPSSHCommand):
    _name_ = "useradd"
    _short_description_ = "Create a new user."
    _description_ = ""

    def main(self, *args):
        self.terminal.write("NOT YET IMPLEMENTED")
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_useradd)
'''

'''
class OPSSHCommand_userdel(OPSSHCommand):
    _name_ = "userdel"
    _short_description_ = "Delete an existing user."
    _description_ = ""

    def main(self, *args):
        self.terminal.write("NOT YET IMPLEMENTED")
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_userdel)
'''

'''
class OPSSHCommand_userlist(OPSSHCommand):
    _name_ = "userlist"
    _short_description_ = "List users."
    _description_ = ""

    def main(self, *args):
        self.terminal.write("NOT YET IMPLEMENTED")
        self.terminal.nextLine()
available_commands.append(OPSSHCommand_userlist)
'''

