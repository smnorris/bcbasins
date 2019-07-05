from pathlib import Path


import click
import pandas
import geopandas


def multi2single(gdf):
    """multi to single is not a geopandas builtin
    https://github.com/geopandas/geopandas/issues/369
    """
    gdf_singlepoly = gdf[gdf.geometry.type == "Polygon"]
    gdf_multipoly = gdf[gdf.geometry.type == "MultiPolygon"]

    for i, row in gdf_multipoly.iterrows():
        Series_geometries = pandas.Series(row.geometry)
        df = pandas.concat(
            [geopandas.GeoDataFrame(row, crs=gdf_multipoly.crs).T]
            * len(Series_geometries),
            ignore_index=True,
        )
        df["geometry"] = Series_geometries
        gdf_singlepoly = pandas.concat([gdf_singlepoly, df])

    gdf_singlepoly.reset_index(inplace=True, drop=True)
    return gdf_singlepoly


@click.command()
@click.option("--wksp", type=click.Path(exists=True), default="tempfiles")
@click.option(
    "--in_id", "-id", help="Unique id of in_file or in_layer", default="station"
)
def merge(wksp, in_id):
    """merge output data
    """
    workpath = Path(wksp)
    outgpkg = Path("watersheds.gpkg")

    # remove output file if it already exists
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
    gdf.to_file("watersheds.gpkg", layer="referenced_points", driver="GPKG")

    # merge watershed polys
    shapefiles = []
    for folder in workpath.iterdir():
        if (folder / "wsd.shp").exists():
            shapefiles.append(folder / "wsd.shp")
        elif (folder / "postprocess.shp").exists() and (folder / "ref.shp").exists():
            shapefiles.append(folder / "postprocess.shp")
            shapefiles.append(folder / "ref.shp")

    gdf = pandas.concat([geopandas.read_file(shp) for shp in shapefiles]).pipe(
        geopandas.GeoDataFrame
    )
    gdf.crs = {"init": "epsg:3005"}

    # dissolve on id, buffer slightly out and back in
    dissolved = gdf.dissolve(by=in_id)
    dissolved["geometry"] = dissolved.buffer(.1).buffer(-.1)
    out = dissolved.reset_index()
    out.to_file("watersheds.gpkg", layer="watersheds_src", driver="GPKG")

    # run this after to extract only exterior rings
    click.echo(
        """ogr2ogr -f GPKG t.gpkg -sql "SELECT station, wscode, localcode, refine_met, ST_MakePolygon(ST_ExteriorRing(geom)) FROM watersheds_src" -dialect SQLITE watersheds.gpkg -nln watersheds"""
    )


if __name__ == "__main__":
    merge()
