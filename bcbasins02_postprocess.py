import glob
import os
import sys
import uuid

import arcpy


def create_wksp(path, gdb):
    """Create a .gdb workspace in given path
    """
    wksp = os.path.join(path, gdb)
    # create the workspace if it doesn't exist
    if not arcpy.Exists(wksp):
        arcpy.CreateFileGDB_management(path, gdb)
    return os.path.join(path, gdb)


def wsdrefine_dem(in_wsd, in_stream, in_dem, out_wsd):
    """
    Refine a watershed polygon - extract only areas that flow to supplied stream segment.
    - in_wsd:  feature class holding watershed area to be refined
    - in_stream: feature class holding stream to be used as 'pour points'
    """

    # get spatial analyst and set env
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        raise EnvironmentError("Spatial Analyst license unavailable")

    arcpy.env.workspace = "IN_MEMORY"

    # environment settings
    arcpy.env.overwriteOutput = True
    extent = arcpy.Describe(in_wsd).extent
    arcpy.env.extent = extent

    # read inputs
    arcpy.MakeFeatureLayer_management(in_stream, "streams_fl")
    arcpy.MakeFeatureLayer_management(in_wsd, "wsd_fl")

    print("  - writing wsd to temp fc")

    # write the watershed to a feature class so we can get the extent
    # and create mask
    arcpy.Dissolve_management("wsd_fl", "wsd_fc_tmp")

    # set extent to wsd polygon
    arcpy.env.mask = "wsd_fc_tmp"
    extent = arcpy.Describe("wsd_fc_tmp").extent
    arcpy.env.extent = extent

    print("  - writing streams to raster")
    # for some reason the stream raster doesn't overwrite the existing output
    # as workaround, create raster using unique name
    streams_raster = "stream_" + str(uuid.uuid4())
    arcpy.FeatureToRaster_conversion("streams_fl", "linear_fea", streams_raster, "25")

    # fill the dem, calculate flow direction and create watershed raster
    print("  - filling DEM")
    fill = arcpy.sa.Fill(in_dem, 100)
    print("  - calculating flow direction")
    flow_direction = arcpy.sa.FlowDirection(fill, "NORMAL")
    print("  - creating DEM based watershed")
    wsd_grid = arcpy.sa.Watershed(flow_direction, streams_raster)

    # check to make sure there is a result - if all output raster is null,
    # do not try to create a watershed polygon output
    out_is_null = arcpy.sa.IsNull(wsd_grid)
    check_min_result = arcpy.GetRasterProperties_management(out_is_null, "MINIMUM")
    check_min = check_min_result.getOutput(0)
    check_max_result = arcpy.GetRasterProperties_management(out_is_null, "MAXIMUM")
    check_max = check_max_result.getOutput(0)
    if "0" in (check_min, check_max):
        print("  - writing new watershed to %s" % out_wsd)
        arcpy.RasterToPolygon_conversion(wsd_grid, out_wsd, "SIMPLIFY")
        return out_wsd
    else:
        return None


def postprocess(args):
    """Run postprocessing of watershed with DEM
    """
    # find input shapes
    if len(args) > 1:
        wksp = args[1]
    else:
        wksp = "tempfiles"

    # run the dem postprocessing
    for folder in glob.glob(os.path.join(wksp, "*")):

        # look for required files
        if (
            os.path.exists(os.path.join(folder, "hex.shp"))
            and os.path.exists(os.path.join(folder, "str.shp"))
            and os.path.exists(os.path.join(folder, "dem.tif"))
        ):

            print("Postprocessing " + folder)

            # run the job
            wsdrefine_dem(
                os.path.join(folder, "hex.shp"),
                os.path.join(folder, "str.shp"),
                os.path.join(folder, "dem.tif"),
                os.path.join(folder, "ref.shp"),
            )

            # make schema of ref shapefile match the rest of the sources
            arcpy.AddField_management(
                os.path.join(folder, "ref.shp"), "station", "TEXT", field_length=80
            )
            arcpy.AddField_management(
                os.path.join(folder, "ref.shp"), "wscode", "TEXT", field_length=80
            )
            arcpy.AddField_management(
                os.path.join(folder, "ref.shp"), "localcode", "TEXT", field_length=80
            )
            arcpy.AddField_management(
                os.path.join(folder, "ref.shp"), "area_ha", "FLOAT"
            )
            arcpy.AddField_management(
                os.path.join(folder, "ref.shp"), "refine_met", "TEXT", field_length=80
            )
            arcpy.DeleteField_management(os.path.join(folder, "ref.shp"), "Id")
            arcpy.DeleteField_management(os.path.join(folder, "ref.shp"), "gridcode")

            # get watershed code values from postprocess.shp
            with arcpy.da.SearchCursor(
                os.path.join(folder, "postprocess.shp"), ["wscode", "localcode"]
            ) as cursor:
                for row in cursor:
                    wscode = row[0]
                    localcode = row[1]

            # set station/wscode values in the ref shapefile
            with arcpy.da.UpdateCursor(
                os.path.join(folder, "ref.shp"),
                ["station", "wscode", "localcode", "refine_met"],
            ) as cursor:
                for row in cursor:
                    row[0] = os.path.basename(folder)[2:]
                    row[1] = wscode
                    row[2] = localcode
                    row[3] = "DEM"
                    cursor.updateRow(row)

    # merge all outputs
    merge_layers = []
    for folder in glob.glob(os.path.join(wksp, "*")):
        wsd = os.path.join(folder, "wsd.shp")
        ref = os.path.join(folder, "ref.shp")
        postprocess = os.path.join(folder, "postprocess.shp")
        if os.path.exists(wsd):
            merge_layers.append(wsd)
        elif os.path.exists(ref) and os.path.exists(postprocess):
            merge_layers.append(ref)
            merge_layers.append(postprocess)

    print("Creating output watersheds.gdb")
    print(len(merge_layers))
    print(merge_layers)
    create_wksp(os.getcwd(), "watersheds.gdb")
    arcpy.Merge_management(
        merge_layers, os.path.join("watersheds.gdb", "watersheds_merged")
    )
    fields = ["station", "wscode", "localcode", "refine_met"]
    arcpy.Dissolve_management(
        os.path.join("watersheds.gdb", "watersheds_merged"),
        os.path.join("watersheds.gdb", "watersheds_dissolved"),
        fields,
    )


if __name__ == "__main__":
    postprocess(sys.argv)
