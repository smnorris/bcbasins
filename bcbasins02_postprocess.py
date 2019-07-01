import os
import sys

import arcpy


def create_wksp(path, gdb):
    """
    Create a .gdb workspace in given path
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
    if arcpy.Exists("streams_pourpt"):
        arcpy.Delete_management("streams_pourpt")
    arcpy.FeatureToRaster_conversion("streams_fl", "bllnk", "streams_pourpt", "25")

    # fill the dem, calculate flow direction and create watershed raster
    print("  - filling DEM")
    fill = arcpy.sa.Fill(in_dem, 100)
    print("  - calculating flow direction")
    flow_direction = arcpy.sa.FlowDirection(fill, "NORMAL")
    print("  - creating DEM based watershed")
    wsd_grid = arcpy.sa.Watershed(flow_direction, "streams_pourpt")

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
    """Process all files in the input folder"""
    # find input shapes
    if len(args) > 1:
        wksp = args[1]
    else:
        wksp = "tempfiles/02_postprocess.gpkg"
    arcpy.env.workspace = wksp
    to_process = arcpy.ListFeatureClasses("*_hex")

    # create output wksp
    #create_wksp("tempfiles", "02b_postprocess_out.gdb")

    for in_wsd in to_process:

        # check all files are present
        pt_id = in_wsd.split(".")[0][-4]
        print("Postprocessing "+pt_id)
        in_stream = os.path.join(wksp, pt_id + "_stream")
        in_dem = os.path.join("tempfiles", "dem", pt_id + "_dem.tif")

        # run the job
        wsdrefine_dem(
            in_wsd,
            in_stream,
            in_dem,
            os.path.join(wksp, pt_id + "_processed")
        )


if __name__ == "__main__":
    postprocess(sys.argv)
