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
import pickle

from keplermatik_transmitters import Transmitters

import satnogs_network
import  warnings

from skyfield.api import EarthSatellite, load, wgs84
from time import time, sleep
import re, numpy as np


class SatelliteEvents:
    def __init__(self):
        self.current_time = ""
        self.events = []


class SatelliteEvent:
    def __init__(self):
        self.datetime_string = ""
        self.event_type = ""

    def __init(self, datetime_string, event_type):
        self.datetime_string = datetime_string
        self.event_type = event_type

    def __repr__(self):
        return "event=(" + self.datetime_string + ", " + self.event_type + ")"


class SatellitePass:
    def __init__(self):
        self.rise_time = ""
        self.set_time = ""
        self.culimnation_time = ""
        self.maximum_elevation = ""


class Satellites(dict):

    def __init__(self):
        super(Satellites, self).__init__()
        self.offline_flag = 1
        self.tle_source = ""
        self.cleaned_up_satellites = []
        self.not_found_satellites = []
        self.satnogs_tle_satellites = []
        self.tracked_satellites = []

        current_tles = ""

        satnogs = satnogs_network.SatnogsClient(self)

        if(self.offline_flag == 0):
            satnogs.get_satellites()
            self.tle_source = "tle.txt"
            self.cleanup_satellites()

            for norad_cat_id, satellite in self.items():
                current_tles += satellite.tle.tle_lines[0] + "\r\n" + satellite.tle.tle_lines[1] + "\r\n" + satellite.tle.tle_lines[2] + "\r\n"

            with open('tle_cache.txt', 'wb') as file:
                file.write(bytes(current_tles, "UTF-8"))
        else:
            satnogs.get_satellites_offline()
            self.tle_source = "tle_cache.txt"
            self.cleanup_satellites()

        print("LOADING TLEs | " + str(len(self)) + " SATELLITES")
        for norad_cat_id, satellite in self.items():
            satellite.load_tle(self.tle_source)

    def get_by_name(self, name):
        by_name = {sat.name: sat for sat in self.items()}
        satellite = by_name[name]
        print(satellite)

    def start_prediction_engine(self):

        while 1:
            pass
            # start_time = time()
            #
            # timing, predictions = self.predictor.predict()
            #
            # #tuning parameter for prediction engine
            # #
            #
            # #print("PREDICTIONS COMPLETE | " + str(len(self.tracked_satellites)) + " SATELLITES IN " + str(round(time() - start_time, 3)) + " SECONDS")
            # #print("PREDICTION RUN | QUEUE LOAD " + str(timing['queue_load']) + " PREDICT " + str(timing['prediction']) + " (" + str(round(timing['prediction'] / len(self.tracked_satellites), 3)) + "/SAT) " + "QUEUE UNLOAD " + str(timing['queue_unload']))

    @property
    def selected_satellite(self):
        if([a_satellite for norad_cat_id, a_satellite in self.items() if a_satellite.selected]):
            return [a_satellite for norad_cat_id, a_satellite in self.items() if a_satellite.selected][0]

    def cleanup_satellites(self):
        satellites_to_delete = []
        no_tle_count = 0
        not_orbiting_count = 0

        if(self.offline_flag == 1):
            with open('cleanup_cache',) as fp:
                satellites_to_delete = json.load(fp)


            print("CLEANING UP INVALID SATELLITES | " + str(len(satellites_to_delete)) + " INVALID SATELLITES IN CACHE")

            for satellite_to_delete in satellites_to_delete:
                for satellite in [satellite for satellite in self if satellite == satellite_to_delete]: del(self[int(satellite_to_delete)])

        else:
            print("CLEANING UP INVALID SATELLITES | ANALYZING " + str(len(self)) + " SATELLITES")

            for norad_cat_id, satellite in self.items():
                satellite.load_tle(self.tle_source)
                if not satellite.tle.exists:
                    satellites_to_delete.append(norad_cat_id)
                    no_tle_count = no_tle_count + 1
                    self.cleaned_up_satellites.append(norad_cat_id)

            for satellite_to_delete in satellites_to_delete:
                for satellite in [satellite for satellite in self if satellite == satellite_to_delete]: del(self[int(satellite_to_delete)])


            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                for norad_cat_id, satellite in self.items():
                    satellite.predict_now()

                    if(wgs84.height_of(satellite.geocentric).m <= 0):
                        satellites_to_delete.append(norad_cat_id)
                        self.cleaned_up_satellites.append(norad_cat_id)
                        not_orbiting_count = not_orbiting_count + 1

            with open('cleanup_cache', 'w') as fp:
                json.dump(satellites_to_delete, fp)

            for satellite_to_delete in satellites_to_delete:
                for satellite in [satellite for satellite in self if satellite == satellite_to_delete]: del(self[int(satellite_to_delete)])


            print("CLEANED UP " + str(no_tle_count + not_orbiting_count) + " SATELLITES | " + str(no_tle_count) + " WITHOUT TLE / " + str(not_orbiting_count) + " NOT ORBITING")

            with open('satellite_cache', 'wb') as fp:
                pickle.dump(satellites_to_delete, fp)

    def track_all_satellites(self):
        for norad_cat_id, satellite in self.items():
            self.track_satellite(satellite)

    def is_tracked(self, satellite):
        if satellite.norad_cat_id in self.tracked_satellites:
            return True
        else:
            return False

    def track_satellite_by_norad_cat_id(self, id):

        self.tracked_satellites.append(id)
        satellite_to_track = self[id]

        tracked_satellite_text = satellite_to_track.name + " (" + str(satellite_to_track.norad_cat_id) + ")"

        #print("TRACKING | " + tracked_satellite_text)

    def untrack_satellite_by_norad_cat_id(self, id):

        self.tracked_satellites.remove(id)
        satellite_to_untrack = self[id]

        untracked_satellite_text = satellite_to_untrack.name + " (" + str(satellite_to_untrack.norad_cat_id) + ")"

        print("NO LONGER TRACKING | " + untracked_satellite_text)

    def track_satellite(self, satellite_to_track):

        self.tracked_satellites.append(satellite_to_track.norad_cat_id)
        selected_satellite_text = satellite_to_track.name + " (" + str(satellite_to_track.norad_cat_id) + ")"

        print("TRACKING | " + selected_satellite_text)

    def untrack_satellite(self, satellite_to_untrack):

        self.tracked_satellites.remove(satellite_to_untrack.norad_cat_id)
        deselected_satellite_text = satellite_to_untrack.name + " (" + str(satellite_to_untrack.norad_cat_id) + ")"

        print("NO LONGER TRACKING | " + deselected_satellite_text)

    def clear_tracked(self):
        self.tracked_satellites.clear()


class Satellite(object):

    def __init__(self, data):
        self.range_rate = 0
        self.transmitters = Transmitters()
        self.norad_cat_id = 0
        self.elevation = 0
        self.current_time_resolution = 1
        #self.satellite_events = SatelliteEvents()
        self.next_pass = SatellitePass()

        for name, value in data.items():
            setattr(self, name, self._wrap(value))

        self.tle = TLE(self.norad_cat_id)

    def load_tle(self, filename):
        self.tle.load_tle(filename)

    def tle_exists(self, filename):
        self.tle.load_tle(filename)
        return self.tle.exists

    def _wrap(self, value):
        if isinstance(value, (tuple, list, set, frozenset)):
            return type(value)([self._wrap(v) for v in value])
        else:
            return Satellite(value) if isinstance(value, dict) else value

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
        #utc(self, year, month=1, day=1, hour=0, minute=0, second=0.0):
        hours = np.arange(0, 23, 1/60)
        #minutes = np.arange(0, 2, (1))
        #tscale = ts.utc(this_gmtime[0], this
        #_gmtime[1], this_gmtime[2], this_gmtime[3], this_gmtime[4], this_gmtime[5])
        #tscale = ts.utc(2019, 1, 27, hours)
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
            #print(ti.utc_jpl(), name)


    def predict(self, tscale, observer_latitude, observer_longitude):
        sat = EarthSatellite(self.tle.tle_lines[1], self.tle.tle_lines[2], self.name)
        geocentric = sat.at(tscale)
        self.geocentric = geocentric
        subpoint = geocentric.subpoint()

        self.latitude = float(subpoint.latitude.degrees)
        self.longitude = float(subpoint.longitude.degrees)
        self.altitude = float(subpoint.elevation.m)
        here = wgs84.latlon(observer_latitude, observer_longitude)
        difference = sat - here
        topocentric = difference.at(tscale)
        self.position = list(topocentric.position.km)
        self.elevation, self.azimuth, self.range = topocentric.altaz()
        self.elevation = float(self.elevation.degrees)
        self.azimuth = float(self.azimuth.degrees)
        self.range = float(self.range.km)
        self.speed = float(topocentric.speed().km_per_s)
        self.velocity = list(topocentric.velocity.km_per_s)
        self.range_rate = float((self.velocity[0] * self.position[0] + self.velocity[1] * self.position[1] +
                                 self.velocity[2] * self.position[2]) / ((self.position[0] ** 2 + self.position[
            1] ** 2 + self.position[2] ** 2) ** .5))

        for uuid, transmitter in self.transmitters.items():
            transmitter.range_rate = self.range_rate
        event_types = ["rise", "culmination", "set"]
        t_tomorrow = tscale + 1

        # 0 — Satellite rose above ``altitude_degrees``.
        # 1 — Satellite culminated and started to descend again.
        # 2 — Satellite fell below ``altitude_degrees``.

        sat_events = sat.find_events(here, tscale, t_tomorrow, altitude_degrees=20.0)
        t, events = sat.find_events(here, tscale, t_tomorrow, altitude_degrees=20.0)

        # print(f"{sat_events} ")


        # self.satellite_events.current_time = tscale.utc_iso()
        # for i, event_time in enumerate(sat_events[0]):
        #     event = SatelliteEvent()
        #     event.datetime_string = event_time.utc_iso()
        #     event.event_type = event_types[sat_events[1][i]]
        #     self.satellite_events.events.append(event)

        event = SatelliteEvent
        next_event_time = sat_events[0][0]
        event.datetime_string = next_event_time.utc_iso()
        event.event_type = event_types[sat_events[1][0]]
        self.next_pass = event

        event_types = sat_events[1]
        event_times = sat_events[0]

        first_rise = 0
        first_culmination = 0
        first_set = 0

        for i, event_type in enumerate(event_types):
            if event_type == 0:  #rise above threshold
                first_rise = i
                break

        for i, event_type in enumerate(event_types):
            if event_type == 1:
                first_culmination = i
                break

        for i, event_type in enumerate(event_types):
            if event_type == 2:
                first_set = i
                break

        self.next_pass.rise_time = event_times[first_rise].utc_strftime('%B %d %Y at %I:%M %p UTC')
        self.next_pass.culimnation_time = event_times[first_culmination].utc_strftime('%B %d %Y at %I:%M %p')
        self.next_pass.set_time = event_times[first_set].utc_strftime('%B %d %Y at %I:%M %p')

        geocentric = sat.at(event_times[first_culmination])

        here = wgs84.latlon(observer_latitude, observer_longitude)
        difference = sat - here
        topocentric = difference.at(event_times[first_culmination])

        elevation, azimuth, range = topocentric.altaz()
        elevation = float(elevation.degrees)

        self.next_pass.maximum_elevation = elevation



        # if self.norad_cat_id == 25544:
        #
        #     for ti, event in zip(t, events):
        #         name = ('rise above 20°', 'culminate', 'set below 20°')[event]
        #         print(ti.utc_strftime('%Y %b %d %H:%M:%S'), name)
        # print("")

    def __repr__(self):
        return str(self.__dict__)


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

            if(self.tle_text):
                self.tle_lines = self.tle_text[0].split("\n")
                self.exists = True
            else:
                self.exists = False


