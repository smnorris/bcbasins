import os
import re

import requests
import geopandas
import click
import bcdata
from pprint import pprint
from pathlib import Path
from pyproj import Proj, transform

FWA_API_URL = "https://www.hillcrestgeo.ca/fwapg"
EPA_POINT_SERVICE_URL = "http://ofmpub.epa.gov/waters10/PointIndexing.Service?"
EPA_WSD_DELINEATION_URL = (
    "http://ofmpub.epa.gov/waters10/NavigationDelineation.Service?"
)

# For more info on EPA Services:
# points      - https://www.epa.gov/waterdata/point-indexing-service
# deliniation - https://www.epa.gov/waterdata/navigation-delineation-service
# other       - https://www.epa.gov/waterdata/waters-web-services


def geojson2gdf(geojson, out_srid=3005):
    """Convert provided geojson feature(s) to a BC Albers geodataframe
    """
    # convert returned feature to a FeatureCollection
    outjson = dict(type="FeatureCollection", features=[])
    for result in [geojson]:
        outjson["features"] += result
    # return the point as a GDF in using specified EPSG id
    return geopandas.GeoDataFrame.from_features(outjson, crs="EPSG:4326").to_crs(
        epsg=out_srid
    )


def fwa_neareststream(x, y, srid=4326, tolerance=500, num_features=10, as_gdf=False):
    """Request stream nearest to given point, return as single feature or geopandas dataframe
    """
    url = FWA_API_URL + "/functions/fwa_neareststream/items.json"
    # request the closest stream, get first record
    r = requests.get(
        url,
        params={
            "x": x,
            "y": y,
            "srid": srid,
            "tolerance": tolerance,
            "num_features": num_features,
        },
    )
    if as_gdf:
        return geojson2gdf(r.json()["features"])
    else:
        return r.json()["features"][0]


def fwa_watershedatmeasure(blkey, meas, as_gdf=False):
    """Request watershed upstream of location, return as single feature or as geopandas dataframe
    """
    url = FWA_API_URL + "/functions/fwa_watershedatmeasure/items.json"
    param = {"blue_line_key": blkey, "downstream_route_measure": meas}
    r = requests.get(url, params=param)
    if as_gdf:
        return geojson2gdf(r.json()["features"])
    else:
        return r.json()["features"][0]


def fwa_watershedhex(blkey, meas, as_gdf=False):
    """Request 25m hex within fundamental watershed at location specified, return
    as feature collection or geopandas dataframe
    """
    url = FWA_API_URL + "/functions/fwa_watershedhex/items.json"
    param = {"blue_line_key": blkey, "downstream_route_measure": meas, "limit": 10000}
    r = requests.get(url, params=param)
    # convert returned feature to a FeatureCollection
    if as_gdf:
        return geojson2gdf(r.json()["features"])
    else:
        return r.json()["features"]


def fwa_watershedstream(blkey, meas, as_gdf=False):
    """Request upstream stream segments within fundamental watershed at location specified.
    Return as feature collection or geopandas dataframe
    """
    url = FWA_API_URL + "/functions/fwa_watershedstream/items.json"
    param = {"blue_line_key": blkey, "downstream_route_measure": meas}
    r = requests.get(url, params=param)
    if as_gdf:
        return geojson2gdf(r.json()["features"])
    else:
        return r.json()["features"]


def epa_index_point(x, y, srid=4326, tolerance=150, as_gdf=False):
    """
    Provided a location as x,y,srid, find nearest NHD stream within tolerance
    Returns stream id, measure of location on stream, and distance from point to stream
    """
    # transform coordinates into (lon,lat)
    if srid != 4326:
        in_srs = Proj(init="epsg:{}".format(srid))
        request_srs = Proj(init="epsg:4326")
        x, y = transform(in_srs, request_srs, x, y)
    parameters = {
        "pGeometry": "POINT(%s %s)" % (x, y),
        "pResolution": "2",
        "pPointIndexingMethod": "DISTANCE",
        "pPointIndexingMaxDist": str(tolerance),
        "pOutputPathFlag": "FALSE",
    }
    # make the resquest
    r = requests.get(EPA_POINT_SERVICE_URL, params=parameters).json()

    # extract the coordinates on the nearest stream
    x_indexed, y_indexed = r["output"]["end_point"]["coordinates"]

    # reproject if necessary
    if srid != 4326:
        x_indexed, y_indexed = transform(request_srs, in_srs, x_indexed, y_indexed)

    # build a feature from the coordinates, matching properties of FWA for convenience
    f = {
        "type": "Feature",
        "properties": {
            "gnis_name": r["output"]["ary_flowlines"][0]["gnis_name"],
            "blue_line_key": None,
            "distance_to_stream": r["output"]["path_distance"],
            "downstream_route_measure": r["output"]["ary_flowlines"][0]["fmeasure"],
            "bc_ind": "USA",
            "comid": r["output"]["ary_flowlines"][0]["comid"],
        },
        "geometry": {"type": "Point", "coordinates": [x_indexed, y_indexed]},
    }
    # transform to geodataframe if specified
    if as_gdf:
        return geojson2gdf(f)
    else:
        return f


def epa_delineate_watershed(comid, measure, as_gdf=False):
    """
    Given a location as comid and measure, return boundary of watershed upstream
    (as geojson/wgs84 or geodataframe/bc albers)
    """
    parameters = {
        "pNavigationType": "UT",
        "pStartComid": comid,
        "pStartMeasure": measure,
        "pMaxDistance": 560,
        "pFeatureType": "CATCHMENT",
        "pOutputFlag": "FEATURE",
        "pAggregationFlag": "TRUE",
        "optOutGeomFormat": "GEOJSON",
        "optOutPrettyPrint": 0,
    }

    # make the resquest
    r = requests.get(EPA_WSD_DELINEATION_URL, params=parameters).json()

    if r["output"] is not None:
        # build a feature with schema matching fwa schema
        f = {
            "type": "Feature",
            "properties": {
                "wscode": None,
                "localcode": None,
                "refine_method": None,
                "area_ha": r["output"]["total_areasqkm"] * 100,
            },
            "geometry": r["output"]["shape"],
        }
        if as_gdf:
            return geojson2gdf(f)
        else:
            return f
    else:
        return None


def find_ngrams(text: str, number: int = 3) -> set:
    """
    returns a set of ngrams for the given string
    :param text: the string to find ngrams for
    :param number: the length the ngrams should be. defaults to 3 (trigrams)
    :return: set of ngram strings
    """

    if not text:
        return set()

    words = [f"  {x} " for x in re.split(r"\W+", text.lower()) if x.strip()]

    ngrams = set()

    for word in words:
        for x in range(0, len(word) - number + 1):
            ngrams.add(word[x : x + number])

    return ngrams


def similarity(text1: str, text2: str, number: int = 3) -> float:
    """
    Finds the similarity between 2 strings using ngrams.
    0 being completely different strings, and 1 being equal strings
    """
    # https://stackoverflow.com/questions/46198597/python-string-matching-exactly-equal-to-postgresql-similarity-function
    ngrams1 = find_ngrams(text1, number)
    ngrams2 = find_ngrams(text2, number)

    num_unique = len(ngrams1 | ngrams2)
    num_equal = len(ngrams1 & ngrams2)

    return float(num_equal) / float(num_unique)


def distance_name_match(in_df, name, column="gnis_name", keep_ranks=False):
    """Return top ranked row in df, ranking by
    - distance_to_stream (weight=0.3)
    - matching input 'name' to supplied column, using trgrm similaryt (weight=0.7)
    """
    # https://stackoverflow.com/questions/46198597/python-string-matching-exactly-equal-to-postgresql-similarity-function
    in_df["name_rank"] = in_df.apply(lambda row: similarity(row[column], name), axis=1)
    in_df["name_rank"][in_df["name_rank"] > 0.3] = 1
    in_df["distance_rank"] = in_df.apply(
        lambda row: (500 - row.distance_to_stream) / 500, axis=1
    )
    in_df["match_rank"] = in_df.apply(
        lambda row: row.name_rank * 0.8 + row.distance_rank * 0.2, axis=1
    )
    # drop the ranking columns by default
    if keep_ranks:
        return (
            in_df.sort_values(["match_rank"], ascending=False)
            .head(1)
            .reset_index()
            .drop(["index"], axis=1)
        )
    else:
        return (
            in_df.sort_values(["match_rank"], ascending=False)
            .head(1)
            .reset_index()
            .drop(["index", "name_rank", "distance_rank", "match_rank"], axis=1)
        )


@click.command()
@click.argument("in_file")
@click.argument("in_id")
@click.option(
    "--in_name", "-n", help="Text column present in in_file for matching to stream name"
)
@click.option("--in_layer", "-l", help="Input layer held in in_file")
@click.option("--points_only", help="Return only points", is_flag=True)
def create_watersheds(in_file, in_id, in_name=None, in_layer=None, points_only=None):
    """Get watershed boundaries upstream of provided points
    """

    # load input points
    in_points = []
    in_points = geopandas.read_file(in_file, layer=in_layer)
    srid = in_points.crs.to_epsg()

    # This just makes things simpler.
    if srid != 3005:
        return "Input points must be BC Albers"

    # iterate through input points
    for index, pt in in_points.iterrows():

        click.echo("-----------------------------------------------------------")
        click.echo("* INPUT POINT")
        click.echo(pt)
        # create temp folder structure
        temp_folder = os.path.join("tempfiles", "t_" + str(pt[in_id]))
        Path(temp_folder).mkdir(parents=True, exist_ok=True)

        # find 10 closest streams in BC, within 500m
        nearest_streams = fwa_neareststream(
            pt.geometry.x,
            pt.geometry.y,
            srid,
            tolerance=500,
            num_features=10,
            as_gdf=True,
        )

        # The closest stream is not necessarily the one we want!
        # If we have a name column to compare against, try getting the best combination
        # of name and distance matching by comparing to the stream gnis_name
        if in_name:
            matched_stream = distance_name_match(nearest_streams, pt[in_name])
        # if no name provided, just use the first result
        else:
            matched_stream = nearest_streams.head(1)

        # simplify the schema for standardization between BC/USA
        matched_stream = matched_stream.drop(
            ["wscode_ltree", "localcode_ltree", "linear_feature_id"], axis=1
        )
        matched_stream["comid"] = ""

        # if the nearest stream is not in BC or is more than 150m from the
        # input point, try the EPA service
        if (
            matched_stream.iloc[0]["bc_ind"] == "NOTBC"
            and matched_stream.iloc[0]["distance_to_stream"] >= 150
        ):
            matched_stream = epa_index_point(
                pt["src_x"], pt["src_y"], srid, 150, as_gdf=True
            )

        # add input id column and value to point
        matched_stream.at[0, in_id] = pt[in_id]

        # write indexed point to shp
        matched_stream.to_file(os.path.join(temp_folder, "point.shp"))

        # drop geom for easy dump to stdout so user know what stream we've matched to
        click.echo("")
        click.echo("* MATCHED STREAM")
        click.echo(pprint(matched_stream.iloc[0].drop("geometry").to_dict()))

        # extract the required values from matched_stream gdf, just to
        # keep code below tidier
        blue_line_key = matched_stream.iloc[0]["blue_line_key"]
        downstream_route_measure = matched_stream.iloc[0]["downstream_route_measure"]
        comid = matched_stream.iloc[0]["comid"]

        # if not just indexing points, start deriving the watershed
        if not points_only:

            # Canadian streams
            if matched_stream.iloc[0]["bc_ind"] != "USA":
                wsd = fwa_watershedatmeasure(
                    blue_line_key, downstream_route_measure, as_gdf=True
                )

            # USA streams (only lower 48 states supported)
            else:
                wsd = epa_delineate_watershed(
                    comid, downstream_route_measure, as_gdf=True
                )

            # add id to watershed
            wsd.at[0, in_id] = pt[in_id]

            # write output shapefile
            wsd.to_file(os.path.join(temp_folder, "wsd.shp"))

            # if we are postprocessing with DEM, get additional data
            if wsd.iloc[0]["refine_method"] == "DEM":
                click.echo("requesting additional data for {}".format(pt[in_id]))
                # fwapg requests
                hexgrid = fwa_watershedhex(
                    blue_line_key, downstream_route_measure, as_gdf=True
                )
                hexgrid.to_file(os.path.join(temp_folder, "hexgrid.shp"))
                pourpoints = fwa_watershedstream(
                    blue_line_key, downstream_route_measure, as_gdf=True
                )
                pourpoints.to_file(os.path.join(temp_folder, "pourpoints.shp"))
                # DEM of hex watershed plus 250m
                bounds = list(hexgrid.geometry.total_bounds)
                expansion = 250
                xmin = bounds[0] - expansion
                ymin = bounds[1] - expansion
                xmax = bounds[2] + expansion
                ymax = bounds[3] + expansion
                expanded_bounds = (xmin, ymin, xmax, ymax)
                bcdata.get_dem(
                    expanded_bounds,
                    out_file=os.path.join(temp_folder, "dem.tif"),
                    src_crs="EPSG:{}".format(srid),
                    dst_crs="EPSG:{}".format(srid),
                    resolution=25,
                )


if __name__ == "__main__":
    create_watersheds()
