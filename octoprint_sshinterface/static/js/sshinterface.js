$(function() {
    function SSHInterfaceViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0]
        self.loginState = parameters[1];
        self.settings = undefined;
        self.usersettings = parameters[2]
        self.authorized_keys = ko.observable(undefined);

        self.usersettings.currentUser.subscribe(function (newUser) {
            if (newUser !== undefined) {
                self.authorized_keys(newUser.settings.plugins.sshinterface.authorized_keys.join('\n'));
            }
        });

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
        };

        self.onUserSettingsBeforeSave = function() {
            var settings = {
                plugins: {
                    sshinterface: {
                        authorized_keys: self.authorized_keys().split('\n')
                    }
                }
            };

            self.usersettings.updateSettings(self.usersettings.currentUser().name, settings);
            //self.usersettings.settings.plugins.sshinterface.authorized_keys("zzz");
            console.log("TEST onUserSettingsBeforeSave");
        }
    }

    ADDITIONAL_VIEWMODELS.push([
        SSHInterfaceViewModel,
        ["settingsViewModel", "loginStateViewModel", "userSettingsViewModel"],
        ["#settings_plugin_sshinterface", "#usersettings_plugin_sshinterface"]
    ]);
});
