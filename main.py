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

from keplermatik_satellites import Satellites
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()
satellites = Satellites()

if __name__ == "__main__":

    config = uvicorn.Config("main:app", host="192.168.1.2", port=8001, log_level="info")
    server = uvicorn.Server(config)
    server.run()



class Prediction(BaseModel):
    norad_cat_id: int
    satellite_name: str
    latitude: float
    longitude: float
    rise_time: str
    set_time: str
    maximum_elevation: str

class PredictionRequest(BaseModel):
    norad_cat_id: int
    observer_latitude: float
    observer_longitude: float
    #prediction: Prediction

#
# @app.get("")
# async def root():
#     satellite = satellites[25544]
#     satellite.predict_now(38.951561, -92.328636)
#
#     return {"satellite": {"norad_cat_id": satellite.norad_cat_id, "latitude": satellite.latitude, "longitude": satellite.longitude}

@app.get("/satellite_list/")
async def satellite_list():
    satellite_list = {}
    for norad_cat_id, satellite in satellites.items():
        satellite_list[satellite.name.upper()] = norad_cat_id
    #print(satellite_list)
    return satellite_list


@app.post("/predict_now/")
async def create_item(prediction_request: PredictionRequest):

    satellite = satellites[prediction_request.norad_cat_id]
    satellite.predict_now(37.7821, -122.4054)

    prediction = Prediction(satellite_name=satellite.name, norad_cat_id=satellite.norad_cat_id, latitude=str(round(float(satellite.latitude), 2)), longitude=str(round(float(satellite.longitude), 2)), rise_time=satellite.next_pass.rise_time, set_time=satellite.next_pass.set_time, maximum_elevation=str(round(satellite.next_pass.maximum_elevation, 2)) + " degrees")
    print(prediction)
    return prediction
