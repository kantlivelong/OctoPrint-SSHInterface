$(function() {
    function SSHInterfaceViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0]
        self.loginState = parameters[1];
        self.settings = undefined;

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
        };
    }

    ADDITIONAL_VIEWMODELS.push([
        SSHInterfaceViewModel,
        ["settingsViewModel", "loginStateViewModel"],
        ["#settings_plugin_sshinterface"]
    ]);
});
