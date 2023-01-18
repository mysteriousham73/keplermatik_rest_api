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

import requests, re, os, pickle
from requests_toolbelt.threaded import pool
import warnings

import simplejson
import keplermatik_satellites
import keplermatik_transmitters

class SatnogsClient:

    def __init__(self, satellites):
        self.satellites = satellites
        self.transmitters = keplermatik_transmitters.Transmitters()
        warnings.simplefilter('ignore', ResourceWarning)

    def get_satellites_offline(self):
        print("OFFLINE MODE | USING CACHED SATNOGS SATELLITES")
        infile = open('satnogs_satellites', 'rb')
        r = pickle.load(infile)
        infile.close()

        for satellite in r.json():

            #todo: if this key isn't in the dict it won't wind up in the object, move to init
            satellite['selected'] = False
            if(satellite['norad_cat_id'] != 99999):
                self.satellites.update({satellite['norad_cat_id']:keplermatik_satellites.Satellite(satellite)})


        print("NETWORK ERROR | USING CACHED SATNOGS TRANSMITTERS")
        infile = open('satnogs_transmitters', 'rb')
        t = pickle.load(infile)
        infile.close()


        for transmitter in t.json():
            self.transmitters.update({transmitter['uuid']:keplermatik_transmitters.Transmitter(transmitter)})

        for uuid, transmitter in self.transmitters.items():
            if transmitter.norad_cat_id in self.satellites:
                satellite = self.satellites[transmitter.norad_cat_id]
                satellite.transmitters.update({uuid:transmitter})

        del self.transmitters

        #todo: select first satellite


    def get_satellites(self):

        satellites_url = 'https://db.satnogs.org/api/satellites/'
        print("GETTING SATELLITES | " + satellites_url)
        payload = {'status': 'alive'}


        try:
            r = requests.get(satellites_url, params=payload)
            outfile = open('satnogs_satellites', 'wb')
            pickle.dump(r, outfile)
            outfile.close()

        except:
            print("NETWORK ERROR | USING CACHED SATNOGS SATELLITES")
            infile = open('satnogs_satellites', 'rb')
            r = pickle.load(infile)
            infile.close()

        # now write output to a file
        output = r.text
        satnogs_json_file = open("satnogs.json", "wb")
        satnogs_json_file.write(simplejson.dumps(simplejson.loads(output), indent=4, sort_keys=True).encode('utf8'))
        satnogs_json_file.close()


        for satellite in r.json():

            #todo: if this key isn't in the dict it won't wind up in the object, move to init
            satellite['selected'] = False

            if(satellite['norad_cat_id'] != 99999 and satellite['norad_cat_id'] != None):
                self.satellites.update({satellite['norad_cat_id']:keplermatik_satellites.Satellite(satellite)})

        transmitters_url = 'https://db.satnogs.org/api/transmitters/'


        payload = {'status': 'active'}

        print("GETTING TRANSMITTERS | " + transmitters_url)
        try:
            t = requests.get('https://db.satnogs.org/api/transmitters/', params=payload)
            outfile = open('satnogs_transmitters', 'wb')
            pickle.dump(t, outfile)
            outfile.close()

        except:
            print("NETWORK ERROR | USING CACHED SATNOGS TRANSMITTERS")
            infile = open('satnogs_transmitters', 'rb')
            t = pickle.load(infile)
            infile.close()


        for transmitter in t.json():
            self.transmitters.update({transmitter['uuid']:keplermatik_transmitters.Transmitter(transmitter)})

        for uuid, transmitter in self.transmitters.items():
            if transmitter.norad_cat_id in self.satellites:
                satellite = self.satellites[transmitter.norad_cat_id]
                satellite.transmitters.update({uuid:transmitter})

        del self.transmitters

        #todo: select first satellite
        self.update_tles()


    def update_tles(self):

        print("UPDATING TLEs | " + str(len(self.satellites)) + " SATELLITES IN SATNOGS")


        celestrak_files = ['satnogs.txt', 'active.txt', 'tle-new.txt']
        self._get_celestrak_tles(celestrak_files)
        self._get_satnogs_tles()

        self._write_tle_files()



    def _get_celestrak_tles(self, celestrack_files):
        tle_text = ""
        celestrak_urls = []

        print("DOWNLOADING CELESTRAK TLEs | " + ', '.join(celestrack_files).upper())

        for filename in celestrack_files:
            celestrak_urls.append('https://celestrak.com/NORAD/elements/' + filename)

        p = pool.Pool.from_urls(celestrak_urls)
        p.join_all()

        for response in p.responses():
            tle_text += response.text


        if(len(tle_text) != 0):

            with open('celestrak_tle.txt', 'wb') as file:
                file.write(bytes(tle_text, "UTF-8"))

            print("CELESTRACK TLEs LOADED")

        else:
            print("NETWORK ERROR | USING CACHED CELESTRACK TLES")
            with open('celestrak_tle.txt', 'r') as file:
                tle_text = file.read()

        del (p)

    def _get_satnogs_tles(self):
        tle_not_found_count = 0
        norad_cat_id_mismatch_count = 0
        manual_tle_count = 0
        id_not_in_satnogs_count = 0
        manual_tle_urls = []


        for id, satellite in self.satellites.items():
            if not satellite.tle_exists("celestrak_tle.txt"):
                tle_not_found_count += 1
                self.satellites.not_found_satellites.append(satellite.norad_cat_id)
                manual_tle_urls.append('https://db.satnogs.org/api/tle/?norad_cat_id=' + str(satellite.norad_cat_id))

        print("FOUND MISSING TLEs | " + str(tle_not_found_count) + " TLEs NOT FOUND")

        p = pool.Pool.from_urls(manual_tle_urls)
        p.join_all()
        manual_tles = ""

        for response in p.responses():
            requested_norad_cat_id = int(
                re.findall("https://db.satnogs.org/api/tle/\?norad_cat_id=(.*)", response.url)[0])
            if(response.status_code != 400 and len(response.json()) != 0):

                tle_json = response.json()

                # TODO:  IndexError: list index out of range here for some reason
                tle_name = tle_json[0]['tle0']
                tle_line1 = tle_json[0]['tle1']
                tle_line2 = tle_json[0]['tle2']
                json_norad_cat_id = tle_json[0]['norad_cat_id']
                tle_norad_cat_id = int(tle_line2[2:7].lstrip('0'))

                if(requested_norad_cat_id == tle_norad_cat_id):
                    self.satellites.satnogs_tle_satellites.append(requested_norad_cat_id)
                    manual_tle_count += 1
                    manual_tles += tle_name + "\r\n" + tle_line1 + "\r\n" + tle_line2 + "\r\n"
                else:
                    norad_cat_id_mismatch_count += 1
                    pass
                    #print("ID MISMATCH | Requested: " + str(requested_norad_cat_id) + "  Received: " + str(tle_norad_cat_id))
            else:
                id_not_in_satnogs_count += 1

        if (len(manual_tles) != 0):
            with open('satnogs_tle.txt', 'wb') as file:
                file.write(bytes("\n", "UTF-8"))
                file.write(bytes(manual_tles, "UTF-8"))
                print('DOWNLOADED SATNOG TLEs | ' + str(id_not_in_satnogs_count) + " NOT IN SATNOGS")
                print('DOWNLOADED SATNOG TLEs | ' + str(norad_cat_id_mismatch_count) + " NORAD CAT ID MISMATCHES")
                print('DOWNLOADED SATNOG TLEs | ' + str(manual_tle_count) + " SATNOG TLEs ADDED")

        else:
            # todo: look for them in the celestrak TLEs just in case
            manual_tle_count = 0
            for id, satellite in self.satellites.items():
                if satellite.tle_exists("satnogs_tle.txt"):
                    manual_tle_count += 1

            print('NETWORK ERROR | ' + str(manual_tle_count) + " MANUAL TLEs ADDED FROM SATNOGS TLE CACHE")



    def _write_tle_files(self):
        tle_text = ""
        with open('celestrak_tle.txt', 'r') as celestrak_file:
            tle_text = celestrak_file.read()
            with open('tle.txt', 'wb') as tle_file:
                tle_file.write(bytes(tle_text, "UTF-8"))
                #todo fix \n between the files
                with open('satnogs_tle.txt', 'r') as satnogs_file:
                    manual_tles = satnogs_file.read()
                    tle_file.write(bytes(manual_tles, "UTF-8"))








