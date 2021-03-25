import numpy as np
import pandas as pd
import h5py

from osgeo import gdal
from osgeo import gdal_array
from osgeo import osr
from osgeo import gdalconst

from glob import glob
import logging
import os

class DatasetCreation(object):

    def __init__(self, path_dir):
        if path_dir[-1] == '/':
            self.path_dir = path_dir
        else:
            self.path_dir = path_dir + '/'




    def x(self, paths, start, end, data_dtypes):

        # extract data types
        data_types = list(data_dtypes.keys())

        ## read data and convert to numpy array
        arr_512 = {}
        for data_type in data_types:
            # create numpy arrays
            arr_512[data_type] = self.read_array( \
                file_paths=paths[data_type][start:end], \
                size=512, \
                dtype=data_dtypes[data_type])

        ## create and apply mask of ground truth
        if 'ground_truth' in data_types:
            # create mask
            mask = np.ma.make_mask(arr_512['ground_truth'])
            # apply mask
            for data_type in data_types:
                if data_type != 'ground_truth':
                    arr_512[data_type] *= mask

        ## set values under and over threshhold to 0
        if 'dsm' in data_types:
            arr_512['dsm'][arr_512['dsm'] < 0] = 0
            arr_512['dsm'][arr_512['dsm'] > 47] = 0

        ## create 256 pixel tiles
        arr_256 = {}
        for data_type in data_types:
            arr_256[data_type] = np.concatenate( \
                [arr_512[data_type][:, :256, :256], \
                arr_512[data_type][:, 256:, :256], \
                arr_512[data_type][:, :256, 256:], \
                arr_512[data_type][:, 256:, 256:]], axis=0)

        # free memory
        del arr_512

        ## delete tiles that are < 0.5 empty
        key = data_types[0]
        limit_gt = arr_256[key].shape[1] ** 2 / 2
        limit_ortho = limit_gt * 4

        idx_delete = []
        for i in range(0,arr_256[key].shape[0]):
            flag = False
            for data_type in data_types:
                if np.count_nonzero(arr_256[data_type][i]==0) > limit_ortho:
                    flag = True
            if flag:
                idx_delete.append(i)


        # delete images with just zeros
        for data_type in data_types:
            arr_256[data_type] = np.delete(arr_256[data_type], idx_delete, axis=0)

        return(arr_256)


    def find_files(self, dir_img, data_types):
        """
        find paths for provided data types
        inputs:
            dir_img (str) : directory path
            data_types (list) : list of data types to be included (exp: ['ortho', 'ground_truth'])
        return:
            paths (dictionary) : dictionary containing file paths for each of the data types
        """

        idxs = []
        # loop over all files found in directory and retrive indices
        for file in os.listdir("{}{}/".format(dir_img, data_types[0])):
            if file[-4:] == ".tif":
                idxs.append(file[file.rfind('_'):])

        paths = {}
        for data_type in data_types:
            paths[data_type] = []

        for idx in idxs:

            # check if index in all data types
            check_path = []
            for data_type in data_types:
                p = "{}{}/tile_{}{}".format(dir_img, data_type, data_type, idx)
                if os.path.isfile(p):
                    check_path.append(p)

            if len(check_path) == len(data_types):
                for i, data_type in enumerate(data_types):
                    paths[data_type].append(check_path[i])

        return paths


    def tif2array(self, file_path, dtype=np.uint8):
        """
        read GeoTiff and convert to numpy.ndarray.
        inputs:
            file_path (str) : file path of the input GeoTiff file
        return:
            image(np.array) : image for each bands
            dataset : for gdal's data drive
        """
        dataset = gdal.Open(file_path, gdal.GA_ReadOnly)

        if dataset is None:
            return None

        # Allocate our array using the first band's datatype
        image_datatype = dataset.GetRasterBand(1).DataType
        image = np.zeros((dataset.RasterYSize, dataset.RasterXSize, dataset.RasterCount),
                         dtype=dtype)

        # Loop over all bands in dataset
        for b in range(dataset.RasterCount):
            # Remember, GDAL index is on 1, but Python is on 0 -- so we add 1 for our GDAL calls
            band = dataset.GetRasterBand(b + 1)
            # Read in the band's data into the third dimension of our array
            image[:, :, b] = band.ReadAsArray()#buf_type=gdalconst.GDT_Byte)

        #image = image[2:-2,2:-2,:]

        return image


    def cut_img(self, img, x, y):
        """
        cut input numpy array to the width(x) and height(y)
        inputs:
            img (np.array) : image as numpy array
            x (int) : target width
            y (int) : target height
        return:
            img (np.array) : image cutted to the target width(x) and height(y)
        """
        # set pixel sizes
        x_i, y_i, z_i = img.shape
        # dict to store the sliceing information
        d = {}

        for var, var_i, key in [(x, x_i, 'x'), (y, y_i, 'y')]:
            # if image pixel size is grater than the target pixel size
            if (var_i > var):
                # if even cut same amount of pixels from both sides
                if var_i%2 == 0:
                    sub = int(var_i/2 - var/2)
                    d[key+'0'] = sub
                    d[key+'1'] = sub
                # if odd cut 1 pixel more from right/bottom
                else:
                    sub = int(var_i/2 - var/2)
                    d[key+'0'] = sub
                    d[key+'1'] = sub + 1
            else:
                print('image too small')
        # cut image
        img = img[d['x0']:-d['x1'],d['y0']:-d['y1']]

        return img


    def read_array(self, file_paths, size, dtype=np.uint8):
        """
        creates numpy array with all images stacked
        inputs:
            file_paths (list) : list of paths to image files
            size (int) : target pixel resolution (exp: 512)
            dtype (dtype) : dtype for storing the loaded image
        return:
            data (np.array) : numpy array containing all the images stacked
        """
        imgs = []

        # add all
        for file_path in file_paths:
            # load image to numpy array
            img = self.tif2array(file_path, dtype)
            # cut into right shape
            img = self.cut_img(img, size, size)
            # append array to list
            imgs.append(img)

        # convert list with arrays to numpy array
        data = np.stack(imgs, axis=0)
        print(data.shape)
        if dtype != np.uint8:
             data[data < 0] = np.nan
             data = np.nan_to_num(data)

        return data
