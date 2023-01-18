#
#     Copyright (C) 2019-present Nathan Odle
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the Server Side Public License, version 1,
#     as published by MongoDB, Inc.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     Server Side Public License for more details.
#
#     You should have received a copy of the Server Side Public License
#     along with this program. If not, email mysteriousham73@gmail.com
#
#     As a special exception, the copyright holders give permission to link the
#     code of portions of this program with the OpenSSL library under certain
#     conditions as described in each individual source file and distribute
#     linked combinations including the program with the OpenSSL library. You
#     must comply with the Server Side Public License in all respects for
#     all of the code used other than as permitted herein. If you modify file(s)
#     with this exception, you may extend this exception to your version of the
#     file(s), but you are not obligated to do so. If you do not wish to do so,
#     delete this exception statement from your version. If you delete this
#     exception statement from all source files in the program, then also delete
#     it in the license file.

class Transmitters(dict):

    @property
    def selected_transmitter(self):
        if([a_transmitter for uuid, a_transmitter in self.items() if a_transmitter.selected]):
            return [a_transmitter for uuid, a_transmitter in self.items() if a_transmitter.selected][0]

    def select_transmitter_by_uuid(self, id):
        for uuid, alltransmitters in self.items():
            alltransmitters.selected = False

        transmitter_to_select = self[id]
        transmitter_to_select.selected = True
        selected_transmitter_text = transmitter_to_select.description + " (" + str(transmitter_to_select.uuid) + ")"

        print("TRANSMITTER SELECTED | " + selected_transmitter_text)

    def select_transmitter(self, transmitter):
        for uuid, alltransmitters in self.items():
            alltransmitters.selected = False

        transmitter_to_select = self[transmitter.uuid]
        transmitter_to_select.selected = True
        selected_transmitter_text = transmitter_to_select.description + " (" + str(transmitter_to_select.uuid) + ")"

        print("transmitter SELECTED | " + selected_transmitter_text)


class Transmitter(object):

    def __init__(self, data):

        self.uuid = ""
        self.description = ""
        self.alive = True
        self.type = ""
        self.uplink_low = 0
        self.uplink_high = 0
        self.uplink_drift = 0
        self.downlink_low = 0
        self.downlink_high = 0
        self.downlink_drift = 0
        self.mode = ""
        self.mode_id = 0
        self.uplink_mode = ""
        self.invert = False
        self.baud = 0.0
        self.norad_cat_id = 0
        self.status = "active"
        self.updated = ""
        self.citation = ""
        self.service = ""
        self.uplink_frequency = 0
        self.downlink_frequency = 0

        for name, value in data.items():
            setattr(self, name, self._wrap(value))

        if(self.uplink_low):
            self.uplink_frequency = self.uplink_low
        if (self.downlink_high):
            self.downlink_frequency = self.downlink_high
        #self.downlink_frequency = Frequency(self.uplink_high)

    @property
    def doppler_per_hz(self):
        return self.__doppler_per_hz

    @doppler_per_hz.setter
    def doppler_per_hz(self, doppler_per_hz):
        self.__doppler_per_hz = doppler_per_hz
        self.uplink_frequency.doppler_per_hz = doppler_per_hz
        self.downlink_frequency.doppler_per_hz = doppler_per_hz

    @property
    def range_rate(self):
        return self.__range_rate

    @range_rate.setter
    def range_rate(self, range_rate):
        c = 299792.458
        self.__range_rate = range_rate
        self.doppler_per_hz = -(self.range_rate / c)
        self.uplink_frequency.doppler_per_hz = self.doppler_per_hz
        self.downlink_frequency.doppler_per_hz = self.doppler_per_hz

    @property
    def uplink_frequency(self):
        return self.__uplink_frequency

    @uplink_frequency.setter
    def uplink_frequency(self, up_frequency):
        self.__uplink_frequency = Frequency(up_frequency)
        self.__uplink_frequency.freq_type = "uplink"

    @property
    def downlink_frequency(self):
        return self.__downlink_frequency

    @downlink_frequency.setter
    def downlink_frequency(self, down_frequency):
        self.__downlink_frequency = Frequency(down_frequency)
        self.__downlink_frequency.freq_type = "downlink"




    def _wrap(self, value):
        if isinstance(value, (tuple, list, set, frozenset)):
            return type(value)([self._wrap(v) for v in value])
        else:
            return Transmitter(value) if isinstance(value, dict) else value


class Frequency(int):

    def __init__(self, freq):
        self.c = 299792.458
        self.freq_type = ""
        self.range_rate = 0
        self.doppler_per_hz = 0
        self = freq

    def shift(self, frequency):
        return frequency * (self.range_rate / self.c)

    @property
    def shifted(self):
        if(self.freq_type == "uplink"):
            return self + self * self.doppler_per_hz
        if(self.freq_type == "downlink"):
            return self - self * self.doppler_per_hz
        else:
            return self



