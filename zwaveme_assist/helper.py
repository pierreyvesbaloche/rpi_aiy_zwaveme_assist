#!/usr/bin/env python
# Copyright 2017 Pierre-yves Baloche
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Helper class for ZAutomation API """
import abc
import io
import logging
import os
import json
import requests
import requests.auth as auth


class ZwaveMeHelper(object):
    """ Helper to access the ZAutomation API """

    LOG_LEVEL = logging.DEBUG

    logging.basicConfig(
        level=LOG_LEVEL,
        format="[%(asctime)s] %(levelname)s:%(name)s.%(funcName)s:%(message)s"
    )

    # noinspection SpellCheckingInspection
    DEFAULT_ZAUTOMATION_CREDENTIALS = '~/zaut_credentials.json'
    # noinspection SpellCheckingInspection
    ZAUTO_USER = "username"
    # noinspection SpellCheckingInspection
    ZAUTO_PWD = "password"
    # noinspection SpellCheckingInspection
    ZAUTO_URL = "server_url"
    BASE_ORDER = "Wave"

    def __init__(self, credential_file_path=DEFAULT_ZAUTOMATION_CREDENTIALS):
        """
        Constructor.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.log(logging.DEBUG, "Credential path:{!s} > {!s}".format(credential_file_path,
                                                                            os.path.expanduser(credential_file_path)))
        with io.open(os.path.expanduser(credential_file_path), 'r', encoding='utf8') as credential_file:
            self.credentials = json.load(credential_file)
        self._commands = None

    def __str__(self):
        """
        Object's textual description
        :return: str
        """
        self.logger.log(logging.DEBUG, "credentials({!s}:{!s}@{!s})".format(self.credentials[ZwaveMeHelper.ZAUTO_USER],
                                                                            self.credentials[ZwaveMeHelper.ZAUTO_PWD],
                                                                            self.credentials[ZwaveMeHelper.ZAUTO_URL]))
        return "It's me, {!s} !".format(self.__class__.__name__)

    def __init_commands__(self):
        """Initialise the set of commands"""
        self._commands = {}
        strategy = self.APIListLocationStrategy(self.credentials)
        rooms = strategy.apply()
        # Mandatory to trim the OFF command as google recognize only "of" and not "OFF"
        ac = [ZwaveMeHelper.APIDeviceActionStrategy.TURN_ON, ZwaveMeHelper.APIDeviceActionStrategy.TURN_OFF,
              ZwaveMeHelper.APIDeviceActionStrategy.TURN_OFF]
        ac_voc = [ZwaveMeHelper.APIDeviceActionStrategy.TURN_ON, ZwaveMeHelper.APIDeviceActionStrategy.TURN_OFF,
                  ZwaveMeHelper.APIDeviceActionStrategy.TURN_OFF[:-1]]
        action_map = {}
        action_strategy = self.APIDeviceActionStrategy(self.credentials)

        for room in rooms:
            switches = []
            for switch in room.switches:
                switches.append(switch)
            action_map[room.name] = switches

        for action_idx in range(len(ac)):
            for room in action_map.keys():
                for device in action_map[room]:
                    command = "{!s} {!s} {!s} in {!s}".format(self.BASE_ORDER, ac_voc[action_idx], device.name, room)\
                        .lower()
                    self.logger.log(logging.DEBUG, "New command '{!s}'".format(command))
                    self._commands[command] = [action_strategy, device, ac[action_idx]]

    def get_vocal_commands(self):
        """
        Retrieve the available vocal commands.
        :return: string
        """
        if self._commands is None:
            self.__init_commands__()
        return self._commands.keys()

    @staticmethod
    def clean_command(command):
        """
        Clean the command being given, if it is between simple quotes.
        :param command: The command to "clean"
        :return:
        """
        if command[:1] == "'" and command[-1:] == "'":
            return command[1:-1]
        return command

    def do_vocal_commands(self, order=None):
        """
        Perform the requested command.
        :return: bool
        """
        if self._commands is None:
            self.__init_commands__()

        cleaned_order = self.clean_command(order)
        try:
            todo = self._commands[cleaned_order]
            todo[0].apply([todo[1], todo[2]])
            return True
        except KeyError as ke:
            self.logger.log(logging.ERROR, "'{!s}' unknown.".format(ke))
        return False

    class AbstractAPIStrategy(metaclass=abc.ABCMeta):
        """
        Abstract strategy for all Blinkt animation strategy.
        """

        BASE_URL = "/ZAutomation/api/v1"

        # noinspection SpellCheckingInspection
        def __init__(self, zautomation_credentials, base_path, zautomation_protocol=requests.get):
            """
            Constructor.
            :param zautomation_credentials: The necessary credential information for the request.
            :type zautomation_credentials: dict
            :param base_path: The API method's path.
            :type base_path: string
            :param zautomation_protocol: The request method to use.
            :type zautomation_protocol: method
            """

            self._logger = logging.getLogger(self.__class__.__name__)
            self._credentials = zautomation_credentials
            self._protocol = zautomation_protocol
            self._url = base_path

        def __str__(self):
            """
            Object's textual description
            :return: str
            """
            return "It's strategy '{!s}'".format(self.__class__.__name__)

        @property
        def username(self):
            """
            Username required for ZAutomation access.
            :return: string
            """
            return self._credentials[ZwaveMeHelper.ZAUTO_USER]

        @property
        def password(self):
            """
            Password required for ZAutomation access.
            :return: string
            """
            return self._credentials[ZwaveMeHelper.ZAUTO_PWD]

        @property
        def server_url(self):
            """
            ZAutomation's server URL access.
            :return: string
            """
            return self._credentials[ZwaveMeHelper.ZAUTO_URL]

        @property
        def server_full_url(self):
            """
            ZAutomation's server URL access with the method included.
            :return: string
            """
            return self.server_url + self._url

        @property
        def method(self):
            return self._protocol

        @property
        def authentication(self):
            """
            Generate the required authentication.
            :return: requests.auth.HTTPBasicAuth
            """
            return auth.HTTPBasicAuth(self.username, self.password)

        @abc.abstractmethod
        def apply(self, param=None):
            """
            Perform the strategy's business.
            :param param: The strategy's request parameters
            :return: json
            """

    class ZAutomationDeviceList(object):
        """
        Collection of devices.
        """

        def __init__(self, data):
            """
            Constructor
            :param data: The collection's data
            """
            self.__dict__ = data

        def __str__(self):
            """
            Collection's textual description
            :return: string
            """
            return "'{!s}'".format(self.id)

    class ZAutomationDevice(object):
        """
        Device.
        """
        _ID = "deviceId"
        _NAME = "deviceName"

        def __init__(self, data):
            """
            Constructor
            :param data: The device's data
            """
            self.__dict__ = data
            self._components = None

        def __str__(self):
            """
            Device's textual description
            :return: string
            """
            return "'{!s}[{!s}]'".format(self.deviceName, self.deviceId)

        @property
        def name(self):
            """
            Device's name.
            :return: string
            """
            return self.deviceName

        @property
        def api_id(self):
            """
            Device's API compliant id.
            :return: string
            """
            return self.deviceId  # .replace("-", ":")

    class ZAutomationLocation(object):
        """
        Location object.
        """
        _SWITCHES = "devices_switchBinary"

        def __init__(self, data):
            """
            Constructor
            :param data: The location's data
            """
            self.__dict__ = data
            self._switches = None

        def __str__(self):
            """
            Location's textual description
            :return: string
            """
            return "'{!s}'".format(self.name)

        @property
        def name(self):
            return self.title

        @property
        def switches(self):
            if self._switches is None:
                self._switches = []
                # Get the list corresponding to the switches
                filtered_list_switches = list(devices for devices in self.namespaces if devices["id"] == self._SWITCHES)
                for raw_device in filtered_list_switches:
                    switches = ZwaveMeHelper.ZAutomationDeviceList(raw_device)
                    for raw_switch in switches.params:
                        device = ZwaveMeHelper.ZAutomationDevice(raw_switch)
                        self._switches.append(device)
            return self._switches

    class APIListLocationStrategy(AbstractAPIStrategy):
        """API request strategy for listing locations"""

        URL = "/locations"

        # noinspection SpellCheckingInspection
        def __init__(self, zautomation_credentials):
            """
            Constructor of the strategy in charge of requesting the list of devices.
            :param zautomation_credentials: The necessary connection information.
            """
            super().__init__(zautomation_credentials, self.BASE_URL + self.URL, requests.get)

        def apply(self, param=None):
            self._logger.log(logging.DEBUG, "Requested with {!s}/{!s}".format(self.server_full_url, str(param)))
            result = self.method(self.server_full_url, auth=self.authentication)
            result.raise_for_status()
            locations = []
            for raw_location in result.json()["data"]:
                locations.append(ZwaveMeHelper.ZAutomationLocation(raw_location))
            return locations

    class APIDeviceActionStrategy(AbstractAPIStrategy):
        """API request strategy for activating/deactivating device"""

        URL = "/devices/{!s}/command/{!s}"  # replace device id - by :
        TURN_ON = "on"
        TURN_OFF = "off"

        # noinspection SpellCheckingInspection
        def __init__(self, zautomation_credentials):
            """
            Constructor of the strategy in charge of requesting the list of devices.
            :param zautomation_credentials: The necessary connection information.
            """
            super().__init__(zautomation_credentials, self.BASE_URL + self.URL, requests.get)

        def apply(self, param=None):
            if param is not None:
                if isinstance(param[0], ZwaveMeHelper.ZAutomationDevice):
                    command = self.server_full_url.format(param[0].api_id, param[1])
                    self._logger.log(logging.DEBUG, "Requested with {!s}".format(command))
                    result = self.method(command, auth=self.authentication)
                    result.raise_for_status()
                else:
                    self._logger.log(logging.ERROR, "Wrong param provided : {!s}".format(param.__class__.__name__))
            else:
                self._logger.log(logging.ERROR, "No param provided")


def main():
    import time
    helper = ZwaveMeHelper()
    # noinspection SpellCheckingInspection
    googled_command = "'Wave on The Plug Switch in The Living Room'".lower()
    print(helper.clean_command(googled_command))
    for command in helper.get_vocal_commands():
        print(command)
    helper.do_vocal_commands(googled_command)
    time.sleep(3)
    helper.do_vocal_commands(googled_command.replace(" on ", " off "))

if __name__ == '__main__':
    main()
