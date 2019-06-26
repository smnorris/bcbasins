import os
import json

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
            for f in src:
                x, y = f["geometry"]["coordinates"]
                in_points.append(
                    {in_id: f["properties"][in_id], "src_x": x, "src_y": y}
                )

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

        # write new point to disk
        out_path = os.path.join("tempfiles", "01_points")
        make_sure_path_exists(out_path)
        with open(
            os.path.join(out_path, "{}.geojson".format(str(pt[in_id]))), "w"
        ) as f:
            f.write(json.dumps(streampt))

        blkey = streampt["properties"]["blue_line_key"]
        meas = streampt["properties"]["downstream_route_measure"]

        if not points_only:
            # get watershed
            url = "{}/{}".format(FWA_API_URL + "/watershed", blkey)
            param = {"downstream_route_measure": meas, "srid": epsg_code}
            r = requests.get(url, params=param)

            wsd = r.json()["features"][0]
            wsd["properties"].update({in_id: pt[in_id]})

            # write watershed
            # - write to 'postprocess' folder if further processing is needed
            # - write to 'completed' if no postprocessing needed
            if wsd["properties"]["refine_method"] == "DEM":
                out_path = os.path.join("tempfiles", "02_postprocess")
            else:
                out_path = os.path.join("tempfiles", "03_complete")
            make_sure_path_exists(out_path)
            with open(
                os.path.join(out_path, "{}.geojson".format(str(pt[in_id]))), "w"
            ) as f:
                f.write(json.dumps(wsd))

            # if DEM post-processing is required, get required data
            if wsd["properties"]["refine_method"] == "DEM":
                click.echo("requesting additional data for {}".format(pt[in_id]))

                # get stream  (pour point)
                url = "{}/{}".format(FWA_API_URL + "/watershed_stream", blkey)
                param = {"downstream_route_measure": meas, "srid": epsg_code}
                r = requests.get(url, params=param)
                with open(
                    os.path.join(out_path, "{}_stream.geojson".format(str(pt[in_id]))),
                    "w",
                ) as f:
                    f.write(json.dumps(wsd))

                # get hex grid covering watershed
                url = "{}/{}".format(FWA_API_URL + "/watershed_hex", blkey)
                param = {"downstream_route_measure": meas, "srid": epsg_code}
                r = requests.get(url, params=param)
                with open(
                    os.path.join(out_path, "{}_hex.geojson".format(str(pt[in_id]))), "w"
                ) as f:
                    f.write(json.dumps(wsd))

                # expand bounds of hex layer by 250m, get DEM for expanded bounds
                with fiona.Env():
                    with fiona.open(
                        os.path.join(out_path, "{}_hex.geojson".format(str(pt[in_id]))),
                        "r",
                    ) as f:
                        bounds = f.bounds
                expansion = 250
                xmin = bounds[0] - expansion
                ymin = bounds[1] - expansion
                xmax = bounds[2] + expansion
                ymax = bounds[3] + expansion
                expanded_bounds = (xmin, ymin, xmax, ymax)
                bcdata.get_dem(
                    expanded_bounds,
                    os.path.join(out_path, "{}_dem.tif".format(str(pt[in_id]))),
                )


if __name__ == "__main__":
    create_watersheds()
