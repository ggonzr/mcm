#!/usr/bin/env python

import tools.settings as settings
from json_layer.json_base import json_base
from copy import deepcopy


class sequence(json_base):

    _json_base__schema = settings.get_value('cmsdriver_options')

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        self._json_base__schema = settings.get_value('cmsdriver_options')

        # how to get the options ?
        # in cmssw
        # import  Configuration.PyReleaseValidation.Options as opt
        # map( lambda s : s.replace('--','') ,opt.parser._long_opt.keys() )

        # update self according to json_input
        self.__update(json_input)
        self.__validate()

    def __validate(self):
        if not self._json_base__json:
            return
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)

    # for all parameters in json_input store their values
    # in self._json_base__json
    def __update(self, json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = deepcopy(self._json_base__schema)
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = deepcopy(self._json_base__schema[key])

    def srepr(self, arg):
        if isinstance(arg, str):  # Python 3: isinstance(arg, str)
            # INFO: <class: str> uses UTF-8 as default
            return arg
        elif isinstance(arg, int):  # in case we have int we should make it string for cmsDriver construction
            return str(arg)
        try:
            return ",".join(self.srepr(x) for x in arg)
        except TypeError:  # catch when for loop fails
            # INFO: I assume this is a <class: str> right?
            return arg  # not a sequence so just return repr

    def to_command_line(self, attribute):
        if attribute == 'index':
            return ''
        value = self.get_attribute(attribute)
        if isinstance(value, str) and not value.strip():
            return ''
        if attribute == 'nThreads':
            if isinstance(value, str) and not value.isdigit():
                return ''
            if int(value) <= 1:
                return ''
        if attribute == 'nStreams':
            if isinstance(value, str) and not value.isdigit():
                return ''
            if int(value) <= 0:
                return ''

        if value == True:
            return "--" + str(attribute)
        elif value == False:
            return ''
        elif attribute == 'extra' and value.strip():
            return value.strip()
        elif value:
            return "--" + attribute + " " + self.srepr(value)
        else:
            return ''

    def to_string(self):
        text = ''
        keys = list(self.json().keys())
        keys.sort()
        for key in keys:
            if key in []:
                continue
            text += key + str(self.get_attribute(key))
        return text

    def build_cmsDriver(self):
        # always MC in McM. better to say it
        command = '--mc '

        for key in self.json():
            if key == "inline_custom":
                if int(self.get_attribute(key)) == 0:  # if inline_custom is 0
                    continue  # means that cmssw might not have inline_custom support
            addone = self.to_command_line(key)
            # prevent from having over spaces
            if addone:
                command += addone
                command += ' '
        return command


if __name__ == '__main__':
    s = sequence()
    s.print_self()
