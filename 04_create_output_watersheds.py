import os
import subprocess

import fiona

import fwakit as fwa
from fwakit import watersheds
from fwakit.util import log


# set up the environment
os.environ["FWA_DB"] = r"postgresql://postgres:postgres@localhost:5432/postgis"


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


# after dem watersheds are created in arc, merge them into a single shapefile
log("Merging gdb feature classes to data/wsdrefine_dem.shp")
merge_gdb_layers("data/fwa_temp.gdb", "data/wsdrefine_dem.shp", "source")

db = fwa.util.connect()
db["public.wsdrefine_dem"].drop()
db.ogr2pg("data/wsdrefine_dem.shp", schema="public")

log("Adding refined watersheds to preliminary watershed table")
watersheds.add_wsdrefine("public.wsdrefine_prelim", "station", db=db)

# dump to shapefile, dissolve in mapshaper, reload
log("Dumping preliminary watersheds to shapefile and dissolving with mapshaper")
rmshp("data/wsdrefine_mapshaper.shp")
rmshp("data/wsdrefine_prelimdiz.shp")
db.pg2ogr(
    "SELECT station, geom FROM public.wsdrefine_prelim",
    driver="ESRI Shapefile",
    outfile="data/wsdrefine_mapshaper.shp",
)
subprocess.call(
    "mapshaper data/wsdrefine_mapshaper.shp -dissolve station -o data/wsdrefine_prelimdiz.shp",
    shell=True,
)

log("Loading watersheds back to postgres for final cleanup")
db = fwa.util.connect()
db["public.wsdrefine_prelimdiz"].drop()
db.ogr2pg("data/wsdrefine_prelimdiz.shp")

# aggregate with st_union to remove overlaps
# also, extract just outer ring to remove gaps and do minor buffering
log("Removing overlaps and cleaning gaps")
db["public.wsdrefine_agg"].drop()
sql = """CREATE TABLE public.wsdrefine_agg AS
         SELECT station, st_union(ST_Buffer(ST_Buffer(geom, .001), -.001)) as geom
         FROM public.wsdrefine_prelimdiz
         GROUP BY station"""
db.execute(sql)
db["public.wsd"].drop()
sql = """CREATE TABLE public.wsd AS
         SELECT
           station,
           ST_Collect(ST_MakePolygon(geom)) As geom
         FROM (SELECT
                 station,
                 ST_ExteriorRing((ST_Dump(geom)).geom) As geom
               FROM public.wsdrefine_agg) as foo
         GROUP BY station
      """
db.execute(sql)

rmshp("data/stn_wsds.shp")
out_file = r"data/stn_wsds.shp"
db.pg2ogr("SELECT * FROM public.wsd", "ESRI Shapefile", out_file)
