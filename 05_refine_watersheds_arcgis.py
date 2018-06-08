from fwakit import watersheds_arcgis

watersheds_arcgis.wsdrefine_dem(
    r'data\wsdrefine_hex.shp',
    r'data\wsdrefine_streams.shp',
    'station',
    r'Q:\dsswhse\Data\Base\DEMs Hillshades\Base20\BC DEM.gdb\bc_dem',
    in_mem=True
)
