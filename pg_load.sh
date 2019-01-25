# --------------------------------------------
# First, BC FWA
# --------------------------------------------

# load individual files and then remove - just to save space
fwakit download -f FWA_BC.gdb.zip
fwakit create-db # creates types even if db exists
fwakit load
rm -r fwakit_downloads/FWA_BC.gdb
fwakit download -f FWA_STREAM_NETWORKS_SP.gdb.zip
fwakit load -l fwa_stream_networks_sp
rm -r fwakit_downloads/FWA_STREAM_NETWORKS_SP.gdb
fwakit download -f FWA_WATERSHEDS_POLY.gdb.zip
fwakit load -l fwa_watersheds_poly_sp
rm -r fwakit_downloads/FWA_WATERSHEDS_POLY.gdb

# we don't have much need for the linear boundaries
fwakit download -f FWA_LINEAR_BOUNDARIES_SP.gdb.zip
fwakit load -l fwa_linear_boundaries_sp
rm -r fwakit_downloads/FWA_LINEAR_BOUNDARIES_SP.gdb.zip

fwakit clean

# --------------------------------------------
# USA
# --------------------------------------------
# get data and extract
wget https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/National/GDB/WBD_National_GDB.zip

unzip WBD_National_GDB.zip

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
  -nlt MULTIPOLYGON \
  -dialect SQLITE \
  -sql "SELECT * FROM WBDHU12 WHERE states LIKE '%%CN%%' OR states LIKE '%%WA%%' OR states LIKE '%%AK%%' OR states LIKE '%%ID%%' OR states LIKE '%%MT%%'" \
  WBD_National_GDB.gdb

# ignore the various errors on load....
# index the columns of interest
psql -c "CREATE INDEX ON usgs.wbdhu12 (huc12)"
psql -c "CREATE INDEX ON usgs.wbdhu12 (tohuc)"

# --------------------------------------------
# Canada, ex BC
# --------------------------------------------
# hydrosheds shapefiles must be manually downloaded from source,
# so I've cached them here:
# https://www.hillcrestgeo.ca/outgoing/public/hydrosheds.zip

wget https://www.hillcrestgeo.ca/outgoing/public/hydrosheds.zip
unzip hydrosheds.zip

psql -c 'CREATE SCHEMA IF NOT EXISTS hydrosheds'

# Write to two tables and combine...
ogr2ogr \
  -f PostgreSQL \
  PG:'host=localhost user=postgres dbname=postgis password=postgres' \
  -lco OVERWRITE=YES \
  -t_srs EPSG:3005 \
  -lco SCHEMA=hydrosheds \
  -lco GEOMETRY_NAME=geom \
  -nlt PROMOTE_TO_MULTI \
  hybas_ar_lev12_v1c/hybas_ar_lev12_v1c.shp

ogr2ogr \
  -f PostgreSQL \
  PG:'host=localhost user=postgres dbname=postgis password=postgres' \
  -t_srs EPSG:3005 \
  -lco SCHEMA=hydrosheds \
  -lco GEOMETRY_NAME=geom \
  -nlt PROMOTE_TO_MULTI \
  hybas_na_lev12_v1c/hybas_na_lev12_v1c.shp

psql -c "ALTER TABLE hydrosheds.hybas_na_lev12_v1c DROP COLUMN ogc_fid"
psql -c "ALTER TABLE hydrosheds.hybas_ar_lev12_v1c DROP COLUMN ogc_fid"

psql -c "ALTER TABLE hydrosheds.hybas_na_lev12_v1c RENAME TO hybas_lev12_v1c"
psql -c "INSERT INTO hydrosheds.hybas_lev12_v1c SELECT * FROM hydrosheds.hybas_ar_lev12_v1c"
psql -c "DROP TABLE hydrosheds.hybas_ar_lev12_v1c"

psql -c "ALTER TABLE hydrosheds.hybas_lev12_v1c ADD PRIMARY KEY (hybas_id)"
psql -c "CREATE INDEX ON hydrosheds.hybas_lev12_v1c (next_down)"