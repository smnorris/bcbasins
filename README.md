# bc_hybasins

Derive watersheds upstream of BC hydrometric stations from various sources.

## Requirements
- Python 3.6
- Postgresql / Postgis
- fwakit
- mapshaper
- DEM (BC 25m DEM used but SRTM 1 arc second data should work fine too)

## Usage

### Download required data

#### FWA

#### USGS
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

```
python 03_create_watersheds.py
```
