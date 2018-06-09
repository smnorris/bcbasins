# bcbasins

Derive watersheds upstream of BC hydrometric stations from various sources.

## Requirements

- Python 3.6
- PostgreSQL / PostGIS
- ArcGIS 10.3
- fwakit
- mapshaper
- DEM (BC 25m DEM used but publicly available SRTM 1 arc second may work as well)

## Setup

On Windows machine where ArcGIS processing is done, set the PATH to the 64bit Python:
```
set PATH="E:\sw_nt\Python27\ArcGISx6410.3";"E:\sw_nt\Python27\ArcGISx6410.3\Scripts";"C:\Users\sinorris\AppData\Roaming\Python\Scripts";%PATH%
```

### Download required data

#### FWA
If BC FWA data is not already loaded to postgres, load with the provided script
```
./01_load_fwa.sh
```

#### USGS
Download USA NHD watershed definitions (entire USA) from https://nhd.usgs.gov/data.html, and load watersheds of interest to postgres:
```
./02_load_usgs.sh
```

#### HydroSHEDS
HydroSHEDs data (http://hydrosheds.org/) are freely available but an account is required download, and downloads take some time. Two manual downloads are required for BC coverage, North America and North American Arctic. These are the files retained from the download zips (many other levels are included):

- `hybas_ar_lev12_v1c.shp` - North American Arctic basins level 12
- `hybas_na_lev12_v1c.shp` - North American basins level 12

With these files downloaded, load to postgres with:
```
./03_load_hydrosheds.sh
```


## Create watersheds

First, create the preliminary watersheds. This creates a table of all watersheds upstream of the provided points. It also notes the first order watershed in which the point is located and determines whether this needs to be refined. If it is to be refined, it generates the inputs needed for the process.  

```
python 04_create_prelim_watersheds.py
```

Next, take the results of above and refine the first order watersheds as required with the DEM using ArcGIS:  

```
python 05_create_prelim_watersheds.py
```

Move the .gdb created by above script to `/data/fwa_temp.gdb`, then  aggregate the watersheds and dump to output shapefile:  

```
python 06_create_output_watersheds.py
```
