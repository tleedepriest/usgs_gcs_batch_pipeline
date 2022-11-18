#!/usr/bin/env python
import sys
import json
from datetime import datetime as dt
import geopandas as gpd


def preprocess_json(loaded_json):
    """
    loaded_json: dict object form json.loads()
    """
    for data_event in loaded_json["features"]:
        # delete this field that denotes event in earthquake (redundant)
        # del data_event['properties']['type'] # caused bug in BQ
        coordinates = data_event["geometry"]["coordinates"]
        data_event["geometry"]["coordinates"] = coordinates[:2]
    return loaded_json


def transform_json_to_newline_json(source_file, dest_file):
    """
    source_file: filepath to raw json from usgs API
    dest_file: filepath to newline deliminated geojson file

    using command ->
        bq load \
        --source_format=NEWLINE_DELIMITED_JSON \
        --json_extension=GEOJSON \
        --autodetect \
        DATASET.TABLE \
        FILE_PATH_OR_URI

    https://cloud.google.com/bigquery/docs/geospatial-data#bq

    unfortunately it seems no Airflow operator supports this
    command above (minus Bash, but authenticating gloud in Docker
    container not worth the pain and added complexity).
    """
    with open(source_file, "r") as fh:
        loaded_json = json.loads(fh.read())
        loaded_json = preprocess_json(loaded_json)

    result = [json.dumps(record) for record in loaded_json["features"]]

    with open(dest_file, "w") as fh:
        for result in result:
            fh.write(f"{result}\n")


def convert_datetime_col(timestamp):
    """
    https://stackoverflow.com/questions/31548132/python-datetime-fromtimestamp-yielding-valueerror-year-out-of-range
    """
    timestamp /= 1000
    return dt.utcfromtimestamp(timestamp)


def preprocess_json_file_to_csv(source_file, dest_file):
    """
    source_file: path to raw json file from USGS API
    dest_file: path to csv to be loaded into BQ
    """
    with open(source_file, "r") as fh:
        loaded_json = json.loads(fh.read())
        loaded_json = preprocess_json(loaded_json)

    print(loaded_json)

    with open(source_file, "w") as fh:
        fh.write(json.dumps(loaded_json))

    geo_df = gpd.read_file(source_file)
    print(geo_df)
    geo_df["time"] = geo_df["time"].apply(convert_datetime_col)
    geo_df["updated"] = geo_df["updated"].apply(convert_datetime_col)
    geo_df = geo_df.astype({"tsunami": "int", "sig": "int"})
    geo_df.to_csv(dest_file, index=False)


if __name__ == "__main__":
    # preprocess_json_to_new_line_json(sys.argv[1], sys.argv[2])
    preprocess_json_file_to_csv(sys.argv[1], sys.argv[2])
