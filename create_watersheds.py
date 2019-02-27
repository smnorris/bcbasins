import os
import subprocess

import fiona
import click

import fwakit as fwa
from fwakit import watersheds


def rmshp(shapes):
    """ delete the shapefiles """
    for shp in set(shapes):
        infile = os.path.splitext(shp)[0]
        for suffix in ["shp", "dbf", "shx", "prj", "sbn", "sbx", "shp.xml", "cpg"]:
            if os.path.exists(infile + "." + suffix):
                os.remove(infile + "." + suffix)


def merge_gdb_layers(in_file, out_file, source_field):
    layers = fiona.listlayers(in_file)
    meta = fiona.open(in_file, layer=layers[0]).meta

    meta["driver"] = "ESRI Shapefile"
    meta["schema"]["properties"][source_field] = "str"
    with fiona.open(out_file, "w", **meta) as sink:
        for layer in layers:
            for feature in fiona.open(in_file, layer=layer):
                feature["properties"]["source"] = str(layer)
                sink.write(feature)


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
@click.argument("stations")
@click.option('--station_id', '-id', help='Unique station id', default='station_id')
@click.option('--in_layer', '-l', help='Input layer', default='stations')
@click.option('--out_file', '-o', help='Output shapfile', default='stn_wsds.shp')
@click.option('--db_url', '-db', help='FWA database', envvar='FWA_DB')
def create_watersheds(stations, station_id, in_layer, out_file, db_url):
    """Create 20k watershed boundaries upstream of provided points
    """
    # make a temp data folder in cwd
    make_sure_path_exists("data")

    # load points
    click.echo("Loading input points to postgres")
    db = fwa.util.connect(db_url)

    # todo: check input layer type is point
    db.ogr2pg(stations, in_layer=in_layer, out_layer="stations")

    # reference stations to stream network
    # keep just the closest matches - these points have been manually adjusted
    click.echo("Referencing input points to FWA streams within 100m")
    fwa.reference_points(
        "public.stations", station_id, "public.stations_referenced", 100, closest=True, db=db
    )

    # create preliminary watersheds (unaggregated first order watersheds)
    # Note that this also creates wsdrefine_hexwsd and wsdrefine_streams for
    # post processing the watersheds with DEM
    db["public.wsdrefine_prelim"].drop()
    watersheds.points_to_prelim_watersheds(
        "public.stations_referenced",
        station_id,
        "public.wsdrefine_prelim",
        db=db,
        dissolve=False,
    )

    # Find and add (if necessary) the first order watersheds in which the points lie
    watersheds.add_local_watersheds(
        "public.stations_referenced", station_id, "public.wsdrefine_prelim",
        db=db
    )

    # add watersheds that are outside of BC
    watersheds.add_ex_bc(
        "public.stations",
        "public.stations_referenced",
        station_id,
        "public.wsdrefine_prelim",
        db=db
    )

    # dump data required for processing watersheds with DEM
    db.pg2ogr(
        "SELECT * FROM public.wsdrefine_hexwsd", "ESRI Shapefile", "data/wsdrefine_hex.shp"
    )
    db.pg2ogr(
        """SELECT {}, linear_feature_id AS lnrftrd, blue_line_key AS bllnk, geom
        FROM public.wsdrefine_streams""".format(station_id),
        "ESRI Shapefile",
        "data/wsdrefine_streams.shp",
    )
    fwa.create_geom_from_events("public.stations_referenced", "public.stations_points", db=db)
    db.pg2ogr(
            "SELECT * FROM public.stations_points",
            "ESRI Shapefile",
            "data/wsdrefine_stations.shp",
    )

    # for each watershed where DEM refinement is required, run the job
    watersheds.wsdrefine_dem(
        r"data/wsdrefine_hex.shp",
        r"data/wsdrefine_streams.shp",
        r"data/wsdrefine_stations.shp",
        station_id,
    )

    # load to postgres
    db["public.wsdrefine_dem"].drop()
    db.ogr2pg("data/wsdrefine_dem.shp", out_layer="wsdrefine_dem", s_srs="EPSG:3005", schema="public")

    click.echo("Adding refined watersheds to preliminary watershed table")
    watersheds.add_wsdrefine("public.wsdrefine_prelim", station_id, db=db)

    # dump to shapefile, dissolve in mapshaper, reload
    click.echo("Dumping preliminary watersheds to shapefile and dissolving with mapshaper")
    rmshp("data/wsdrefine_mapshaper.shp")
    rmshp("data/wsdrefine_prelimdiz.shp")
    db.pg2ogr(
        "SELECT {}, geom FROM public.wsdrefine_prelim".format(station_id),
        driver="ESRI Shapefile",
        outfile="data/wsdrefine_mapshaper.shp",
    )
    subprocess.call(
        "mapshaper-xl data/wsdrefine_mapshaper.shp -dissolve {} -o data/wsdrefine_prelimdiz.shp".format(station_id),
        shell=True,
    )

    click.echo("Loading watersheds back to postgres for final cleanup")
    db["public.wsdrefine_prelimdiz"].drop()
    db.ogr2pg("data/wsdrefine_prelimdiz.shp")

    # aggregate with st_union to remove overlaps
    # also, extract just outer ring to remove gaps and do minor buffering
    click.echo("Removing overlaps and cleaning gaps")
    db["public.wsdrefine_agg"].drop()
    sql = """CREATE TABLE public.wsdrefine_agg AS
             SELECT {stn}, st_union(ST_Buffer(ST_Buffer(geom, .001), -.001)) as geom
             FROM public.wsdrefine_prelimdiz
             GROUP BY {stn}""".format(stn=station_id)
    db.execute(sql)
    db["public.wsd"].drop()
    sql = """CREATE TABLE public.wsd AS
             SELECT
               {stn},
               ST_Collect(ST_MakePolygon(geom)) As geom
             FROM (SELECT
                     {stn},
                     ST_ExteriorRing((ST_Dump(geom)).geom) As geom
                   FROM public.wsdrefine_agg) as foo
             GROUP BY {stn}
          """.format(stn=station_id)
    db.execute(sql)

    rmshp(out_file)
    db.pg2ogr("SELECT * FROM public.wsd", "ESRI Shapefile", out_file)


if __name__ == '__main__':
    create_watersheds()
