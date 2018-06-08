# load hydrosheds to postgres
# shapefiles must be manually downloaded and unzipped.

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