import os

import requests
import fiona
import click
import bcdata


FWA_API_URL = "https://www.hillcrestgeo.ca/fwa/v1"


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


@click.command()
@click.argument("in_file")
@click.option("--in_layer", "-l", help="Input layer held in in_file")
@click.option("--in_id", "-id", help="Unique id of in_file or in_layer")
@click.option("--points_only", help="Return only points", is_flag=True)
def create_watersheds(in_file, in_layer, in_id, points_only):
    """Create 20k watershed boundaries upstream of provided points
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

    # create temp folder structure
    make_sure_path_exists(os.path.join("tempfiles", "dem"))

    # iterate through input points
    for pt in in_points:

        click.echo("Processing {}".format(str(pt[in_id])))

        # find closest stream
        url = "{}/{},{},{}".format(
            FWA_API_URL + "/nearest_stream", pt["src_x"], pt["src_y"], str(epsg_code)
        )
        # request the closest stream, get first record, add id
        r = requests.get(url)
        streampt = r.json()["features"][0]
        # add unique id to result
        streampt["properties"].update({in_id: pt[in_id]})

        pt_schema = {
            "properties": {
                "linear_feature_id": "int",
                "gnis_name": "str",
                "wscode": "str",
                "localcode": "str",
                "blue_line_key": "int",
                "distance_to_stream": "float",
                "downstream_route_measure": "float",
                in_id: in_id_type,
            },
            "geometry": "Point",
        }

        with fiona.open(
            os.path.join("tempfiles", "01_points.gpkg"),
            "w",
            driver="GPKG",
            layer=str(pt[in_id]),
            crs=source_crs,
            schema=pt_schema,
        ) as dst:
            dst.write(streampt)

        blkey = streampt["properties"]["blue_line_key"]
        meas = streampt["properties"]["downstream_route_measure"]

        if not points_only:
            # get watershed
            url = "{}/{}".format(FWA_API_URL + "/watershed", blkey)
            param = {"downstream_route_measure": meas, "srid": epsg_code}
            r = requests.get(url, params=param)

            wsd = r.json()["features"][0]
            wsd["properties"].update({in_id: pt[in_id]})

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
            # write watershed
            # - write to 'postprocess' if further processing is needed
            # - write to 'completed' if no postprocessing needed
            if wsd["properties"]["refine_method"] == "DEM":
                out_file = os.path.join("tempfiles", "02_postprocess.gpkg")
            else:
                out_file = os.path.join("tempfiles", "03_complete.gpkg")
            with fiona.open(
                out_file,
                "w",
                driver="GPKG",
                layer=str(pt[in_id]),
                crs=source_crs,
                schema=wsd_schema,
            ) as dst:
                dst.write(wsd)

            # if DEM post-processing is required, get required data
            if wsd["properties"]["refine_method"] == "DEM":
                click.echo("requesting additional data for {}".format(pt[in_id]))

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
                param = {"downstream_route_measure": meas, "srid": epsg_code}
                r = requests.get(url, params=param)
                with fiona.Env():
                    with fiona.open(
                        out_file,
                        "w",
                        driver="GPKG",
                        layer=str(pt[in_id]) + "_stream",
                        crs=source_crs,
                        schema=stream_schema,
                    ) as dst:
                        for f in r.json()["features"]:
                            dst.write(f)

                # get hex grid covering watershed to be adjusted
                url = "{}/{}".format(FWA_API_URL + "/watershed_hex", blkey)
                param = {"downstream_route_measure": meas, "srid": epsg_code}
                r = requests.get(url, params=param)
                with fiona.Env():
                    with fiona.open(
                        out_file,
                        "w",
                        driver="GPKG",
                        layer=str(pt[in_id]) + "_hex",
                        crs=source_crs,
                        schema=hex_schema,
                    ) as dst:
                        for f in r.json()["features"]:
                            dst.write(f)
                    # get bounds by opening file just written
                    # NOTE - this will not work if CRS uses degrees
                    with fiona.open(out_file, "r", layer=str(pt[in_id]) + "_hex") as f:
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
                    os.path.join("tempfiles", "dem", str(pt[in_id]) + ".tif"),
                )


if __name__ == "__main__":
    create_watersheds()
