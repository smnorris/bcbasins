# get data and extract
wget https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/National/GDB/NATIONAL_WBD_GDB.zip
unzip GDB/NATIONAL_WBD_GDB.zip

# load to postgres
psql -c 'CREATE SCHEMA IF NOT EXISTS usgs'
ogr2ogr \
  -f PostgreSQL \
  PG:'host=localhost user=postgres dbname=postgis password=postgres' \
  -lco OVERWRITE=YES \
  -t_srs EPSG:3005 \
  -lco SCHEMA=usgs \
  -lco GEOMETRY_NAME=geom \
  -nln wbdhu12 \
  -nlt PROMOTE_TO_MULTI \
  -dialect SQLITE \
  -sql "SELECT * FROM WBDHU12 WHERE states LIKE '%%CN%%' OR states LIKE '%%WA%%' OR states LIKE '%%AK%%' OR states LIKE '%%ID%%' OR states LIKE '%%MT%%'" \
  NATIONAL_WBD_GDB/NATIONAL_WBD_GDB.gdb

# ignore the various errors on load....
# index the columns of interest
psql -c "CREATE INDEX ON usgs.wbdhu12 (huc12)"
psql -c "CREATE INDEX ON usgs.wbdhu12 (tohuc)"