# bcbasins

Derive watersheds upstream of BC hydrometric stations from [BC Freshwater Atlas](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/freshwater) and [various other sources for neigbouring jurisdictions](notes_cross_boundary.md).

## Software requirements

- Python (tested on v3.6 for non ArcGIS components, 2.7 for ArcGIS script)
- PostgreSQL / PostGIS (tested on v10.4/2.4.4)
- ArcGIS (tested with v10.3)
- GDAL (with ogr2ogr available at the command line)
- mapshaper (tested with 0.4.81)
- wget (optional, for scripted download of USA NHD data)

## Data requirements

Scripts and instructions for download and preparation of source watershed/basin polygons are noted below.  


A relatively high resolution DEM covering BC is required to refine first order watersheds in which a site is located (truncate the watershed at the site by using the site as a 'pour point' or 'outlet'). The script has been tested with the [BC 25m DEM](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/topographic-data/elevation/digital-elevation-model) which is not publicly available. Alternatively, [SRTM 1 arc second (~30m) DEM](https://lta.cr.usgs.gov/SRTM1Arc) may be of sufficent resolution and is [easily and freely available via AWS](https://registry.opendata.aws/terrain-tiles/).

## Installation

1. Install the various software packages noted above
2. Install required Python libraries:
        
        pip install --user requirements.txt

    Note that when running the scripts on Windows, you may have to [install fiona - and perhaps gdal - manually from pre-built wheels](https://github.com/Toblerity/Fiona#windows). 

3. The data load scripts assume that postgres environment variables are set to point to the database to be used. Set and adjust these as required:
   
        export PGHOST=localhost
        export PGPORT=5432
        export PGDATABASE=postgis
        export PGUSER=postgres

## Download required data

### FWA

If BC FWA data is not already loaded to postgres, load with the provided script. This will take some time and requires >20G of free disk space.
```
./01_load_fwa.sh
```

### USGS

Download USA NHD watershed definitions (entire USA) from https://nhd.usgs.gov/data.html, and load watersheds of interest to postgres. Again, this is a large download.
```
./02_load_usgs.sh
```

### HydroSHEDS

HydroSHEDs data (http://hydrosheds.org/) are freely available but an account is required download, and downloads take some time. Two manual downloads are required for BC coverage, North America and North American Arctic. Once you have manually downloaded these datasets, these are the two files to retain:

- `hybas_ar_lev12_v1c.shp` - North American Arctic basins level 12
- `hybas_na_lev12_v1c.shp` - North American basins level 12

With these files downloaded, load to postgres with:
```
./03_load_hydrosheds.sh
```

### DEM
No script is included for DEM data download, but DEM GeoTIFFs are available via `https://s3.amazonaws.com/elevation-tiles-prod/geotiff/{z}/{x}/{y}.tif`, and a [Python interface is available](https://github.com/bopen/elevation).

## Create watersheds

First, create the preliminary watersheds. This creates a table of all watersheds upstream of the provided points. It also notes the first order watershed in which the point is located and determines whether this needs to be refined. If the watershed is to be refined, the script generates the temporary shapefiles needed for processing in ArcGIS.  

```
python 04_create_prelim_watersheds.py
```

Next, refine the watersheds with the DEM using ArcGIS. This attempts to terminate the watershed at site location. Only single line streams are processed with this methond, watersheds on a double line stream are truncated directly at the site location using PostGIS in the step above. Before running the ArcGIS script, depending on your setup you may want to point to the 64bit geoprocessing version of Python:

```
set PATH="E:\sw_nt\Python27\ArcGISx6410.3";"E:\sw_nt\Python27\ArcGISx6410.3\Scripts";"C:\Users\sinorris\AppData\Roaming\Python\Scripts";%PATH%
python 05_create_prelim_watersheds.py
```

Move the .gdb created by above script to `/data/fwa_temp.gdb`, then aggregate the watersheds and dump to output shapefile:  

```
python 06_create_output_watersheds.py
```
