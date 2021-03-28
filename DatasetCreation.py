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

        # set standard data_dic
        self.data_dic = {'ortho':{'dtype':np.uint8, 'dim':4}, \
                          'dsm':{'dtype':np.float16, 'dim':1}, \
                          'dtm':{'dtype':np.float16, 'dim':1}, \
                          'slope':{'dtype':np.float16, 'dim':1}, \
                          'ground_truth':{'dtype':np.uint8, 'dim':1}}

        self.data_types = ['ortho', 'dsm', 'dtm', 'slope', 'ground_truth']


    def set_input_dir(self, path_dir):
        if path_dir[-1] == '/':
            self.path_dir = path_dir
        else:
            self.path_dir = path_dir + '/'


    def set_data_types(self, data_dic):
        self.data_dic = data_dic
        self.data_types = list(data_dic.keys())


    def create_hdf5(self, path_file, tile_size, dataset_size):
        self.path_hdf5 = path_file
        # cerate file
        hdf5_ds = h5py.File(path_file, 'a')
        # create dataset
        for data_type in self.data_types:
            x = hdf5_ds.create_dataset(data_type, \
            (dataset_size, tile_size, tile_size, self.data_dic[data_type]['dim']), \
            dtype=self.data_dic[data_type]['dtype'])
        hdf5_ds.close()


    def set_hdf5(self, path_file):
        #TODO: check if file exist
        self.path_hdf5 = path_file


    def add_dataset_to_hdf5(self, block_size, start_index=0):
        # open hdf5 file
        hdf5_ds = h5py.File(self.path_hdf5, 'a')
        # find paths
        paths = self.find_files(self.path_dir, self.data_types)

        ds_size = len(paths[list(paths.keys())[0]])

        # TODO add else
        # refracture code no dublicate
        if ds_size > block_size:
            counter = start_index
            for i in range(ds_size // block_size):

                print(block_size*i, block_size*(i+1))

                data = self.prepare_dataset(paths, block_size*i, block_size*(i+1), self.data_dic)

                for data_type in self.data_types:
                    # set dataset
                    x = hdf5_ds[data_type]
                    # assign data
                    x[counter:counter+data[data_type].shape[0],:,:,:] = data[data_type]
                # update counter
                counter += data[data_type].shape[0]
                print(counter)

            print(block_size*(i+1), block_size*(i+1) + ds_size % block_size)
            data = self.prepare_dataset(paths, block_size*(i+1), ds_size, self.data_dic)

            for data_type in self.data_types:
                # set dataset
                x = hdf5_ds[data_type]
                # assign data
                x[counter:counter+data[data_type].shape[0],:,:,:] = data[data_type]

            counter += data[data_type].shape[0]
            print(counter)


        hdf5_ds.close()
        print('finished')


    def prepare_dataset(self, paths, start, end, data_dtypes):

        # extract data types
        data_types = self.data_types

        ## read data and convert to numpy array
        arr_512 = {}
        for data_type in data_types:
            # create numpy arrays
            arr_512[data_type] = self.read_array( \
                file_paths=paths[data_type][start:end], \
                size=512, \
                dtype=data_dtypes[data_type]['dtype'])

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


class DatasetStats(object):

    def __init__(self, path_dir):
        if path_dir[-1] == '/':
            self.path_dir = path_dir
        else:
            self.path_dir = path_dir + '/'


    def calc_mean(self, dset, data_type, start_index, end_index, block_size=10000, bands=1):

        mean_bands = list()
        for band in range(bands):

            ds_size = end_index - start_index

            means = []

            counter = start_index
            for i in range(ds_size // block_size):
                # calc start and end index
                start = counter + block_size*i
                end = counter + block_size*(i+1)
                # append the mean
                means.append(np.moveaxis(dset[data_type][start:end], 3, 0)[band].mean())
            # calc start index, end index and rest
            rest = ds_size % block_size
            start = counter + block_size*(i+1)
            end = end_index
            # append the mean multiplied with the percentage (rest/block_size)
            means.append(np.moveaxis(dset[data_type][start:end], 3, 0)[band].mean() * (rest/block_size))
            # calc the mean
            mean_bands.append(sum(means) / (len(means)-1+(rest/block_size)))

        return mean_bands


    def calc_std(self, mean, dset, data_type, start, end, block_size=10000, bands=1, scaler=1):

        #ds_size = end_index - start_index
        if bands > 1:

            std_bands = list()
            for band in range(bands):
                print('Band: {}'.format(band))
                # sum squared difference
                sum_sqr = list()
                for i in range(end//block_size):
                    sum_sqr.append(((np.moveaxis(dset[data_type][start+(i)*block_size:start+(i+1)*block_size], 3, 0)[band]/scaler - (mean[band]/scaler))**2).sum())
                sum_sqr.append(((np.moveaxis(dset[data_type][start+(i+1)*block_size:end], 3, 0)[band]/scaler - (mean[band]/scaler))**2).sum())

                # count records
                sum_n = list()
                for i in range(end//block_size):
                    sum_n.append(np.moveaxis(dset[data_type][start+(i)*block_size:start+(i+1)*block_size], 3, 0)[band].size)
                sum_n.append(np.moveaxis(dset[data_type][start+(i+1)*block_size:end], 3, 0)[band].size)

                std_bands.append((sum(sum_sqr)/sum(sum_n))**(1/2)*scaler)

            return std_bands

        else:
            band = bands-1
            # sum squared difference
            sum_sqr = list()
            for i in range((end-start)//block_size):
                sum_sqr.append(((dset[data_type][start+(i)*block_size:start+(i+1)*block_size]/scaler - (mean[band]/scaler))**2).astype(np.float64).sum())
            sum_sqr.append(((dset[data_type][start+(i+1)*block_size:end]/scaler - (mean[band]/scaler))**2).astype(np.float64).sum())

            # count records
            sum_n = list()
            for i in range((end-start)//block_size):
                sum_n.append((dset[data_type][start+(i)*block_size:start+(i+1)*block_size]).size)
            sum_n.append((dset[data_type][start+(i+1)*block_size:end]).size)

            return [(sum(sum_sqr)/sum(sum_n))**(1/2)*scaler]
