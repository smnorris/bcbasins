# bcbasins

Derive watersheds upstream of points. Uses the [BC Freshwater Atlas](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/freshwater) and [various other sources for neigbouring jurisdictions](notes_cross_boundary.md).

## Software requirements

- ArcGIS
- Python

## Installation / Setup

1. Create virtual environment and install Python requirements:

        python -m pip install --user virtualenv
        SET PATH=C:\Users\%USERNAME%\AppData\Roaming\Python\Python36\Scripts;%PATH%
        virtualenv venv
        venv\Scripts\activate
        pip install -r requirements.txt

3. (Optional) Define the `FWA_DB` connection as an environment variable:

        SET FWA_DB=postgresql://username:password@host:5432/postgis


## Usage

First, prepare an input point layer with a unique id. Take care to ensure that the points are closest to the FWA stream with which you want them to be associated - the script simply generates the watershed upstream of the closest stream.  Note also that the script does not consider streams with no value for `local_watershed_code`.

Run the first script, loading data:

    python wsds01_load.py <in_file> --in_layer <in_layer> --in_id <unique_id>

Postprocess the results with the DEM:

    python wsds02_postprocess.py

Finally, merge outputs:

    python wsds03_merge.py

Output watersheds are the `wsds_output` folder.

## Notes

- defining very large watersheds is currently very slow and not recommended (eg Peace River, Fraser River)