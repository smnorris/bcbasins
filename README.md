# bcbasins

Derive watersheds upstream of points. Uses the [BC Freshwater Atlas](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/freshwater) and [various other sources for neigbouring jurisdictions](notes_cross_boundary.md).

## Software requirements

- Python 3.6
- NodeJS and Mapshaper (tested with Mapshaper v0.4.105)
- PostgreSQL/PostGIS (or just access to a server, see [gis_droplet](https://github.com/smnorris/gis_droplet) repository for a sample setup and scripts)


## Data requirements

An input point layer with a unique id.

For the script to work properly, points must be closest to the stream with which they should be associated (for example, a point should be closest to the centerline of the river that it should be associated, not any minor side tributary).


## Installation / Setup

Presuming ArcGIS and Python are already installed:

1. Install Mapshaper
    - download NodeJS 64bit binary for Windows, unzip
    - in command prompt, navigate to uznipped node folder
    - `npm install -g mapshaper`

2. Create virtual environment and install Python requirements:

        python -m pip install --user virtualenv
        SET PATH=C:\Users\%USERNAME%\AppData\Roaming\Python\Python36\Scripts;%PATH%
        virtualenv venv
        venv\Scripts\activate
        pip install -r requirements.txt

3. (Optional) Define the `FWA_DB` connection as an environment variable:

        SET FWA_DB=postgresql://username:password@host:5432/postgis


## Create watersheds

    python create_watersheds.py
