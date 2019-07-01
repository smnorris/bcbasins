import os
import json

import requests
import fiona
import click
import bcdata
from pyproj import Proj, transform

FWA_API_URL = "https://www.hillcrestgeo.ca/fwa/v1"

# point service:
# https://www.epa.gov/waterdata/point-indexing-service
EPA_POINT_SERVICE_URL = "http://ofmpub.epa.gov/waters10/PointIndexing.Service?"

# delineation service:
# https://www.epa.gov/waterdata/navigation-delineation-service
EPA_WSD_DELINEATION_URL = "http://ofmpub.epa.gov/waters10/NavigationDelineation.Service?"

# See here for info for all EPA WATERS web services
# https://www.epa.gov/waterdata/waters-web-services


def make_sure_path_exists(path):
    """
    Make directories in path if they do not exist.
    Modified from http://stackoverflow.com/a/5032238/1377021
    """
    try:
        os.makedirs(path)
    except:
        pass
    return path


def get_fwa_stream(x, y, epsg_code):
    """request stream nearest to given point
    """
    url = "{}/{},{},{}".format(
        FWA_API_URL + "/nearest_stream", x, y, str(epsg_code)
    )
    # request the closest stream, get first record
    r = requests.get(url)
    streampt = r.json()["features"][0]

    # to match USA schema, pop FWA attributes that we don't really need
    streampt["properties"].pop("wscode")
    streampt["properties"].pop("localcode")
    streampt["properties"].pop("linear_feature_id")
    return streampt


def get_fwa_wsd(blkey, meas, epsg_code):
    """request a FWA watershed
    """
    url = "{}/{}".format(FWA_API_URL + "/watershed", blkey)
    param = {"downstream_route_measure": meas, "srid": epsg_code}
    r = requests.get(url, params=param)
    return r.json()["features"][0]


def get_dem_data(blkey, meas, feature_id, srid, source_crs, out_file):
    """get DEM and pour point for watershed of interest
    NOTE - units of input source_crs / srid must be meters
    """
    click.echo("requesting additional data for {}".format(feature_id))

    # define schemas for output files
    stream_schema = {
        "properties": {"linear_feature_id": "int"},
        "geometry": "MultiLineString",
    }
    hex_schema = {
        "properties": {"hex_id": "int"},
        "geometry": "MultiPolygon",
    }

    # get stream  (pour point)
    url = "{}/{}".format(FWA_API_URL + "/watershed_stream", blkey)
    param = {"downstream_route_measure": meas, "srid": srid}
    r = requests.get(url, params=param)
    with fiona.Env():
        with fiona.open(
            out_file,
            "w",
            driver="GPKG",
            layer=str(feature_id) + "_stream",
            crs=source_crs,
            schema=stream_schema,
        ) as dst:
            for f in r.json()["features"]:
                dst.write(f)

    # get hex grid covering watershed to be adjusted
    url = "{}/{}".format(FWA_API_URL + "/watershed_hex", blkey)
    param = {"downstream_route_measure": meas, "srid": srid}
    r = requests.get(url, params=param)
    with fiona.Env():
        with fiona.open(
            out_file,
            "w",
            driver="GPKG",
            layer=str(feature_id) + "_hex",
            crs=source_crs,
            schema=hex_schema,
        ) as dst:
            for f in r.json()["features"]:
                dst.write(f)
        # get bounds by opening file just written
        with fiona.open(out_file, "r", layer=str(feature_id) + "_hex") as f:
            bounds = f.bounds

    # get DEM of hex watershed plus 250m
    expansion = 250
    xmin = bounds[0] - expansion
    ymin = bounds[1] - expansion
    xmax = bounds[2] + expansion
    ymax = bounds[3] + expansion
    expanded_bounds = (xmin, ymin, xmax, ymax)
    bcdata.get_dem(
        expanded_bounds,
        out_file=os.path.join("tempfiles", "dem", str(feature_id) + ".tif"),
        src_crs="EPSG:{}".format(srid),
        dst_crs="EPSG:{}".format(srid),
        resolution=25
    )


def epa_index_point(in_x, in_y, srid, tolerance):
    """
    Provided a location as x,y,srid, find nearest NHD stream within tolerance
    Returns stream id, measure of location on stream, and distance from point to stream
    """
    # transform coordinates into (lon,lat)
    in_srs = Proj(init='epsg:{}'.format(srid))
    out_srs = Proj(init='epsg:4326')
    x, y = transform(in_srs, out_srs, in_x, in_y)

    parameters = {
        "pGeometry": "POINT(%s %s)" % (x, y),
        "pResolution": "2",
        "pPointIndexingMethod": "DISTANCE",
        "pPointIndexingMaxDist": str(tolerance),
        "pOutputPathFlag": "FALSE",
    }
    # make the resquest
    r = requests.get(
        EPA_POINT_SERVICE_URL,
        params=parameters).json()

    # build a feature from the results, matching FWA schema
    f = {
            "type": "Feature",
            "properties": {
                "blue_line_key": r["output"]["ary_flowlines"][0]["comid"],
                "downstream_route_measure": r["output"]["ary_flowlines"][0]["fmeasure"],
                "distance_to_stream": r["output"]["path_distance"],
                "gnis_name": r["output"]["path_distance"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": r["output"]["end_point"]["coordinates"]
            }
        }
    return f


def epa_delineate_watershed(feature_id, comid, measure):
    """
    Given a location as comid and measure, return geojson representing
    boundary of watershed upstream
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
        "optOutPrettyPrint": 0
    }
    # make the resquest
    r = requests.get(
        EPA_WSD_DELINEATION_URL,
        params=parameters)

    if r.json()["output"] is not None:
        if len(r.json()["output"]["shape"]["coordinates"]) == 1:
            geomtype = "Polygon"
        elif len(r.json()["output"]["shape"]["coordinates"]) > 1:
            geomtype = "MultiPolygon"
        # build a feature with schema matching fwa schema
        f = {
            "type": "Feature",
            "properties": {
                "wscode": None,
                "localcode": None,
                "area_ha": r.json()["output"]["areasqkm"] * .01
                },
            "geometry": {
                "type": geomtype,
                "coordinates": r.json()["output"]["shape"]["coordinates"]
            }
        }
        return f
    else:
        return None


@click.command()
@click.argument("in_file")
@click.option("--in_layer", "-l", help="Input layer held in in_file")
@click.option("--in_id", "-id", help="Unique id of in_file or in_layer")
@click.option("--points_only", help="Return only points", is_flag=True)
def create_watersheds(in_file, in_layer, in_id, points_only):
    """Get watershed boundaries upstream of provided points
    """

    # load input points
    in_points = []
    with fiona.Env():
        with fiona.open(in_file, layer=in_layer) as src:
            epsg_code = src.crs["init"].split(":")[1]
            source_crs = src.crs
            in_id_type = src.schema["properties"][in_id]
            for f in src:
                x, y = f["geometry"]["coordinates"]
                in_points.append(
                    {in_id: f["properties"][in_id], "src_x": x, "src_y": y}
                )

    if epsg_code == 4326:
        return("Input points must be in a projected coordinate system, not lat/lon (for easy DEM extraction)")
    # create temp folder structure
    make_sure_path_exists(os.path.join("tempfiles", "dem"))

    # iterate through input points
    for pt in in_points:

        click.echo("Processing {}".format(str(pt[in_id])))

        # find closest stream in BC
        streampt = get_fwa_stream(pt["src_x"], pt["src_y"], epsg_code)

        # if the stream is not in terrestrial BC and fairly far from a stream
        # (say 150m), try using the EPA service
        if streampt["properties"]["bc_ind"] == 'NOTBC' and streampt["properties"]["distance_to_stream"] >= 150:
            streampt = epa_index_point(x, y, epsg_code, 150)

        # add id to point
        streampt["properties"].update({in_id: pt[in_id]})

        # write point to disk as temp geojson
        out_path = os.path.join("tempfiles", "01_points")
        make_sure_path_exists(out_path)
        with open(
            os.path.join(out_path, "{}.geojson".format(str(pt[in_id]))), "w"
        ) as f:
            f.write(json.dumps(streampt))

        if not points_only:

            # canada streams
            if streampt["properties"]["blue_line_key"]:
                wsd = get_fwa_wsd(
                    streampt["properties"]["blue_line_key"],
                    streampt["properties"]["downstream_route_measure"],
                    epsg_code
                )

            # lower 48 usa streams
            elif "comid" in streampt["properties"]:
                wsd = epa_delineate_watershed(
                    streampt["properties"]["comid"],
                    streampt["properties"]["measure"]
                )

            wsd["properties"].update({in_id: pt[in_id]})

            # write watershed
            # - write to 'postprocess' if further processing is needed
            # - write to 'completed' if no postprocessing needed
            wsd_schema = {
                "properties": {
                    "wscode": "str",
                    "localcode": "str",
                    "area_ha": "float",
                    "refine_method": "str",
                    in_id: in_id_type,
                },
                "geometry": "Polygon",
            }
            if wsd["properties"]["refine_method"] != "DEM":
                out_file = os.path.join("tempfiles", "03_complete.gpkg")

            elif wsd["properties"]["refine_method"] == "DEM":
                out_file = os.path.join("tempfiles", "02_postprocess.gpkg")
                get_dem_data(
                    streampt["properties"]["blue_line_key"],
                    streampt["properties"]["downstream_route_measure"],
                    pt[in_id],
                    epsg_code,
                    source_crs,
                    out_file
                )

            # write output wsd
            with fiona.open(
                out_file,
                "w",
                driver="GPKG",
                layer=str(pt[in_id]),
                crs=source_crs,
                schema=wsd_schema,
            ) as dst:
                dst.write(wsd)

            # collect output features
            #out_pts.append(streampt)
            #wsds.append(wsd)


if __name__ == "__main__":
    create_watersheds()
