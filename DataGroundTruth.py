import sys
import os

import geopandas as gpd
import pandas as pd

from osgeo import gdal

class DataGroundTruth(object):

    def __init__(self, path_dir):
        if path_dir[-1] == '/':
            self.path_dir = path_dir
        else:
            self.path_dir = path_dir + '/'


    def get_file_paths(self, file_dir):
        file_names = []
        # loop over all filenames
        for file in os.listdir(file_dir):
            # get filename
            filename = os.fsdecode(file)
            # if the filename contains .tif -> it is a raster file
            if filename.endswith(".tif"):
                file_names.append(filename)
        return file_names


    def get_extend(self, file_path):
        src = gdal.Open(file_path)
        ulx, xres, xskew, uly, yskew, yres  = src.GetGeoTransform()
        lrx = ulx + (src.RasterXSize * xres)
        lry = uly + (src.RasterYSize * yres)
        return(ulx,uly,lrx,lry)


    def create_raster(self, path_dir, path_shp, name_vector, name_layer):
        """
        raterizes vector layer

        input:
        path_dir (string) - path to raster directory (exp. "/media/philipp/DATA/2018_tamsweg/")
        path_shp (string) - path to vector file
        name_vector (string) - name of vector (exp. "gis_df_wwie_2020_typ_177")
        name_layer (string) - name of layer to be raterized (exp. "typ")
        """

        # raster paths
        path_dir_in = path_dir + "ortho/"
        path_dir_out = path_dir + "ground_truth/"

        # get all file paths in directory
        file_paths = self.get_file_paths(path_dir_in)

        # pixel resolution
        pixel = 0.2

        size = len(file_paths)
        percentage = 0

        # create ground truth
        for i, file_path in enumerate(file_paths):

            # keep track of the progress
            if i % (size // 10) == 0:
                print('{}%'.format(percentage))
                percentage += 10

            # get extend from taster
            c0, c3, c2, c1 = self.get_extend(path_dir_in + file_path)

            path_out = path_dir_out + 'tile_ground_truth' + file_path[10:]

            # create string for bash command
            bashCommand = "gdal_rasterize -l " + name_vector + " -a " + name_layer + " -tr " + str(pixel) + " " + str(pixel) + \
            " -a_nodata 0.0 -te " + str(c0) + " " + str(c1) + " " + str(c2) + " " + str(c3) + \
            " -ot Byte -of GTiff " + path_shp + " " + path_out

            # execute bash command
            os.system(bashCommand)
