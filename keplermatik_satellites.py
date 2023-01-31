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

import json
import os

import numpy as np
import pickle
import re
import warnings

import skyfield.positionlib
from skyfield.api import EarthSatellite, load, wgs84

import satnogs_network
from keplermatik_transmitters import Transmitters


class Satellites(dict):

    def __init__(self):
        super(Satellites, self).__init__()
        self.offline_flag = True
        self.tle_source = ""
        self.cleaned_up_satellites = []
        self.not_found_satellites = []
        self.satnogs_tle_satellites = []

        current_tles = ""

        satnogs = satnogs_network.SatnogsClient(self)

        if not self.offline_flag:
            satnogs.get_satellites()
            self.tle_source = "tle.txt"
            self.cleanup_satellites()

            for norad_cat_id, satellite in self.items():
                current_tles += satellite.tle.tle_lines[0] + "\r\n" + \
                                satellite.tle.tle_lines[1] + "\r\n" + \
                                satellite.tle.tle_lines[2] + "\r\n"

            with open('tle_cache.txt', 'wb') as file:
                file.write(bytes(current_tles, "UTF-8"))
        else:
            satnogs.get_satellites(offline=True)
            self.tle_source = "tle_cache.txt"
            self.cleanup_satellites()

        print("LOADING TLEs | " + str(len(self)) + " SATELLITES")
        for norad_cat_id, satellite in self.items():
            satellite.load_tle(self.tle_source)

    def get_by_name(self, name):
        by_name = {sat.name: sat for sat in self.items()}
        satellite = by_name[name]
        print(satellite)

    def cleanup_satellites(self):
        satellites_to_delete = []
        no_tle_count = 0
        not_orbiting_count = 0

        if self.offline_flag == 1:
            if os.path.isfile('cleanup_cache'):
                with open('cleanup_cache', ) as fp:
                    satellites_to_delete = json.load(fp)

                print("CLEANING UP INVALID SATELLITES | " + str(len(satellites_to_delete)) + " INVALID SATELLITES IN CACHE")

                for satellite_to_delete in satellites_to_delete:
                    for satellite in [satellite for satellite in self if satellite == satellite_to_delete]: del (
                        self[int(satellite_to_delete)])

        else:
            print("CLEANING UP INVALID SATELLITES | ANALYZING " + str(len(self)) + " SATELLITES")

            for norad_cat_id, satellite in self.items():
                satellite.load_tle(self.tle_source)
                if not satellite.tle.exists:
                    satellites_to_delete.append(norad_cat_id)
                    no_tle_count = no_tle_count + 1
                    self.cleaned_up_satellites.append(norad_cat_id)

            for satellite_to_delete in satellites_to_delete:
                for satellite in [satellite for satellite in self if satellite == satellite_to_delete]:
                    del self[int(satellite_to_delete)]

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                for norad_cat_id, satellite in self.items():
                    satellite.update_current_prediction()

                    if wgs84.height_of(satellite.geocentric).m <= 0:
                        satellites_to_delete.append(norad_cat_id)
                        self.cleaned_up_satellites.append(norad_cat_id)
                        not_orbiting_count = not_orbiting_count + 1

            with open('cleanup_cache', 'w') as fp:
                json.dump(satellites_to_delete, fp)

            for satellite_to_delete in satellites_to_delete:
                for satellite in [satellite for satellite in self if satellite == satellite_to_delete]: del (
                    self[int(satellite_to_delete)])

            print("CLEANED UP " + str(no_tle_count + not_orbiting_count) + " SATELLITES | " + str(
                no_tle_count) + " WITHOUT TLE / " + str(not_orbiting_count) + " NOT ORBITING")

            with open('satellite_cache', 'wb') as fp:
                pickle.dump(satellites_to_delete, fp)


class Prediction:

    def __init__(self):
        self.timescale = None
        self.range_rate = 0
        self.norad_cat_id = 0
        self.elevation = 0
        self.geocentric = skyfield.positionlib.Geocentric([0.0, 0.0, 0.0])
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.position = 0.0
        self.elevation = 0.0
        self.azimuth = 0.0
        self.range = 0.0
        self.speed = 0.0
        self.velocity = [0.0, 0.0, 0.0]


class Satellite(object):

    def __init__(self, data):

        self.sat = None
        self.name = ""
        self.range_rate = 0
        self.transmitters = Transmitters()
        self.elevation = 0
        self.norad_cat_id = 0
        self.geocentric = None
        self.latitude = None
        self.longitude = None
        self.altitude = 0.0
        self.position = 0.0
        self.elevation = 0.0
        self.azimuth = 0.0
        self.range = 0.0
        self.speed = 0.0
        self.velocity = []

        self.current_time_resolution = 1

        self.passes = []

        # This and _wrap allow the user to access any SATNOGS data as part of the Satellite object by wrapping the
        # SATNOGS object parameters.

        for name, value in data.items():
            setattr(self, name, self._wrap(value))

        self.tle = TLE(self.norad_cat_id)

    def _wrap(self, value):
        if isinstance(value, (tuple, list, set, frozenset)):
            return type(value)([self._wrap(v) for v in value])
        else:
            return Satellite(value) if isinstance(value, dict) else value

    def load_tle(self, filename):
        self.tle.load_tle(filename)

    def tle_exists(self, filename):
        self.tle.load_tle(filename)
        return self.tle.exists

    @property
    def doppler_per_hz(self):
        c = 299792.458
        return -(self.range_rate / c)

    def predict_now(self, observer_latitude, observer_longitude):
        ts = load.timescale()
        timescale = ts.now()
        self.predict(timescale, observer_latitude, observer_longitude)

    def predict_gmtime(self, this_gmtime):
        ts = load.timescale()
        # utc(self, year, month=1, day=1, hour=0, minute=0, second=0.0):
        hours = np.arange(0, 23, 1 / 60)
        # minutes = np.arange(0, 2, (1))
        # tscale = ts.utc(this_gmtime[0], this
        # _gmtime[1], this_gmtime[2], this_gmtime[3], this_gmtime[4], this_gmtime[5])
        # tscale = ts.utc(2019, 1, 27, hours)
        tscale = ts.utc(2019, 1, 27, 23)
        return self.predict(tscale)

    def predict_range(self, start_time, finish_time, step):
        pass

    def find_events(self):
        sat = EarthSatellite(self.tle.tle_lines[1], self.tle.tle_lines[2], self.name)
        ts = load.timescale()

        bluffton = wgs84.latlon(+40.8939, -83.8917)
        t0 = ts.utc(2022, 7, 4)
        t1 = ts.utc(2022, 7, 5)
        t, events = sat.find_events(bluffton, t0, t1, altitude_degrees=30.0)
        for ti, event in zip(t, events):
            name = ('rise above 30°', 'culminate', 'set below 30°')[event]
            # print(ti.utc_jpl(), name)

    def predict_observer(self, prediction, observer_latitude, observer_longitude):

        here = wgs84.latlon(observer_latitude, observer_longitude)
        difference = prediction.sat - here
        topocentric = difference.at(prediction.timescale)
        prediction.position = list(topocentric.position.km)
        obs_elevation, obs_azimuth, obs_range = topocentric.altaz()
        prediction.elevation = float(obs_elevation.degrees)
        prediction.azimuth = float(obs_azimuth.degrees)
        prediction.range = float(obs_range.km)
        prediction.speed = float(topocentric.speed().km_per_s)
        prediction.velocity = list(topocentric.velocity.km_per_s)

        prediction.range_rate = float((prediction.velocity[0] * prediction.position[0] +
                                       prediction.velocity[1] * prediction.position[1] +
                                       prediction.velocity[2] * prediction.position[2]) /
                                      ((prediction.position[0] ** 2 + prediction.position[1] ** 2 + prediction.position[2] ** 2) ** .5))

        # for uuid, transmitter in self.transmitters.items():
        #     transmitter.range_rate = self.range_rate

        return prediction

    def predict_satellite(self, tscale):
        prediction = Prediction()
        prediction.timescale = tscale

        prediction.sat = EarthSatellite(self.tle.tle_lines[1], self.tle.tle_lines[2], self.name)
        geocentric = prediction.sat.at(tscale)

        prediction.geocentric = geocentric
        subpoint = geocentric.subpoint()

        prediction.latitude = float(subpoint.latitude.degrees)
        prediction.longitude = float(subpoint.longitude.degrees)
        prediction.altitude = float(subpoint.elevation.m)

        for uuid, transmitter in self.transmitters.items():
            transmitter.range_rate = self.range_rate

        return prediction

    # todo:  make so no lat long results in just running predict_satellite
    def predict(self, t_scale, observer_latitude=0.0, observer_longitude=0.0):
        sat_prediction = self.predict_satellite(t_scale)
        prediction = self.predict_observer(sat_prediction, observer_latitude, observer_longitude)
        return prediction

    def update_current_prediction(self):
        # todo:  manage observers

        ts = load.timescale()
        timescale = ts.now()
        prediction = self.predict(timescale)

        for key in prediction.__dict__.keys():
            setattr(self, key, getattr(prediction, key))

    def predict_passes(self, tscale_start, tscale_finish, minimum_elevation, observer_longitude, observer_latitude):
        event_types = ["rise", "culmination", "set"]
        t_tomorrow = tscale_start + 1

        # 0 — Satellite rose above ``altitude_degrees``.
        # 1 — Satellite culminated and started to descend again.
        # 2 — Satellite fell below ``altitude_degrees``.
        sat = EarthSatellite(self.tle.tle_lines[1], self.tle.tle_lines[2], self.name)
        here = wgs84.latlon(observer_latitude, observer_longitude)
        sat_events = sat.find_events(here, tscale_start, tscale_finish, altitude_degrees=minimum_elevation)

        event_types = sat_events[1]
        event_times = sat_events[0]

        satellite_pass = SatellitePass()

        for i, event_type in enumerate(event_types):

            if event_type == 0:
                satellite_pass.rise_time = event_times[i].utc_iso()

            elif event_type == 1:
                culmination = Culmination()

                prediction = self.predict(event_times[i], observer_latitude, observer_longitude)

                culmination.time = event_times[i].utc_iso()
                culmination.elevation = prediction.elevation
                culmination.azimuth = prediction.azimuth

                if prediction.elevation > satellite_pass.maximum_elevation:
                    satellite_pass.maximum_elevation = prediction.elevation

                satellite_pass.culimnations.append(event_times[i].utc_iso())

            elif event_type == 2:
                satellite_pass.set_time = event_times[i].utc_iso()
                self.passes.append(satellite_pass)

                satellite_pass = SatellitePass()

    def __repr__(self):
        return str(self.__dict__)


# todo:  set up defaults for params, optional params
class SatellitePass:
    def __init__(self):
        self.rise_time = ""
        self.set_time = ""
        self.culimnations = []
        self.maximum_elevation = 0.0


class Culmination:
    def __init__(self):
        self.time = ""
        self.elevation = 0.0
        self.azimuth = 0.0


class TLE:

    def __init__(self, norad_cat_id):
        self.exists = False
        self.tle_text = ""
        self.tle_lines = []
        self.norad_cat_id = norad_cat_id
        self.filename = ""

    def load_tle(self, filename):
        with open(filename, 'r') as file:
            tle_file_contents = file.read()
            re_string = "\n(.*\n1.*" + str(self.norad_cat_id) + "[UCS].*\n.*)"
            self.tle_text = re.findall(re_string, tle_file_contents)

            if (self.tle_text):
                self.tle_lines = self.tle_text[0].split("\n")
                self.exists = True
            else:
                self.exists = False
