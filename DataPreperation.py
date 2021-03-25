from osgeo import gdal
import sys
import os
import geopandas
import pandas as pd

class DataPreperation(object):

    def __init__(self, path_dir):
        if path_dir[-1] == '/':
            self.path_out_dir = path_dir
        else:
            self.path_out_dir = path_dir + '/'


    def clip(self, path_in_grid, path_in_raster, path_out_dir, typ='ortho'):
        '''
        clip raster by grid

        input:
            path_in_grid (string) - path to vector (.shp) file containing polygons
            path_in_raster (string) - path to raster (.tif) that needs to be cutted
            path_out_dir (string) -
            typ (string) - name of type (exp. 'ortho', 'dsm', 'dtm', 'slope')
        '''

        # load vector file
        grid = geopandas.read_file(path_in_grid)

        if typ == 'ortho':
            sufix = ''
        else:
            sufix = '_1m'

        # variables for keeping track of the progress
        size = grid.shape[0]
        percentage = 0

        # loop over all the polygons
        for i in range(size):
            # keep track of the progress
            if i % (size // 10) == 0:
                print('{}%'.format(percentage))
                percentage += 10
            # get extend
            extend = grid.loc[i,'geometry'].bounds
            # set paths
            path_raster = path_in_raster
            path_out = "{}/{}{}/tile_dsm_{}.tif".format(path_out_dir, typ, sufix, grid.loc[i,'id'])

            # construct bash command
            bash_command = "gdal_translate -projwin {} {} {} {} -a_nodata 0.0 -of GTiff {} {}".format(extend[0], extend[3], extend[2], extend[1], path_raster, path_out)
            # execute command
            os.system(bash_command)

        print("finished cilpping")


    def get_file_paths(self, path_dir):
        '''
        returns all file paths in the provided directory

        input:
            path_dir (string) - path to directory

        returns:
            ids (list) - list with all file paths in the directory
        '''
        ids = []
        # loop over all files found in directory
        for file in os.listdir(path_dir):
            # add path to lists
            ids.append(path_dir + file)
        return ids


    def align_tiles(self, path_dir, typ):
        '''
        converts the resolution of an tif image into the desired resolution

        input:
            path_dir (string) - path to directory
            typ (string) - type of (exp: 'dsm')

        '''
        path_dir_in = "{}{}_1m/".format(path_dir, typ)
        path_dir_out = "{}{}/".format(path_dir, typ)

        file_paths = self.get_file_paths(path_dir_in)

        size = len(file_paths)
        percentage = 0

        for i, file_path in enumerate(file_paths):

            # keep track of the progress
            if i % (size // 10) == 0:
                print('{}%'.format(percentage))
                percentage += 10

            # if file is raster file
            if file_path[-4:] == '.tif':

                #set file paths
                path_in = file_path
                path_out = '{}tile_{}'.format(path_dir_out, file_path[file_path.rfind(typ):])

                # construct bash command
                bash_command = "gdalwarp -tr 0.2 0.2 -tap " + path_in + " " + path_out
                # execute bash command
                os.system(bash_command)
