# bc_hybasins

Derive watersheds upstream of BC hydrometric stations from various sources.

## Requirements
- Python 3.6
- Postgresql / Postgis
- fwakit
- mapshaper
- DEM (BC 25m DEM used but SRTM 1 arc second data should work fine too)

## Download required input data

### FWA (BC)
Load BC Freshwater Atlas (FWA) to postgres via `fwakit`

### USGS WBD (USA)
Download USA NHD watershed definitions (entire USA) from https://nhd.usgs.gov/data.html, and load watersheds of interest to postgres:

```
./scripts/load_usgs.sh
```

### HydroSHEDS
HydroSHEDs data (http://hydrosheds.org/) are freely available but an account is required download, and downloads take some time. Two manual downloads are required for BC coverage, North America and North American Arctic. These are the files retained from the download zips (many other levels are included):

- `hybas_ar_lev12_v1c.shp` - North American Arctic basins level 12
- `hybas_na_lev12_v1c.shp` - North American basins level 12

With these files downloaded, load to postgres with:
```
cd path/to/downloads
./scripts/load_hydrosheds.sh
```



## Usage

```
git clone bc_hybasins
cd bc_hybasins
python bc_hybasins create_prelim
python bc_hybasins refine
python bc_hybasins dump
```
