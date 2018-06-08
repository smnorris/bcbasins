# BC cross boundary watershed delineation

## Canada

- the National Hydrographic Network does not include detailed watershed definitions, only large workareas.


### Alberta

Province of Alberta data are available and can be loaded to postgres, however HydroSHEDS data are adequate for our purposes.

```
wget https://extranet.gov.ab.ca/srd/geodiscover/srd_pub/inlandWaters/ArcHydro/AlbertaArcHydroPhase2.zip
unzip AlbertaArcHydroPhase2.zip
ogr2ogr --config PG_USE_COPY YES -t_srs EPSG:3005 -f PostgreSQL PG:"host=localhost user=postgres dbname=postgis password=postgres" -lco OVERWRITE=YES -lco SCHEMA=temp -lco GEOMETRY_NAME=geom -nln catchment_hayriver AlbertaArcHydroPhase2Vector.gdb Catchment_HayRiver

ogr2ogr --config PG_USE_COPY YES -t_srs EPSG:3005 -f PostgreSQL PG:"host=localhost user=postgres dbname=postgis password=postgres" -lco OVERWRITE=YES -lco SCHEMA=temp -lco GEOMETRY_NAME=geom -nln catchment_peaceriver AlbertaArcHydroPhase2Vector.gdb Catchment_PeaceRiver

ogr2ogr --config PG_USE_COPY YES -t_srs EPSG:3005 -f PostgreSQL PG:"host=localhost user=postgres dbname=postgis password=postgres" -lco OVERWRITE=YES -lco SCHEMA=temp -lco GEOMETRY_NAME=geom -nln catchment_liardriver AlbertaArcHydroPhase2Vector.gdb Catchment_LiardRiver
```

### Yukon
1 M data available, and placer watersheds
ftp://ftp.geomaticsyukon.ca/GeoYukon/Biophysical/Watersheds_1M/
ftp://ftp.geomaticsyukon.ca/GeoYukon/Mining/Placer_Watersheds_50k/

### NWT
Nothing listed at http://www.geomatics.gov.nt.ca/dldsoptions.aspx


## USA

- NHD data is available for download from https://nhd.usgs.gov/data.html
- navigation service available for lower 48 using NHDPlus V2.1 via EPA
- watershed boundaries are also available via this API as well: 
    - https://my.usgs.gov/confluence/display/qwdp/Networked+Linked+Data+Index
    - https://cida.usgs.gov/nldi/swagger-ui.html
- NHDPlus highres BETA is in production for WA/ID/MT https://nhd.usgs.gov/NHDPlus_HR.html (10m DEM)
