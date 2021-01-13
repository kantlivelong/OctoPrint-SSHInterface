# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 Shawn Bruce - Released under terms of the AGPLv3 License"

import os
import time
import octoprint.plugin
from octoprint.server import user_permission
from octoprint.events import eventManager, Events
import threading
from twisted.conch.ssh import factory, keys
from twisted.cred import portal
from twisted.internet import reactor
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from fs.osfs import OSFS
from fs.mountfs import MountFS


from . import opsshserver, opsshcommands

class SSHInterface(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.EventHandlerPlugin,
                   octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self._ssh_thread = None
        self._terminal_cbs = {}
        self._terminal_cbs_mutex = threading.Lock()
        self._plugin_data_dir = ''
        self.vfs = None
        self.port = 0

    def on_settings_initialized(self):
        self._plugin_data_dir = self._settings.global_get_basefolder('data') + os.path.sep + 'sshinterface'
        if not os.path.isdir(self._plugin_data_dir):
            try:
                os.makedirs(self._plugin_data_dir)
            except:
                self._logger.error("Unable to create data directory! Path=%s" % self._plugin_data_dir)
                return

        self.private_key_file = self._plugin_data_dir + '/id_rsa'
        self.public_key_file = self._plugin_data_dir + '/id_rsa.pub'

        self.port = self._settings.get_int(["port"])
        self._logger.debug("port: %s" % self.port)

        self.vfs = MountFS()
        for basefolder in ['uploads', 'scripts', 'logs']:
            self.vfs.mount(basefolder, OSFS(self._settings.global_get_basefolder(basefolder)))

        self._ssh_thread = threading.Thread(target=self._run_ssh)
        self._ssh_thread.setDaemon(True)
        self._ssh_thread.start()

    def _load_ssh_keypair(self):
        with open(self.private_key_file, "rb") as f:
            privateBlob = f.read()
            privateKey = keys.Key.fromString(data=privateBlob)

        with open(self.public_key_file, "rb") as f:
            publicBlob = f.read()
            publicKey = keys.Key.fromString(data=publicBlob)

        return publicKey, privateKey

    def _create_ssh_keypair(self, key_size):
        key = rsa.generate_private_key(
            backend=crypto_default_backend(),
            public_exponent=65537,
            key_size=key_size
        )
        private_key = key.private_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PrivateFormat.TraditionalOpenSSL,
            crypto_serialization.NoEncryption())
        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH
        )

        # TODO: Set appropriate permissions
        with open(self.private_key_file, "w") as f:
            f.write(private_key)

        with open(self.public_key_file, "w") as f:
            f.write(public_key)


    def _run_ssh(self):
        sshFactory = factory.SSHFactory()
        sshFactory.services[b'ssh-userauth'] = opsshserver.OPSSHUserAuthServer

        sshFactory.portal = opsshserver.OPSSHPortal(opsshserver.OPSSHRealm(opsshcommands.available_commands))

        sshFactory.portal.registerChecker(opsshserver.OPSSHCredentialChecker(self))
        sshFactory.portal.registerChecker(opsshserver.OPSSHPublicKeyChecker(self))

        if not os.path.isfile(self.private_key_file) and not os.path.isfile(self.public_key_file):
            self._create_ssh_keypair(2048)

        pubKey, privKey = self._load_ssh_keypair()

        sshFactory.publicKeys = {b'ssh-rsa': pubKey}
        sshFactory.privateKeys = {b'ssh-rsa': privKey}

        sshFactory.protocol._OctoPrintSSH = self

        reactor.listenTCP(self.port, sshFactory)
        reactor.run(installSignalHandlers=0)

    def _on_printer_add_log(self, data):
        with self._terminal_cbs_mutex:
            for name, callback in self._terminal_cbs.items():
                try:
                    reactor.callFromThread(callback, data)
                except:
                    self._logger.exception("Error while processing callback for sessionno %s" % name)

    def on_event(self, event, payload):
        if event == Events.CONNECTED:
            cb = octoprint.printer.PrinterCallback()
            cb.on_printer_add_log = self._on_printer_add_log
            self._printer.register_callback(cb)


    def get_settings_defaults(self):
        return dict(
            port = 2222
        )

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True),
            dict(type="usersettings", custom_bindings=True)
        ]

    def get_assets(self):
        return {
            "js": ["js/sshinterface.js"]
        }

    def get_update_information(self):
        return dict(
            tcpterminal=dict(
                displayName="SSH Interface",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kantlivelong",
                repo="OctoPrint-SSHInterface",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/kantlivelong/OctoPrint-SSHInterface/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "SSH Interface"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SSHInterface()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
