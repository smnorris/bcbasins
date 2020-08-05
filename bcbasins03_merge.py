from pathlib import Path
import subprocess

import click
import pandas
import geopandas


@click.command()
@click.argument("in_id")
@click.option("--wksp", type=click.Path(exists=True), default="tempfiles")
def merge(wksp, in_id):
    """merge output data
    """
    workpath = Path(wksp)
    outgpkg = Path("watersheds.gpkg")

    # remove output file if it already exists
    if outgpkg.exists():
        outgpkg.unlink()

    # merge points
    # https://stackoverflow.com/questions/48874113/concat-multiple-shapefiles-via-geopandas
    shapefiles = []
    for folder in workpath.iterdir():
        if (folder / "point.shp").exists():
            shapefiles.append(folder / "point.shp")

    gdf = pandas.concat([geopandas.read_file(shp) for shp in shapefiles]).pipe(
        geopandas.GeoDataFrame
    )
    gdf.crs = {"init": "epsg:3005"}
    gdf.to_file("referenced_points.shp", layer="referenced_points", driver="ESRI Shapefile")

    # merge watershed polys
    gdf_list = []
    for folder in workpath.iterdir():
        if (folder / "wsd.shp").exists():
            gdf_list.append(geopandas.read_file(folder / "wsd.shp"))
        elif (folder / "postprocess.shp").exists() and (folder / "ref.shp").exists():
            postprocess = geopandas.read_file(folder / "postprocess.shp")
            ref = geopandas.read_file(folder / "ref.shp")
            # add values to ref shapefile, set from the postprocess file
            ref[in_id].values[:] = postprocess[in_id]
            ref["wscode"].values[:] = postprocess["wscode"]
            ref["localcode"].values[:] = postprocess["localcode"]
            ref["refine_met"].values[:] = "DEM"
            gdf_list.append(postprocess)
            gdf_list.append(ref)

    gdf = pandas.concat(gdf_list).pipe(
        geopandas.GeoDataFrame
    )
    gdf.crs = {"init": "epsg:3005"}

    # dissolve on id, buffer slightly out and back in
    dissolved = gdf.dissolve(by=in_id)
    dissolved["geometry"] = dissolved.buffer(.1).buffer(-.1)
    out = dissolved.reset_index()

    # rather than monkey with shapely geoms, write merged polys to file and
    # remove holes with ogr2ogr
    # (writing shape, it is more tolerant of iffy geometries)
    out.to_file("wsd.shp", driver="ESRI Shapefile")

    cmd = [
        "ogr2ogr",
        "watersheds.shp",
        "-sql",
        f"SELECT {in_id}, wscode, localcode, refine_met, ST_MakePolygon(ST_ExteriorRing(Geometry)) as Geometry FROM wsd",
        "-dialect",
        "SQLITE",
        "wsd.shp"
    ]
    click.echo(" ".join(cmd))
    subprocess.run(cmd)


if __name__ == "__main__":
    merge()
