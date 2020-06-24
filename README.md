# bcbasins

Derive watersheds upstream of points. Uses the [BC Freshwater Atlas](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/freshwater) and [various other sources for neigbouring jurisdictions](notes_cross_boundary.md).

## Software requirements

- Python 3
- ArcGIS Desktop and Windows for script #2

## Installation / Setup

Requirements for scripts 1 and 3 are best installed to a Python virtual environment. If installing on Windows, download the Fiona and GDAL precompiled wheels from https://www.lfd.uci.edu/~gohlke/pythonlibs/ and adjust the paths in `requirements.txt` to point to these files. A virtualenv is already set up in the project folder on GTS but this would be the general sequence of commands to recreate it:

        python -m pip install --user virtualenv
        SET PATH=C:\Users\%USERNAME%\AppData\Roaming\Python\Python36\Scripts;%PATH%
        virtualenv venv
        venv\Scripts\activate
        pip install -r requirements.txt


## Usage

Prepare an input point layer with a unique id (default is `station`) and with points in a projected coordinate system (`EPSG:4326` / lat-lon is not supported). Take care to ensure that the points are closest to the stream with which you want them to be associated - the script simply generates the watershed upstream of the closest stream.  Note also that the script does not consider streams with no value for `local_watershed_code` - if your site is on a side channel, ensure that the channel has a value for `local_watershed_code`.

To open a command prompt with the virtual environment for scripts 1 and 3 activated, double click on `bcbasins.bat`

1. Run the first script:

        (venv)> python bcbasins01_load.py <in_file> <unique_id> --in_layer <in_layer>


2. From the start menu, open a new `Python Command Prompt`, navigate to the project folder and run the ArcGIS DEM postprocessing of the watersheds:

        (arcgispro-py3)> python bcbasins02_postprocess.py

3. Back in the virtualenv command prompt, merge the output watersheds:

        (venv)> python bcbasins03_merge.py <unique_id>

Output watersheds and referenced points are in the `watersheds.gpkg` file. You may want to run a final cleanup by extracting just the exterior rings with this command, run from the virtualenv:

    (venv)> ogr2ogr -f GPKG watersheds.gpkg -sql "SELECT station, wscode, localcode, refine_met, ST_MakePolygon(ST_ExteriorRing(geom)) FROM watersheds_src" -dialect SQLITE watersheds.gpkg -nln watersheds

## Note

Defining very large watersheds is currently not supported - the database server processing the aggregation will run out of memory.

For large waterseds (eg Peace, Fraser, Thompson, Columbia etc), run the query `fwa_watershedrefined(blue_line_key, measure)` on a machine with the FWA postgres db installed and at least 16-32G memory.