# bcbasins

Derive watersheds upstream of points. Uses the [BC Freshwater Atlas](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/freshwater) and [various other sources for neigbouring jurisdictions](notes_cross_boundary.md).

## Software requirements

- ArcGIS
- Python 3

## Installation / Setup

1. Requirements for scripts 1 and 3 are best installed to a Python virtual environment:

        python -m pip install --user virtualenv
        SET PATH=C:\Users\%USERNAME%\AppData\Roaming\Python\Python36\Scripts;%PATH%
        virtualenv venv
        venv\Scripts\activate
        pip install -r requirements.txt


## Usage

First, prepare an input point layer with a unique id (default is `station`). Take care to ensure that the points are closest to the stream with which you want them to be associated - the script simply generates the watershed upstream of the closest stream.  Note also that the script does not consider streams with no value for `local_watershed_code`.

To activate the virtual environment for scripts 1 and 3, double click on `bcbasins.bat`

1. Run the first script:

        (venv)> python bcbasins01_load.py <in_file> --in_layer <in_layer> --in_id <unique_id>


2. From the start menu, open a new `Python Command Prompt`, navigate to the project folder and run the ArcGIS DEM postprocessing of the watersheds:

        (arcgispro-py3)> python bcbasins02_postprocess.py

3. Back in the virtualenv command prompt, merge the output watersheds:

        (venv)> python bcbasins03_merge.py

Output watersheds and referenced points are in the `watersheds.gpkg` file. You may want to run a final cleanup by extracting just the exterior rings with this command, run from the virtualenv:

    ogr2ogr -f GPKG watersheds.gpkg -sql "SELECT station, wscode, localcode, refine_met, ST_MakePolygon(ST_ExteriorRing(geom)) FROM watersheds_src" -dialect SQLITE watersheds.gpkg -nln watersheds

## Note

Defining very large watersheds is currently not supported - the process will run out of memory.

For large waterseds (eg Peace, Fraser, Thompson, Columbia etc), run the query `fwa_watershedrefined(blue_line_key, measure)` on a machine with the FWA postgres db installed and at least 16-32G memory.