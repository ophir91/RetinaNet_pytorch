from __future__ import print_function, division
import sys
import os
import torch
import numpy as np
import random
import csv

from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
from torch.utils.data.sampler import Sampler

#rom pycocotools.coco import COCO

import skimage.io
import skimage.transform
import skimage.color
import skimage

from PIL import Image
from six import raise_from


class CSVDataset(Dataset):
    """CSV dataset."""

    # BB: added argument "feature_class_dir" - The dir with all the csv files

    def __init__(self, train_file, class_list,color_classes,type_classes,feature_class_dir, image_dir, transform=None):
        """
        Args:
            train_file (string): CSV file with training annotations
            annotations (string): CSV file with class list
            test_file (string, optional): CSV file with testing annotations
        """
        self.train_file = train_file
        self.class_list = class_list
        self.transform = transform
        self.type_classes = type_classes
        self.color_classes = color_classes
        self.image_dir = image_dir
        ######## parse general classes
        try:
            with self._open_for_csv(self.class_list) as file:
                self.genral_classes = self.load_classes(csv.reader(file, delimiter=','))
        except ValueError as e:
            raise_from(ValueError('invalid CSV class file: {}: {}'.format(self.class_list, e)), None)

        #######parse type classes
        try:
            with self._open_for_csv(type_classes) as file:
                self.type_classes = self.load_classes(csv.reader(file, delimiter=','))
        except ValueError as e:
            raise_from(ValueError('invalid CSV class file: {}: {}'.format(self.type_classes, e)), None)
        #######parse type classes
        try:
            with self._open_for_csv(self.color_classes) as file:
                 self.color_classes = self.load_classes(csv.reader(file, delimiter=','))
        except ValueError as e:
            raise_from(ValueError('invalid CSV class file: {}: {}'.format(self.type_classes, e)), None)

        ######################## parse Features CSVs ################################

        self.features_classes = {}
        for filename in os.listdir(feature_class_dir):
            name =filename.split(".")[0]
            try:
                 with self._open_for_csv(os.path.join(feature_class_dir,filename)) as file:
                     self.features_classes[name] = self.load_classes(csv.reader(file, delimiter=','))
            except ValueError as e:
                raise_from(ValueError('invalid CSV class file: {}: {}'.format(filename, e)), None)
        ############################################################################

        self.labels = {}
        for key, value in self.genral_classes.items():
            self.labels[value] = key

        ######################## Feature+color+type labels dictionary ################################

        self.labels4features = {}
        for key, value in self.features_classes['ac_vents'].items():
            self.labels4features[value] = key

        self.labels4colors = {}
        for key, value in self.color_classes.items():
            self.labels4colors[value] = key

        self.labels4types = {}
        for key, value in self.type_classes.items():
            self.labels4types[value] = key

        ############################################################################


        # csv with img_path, x1, y1, x2, y2, class_name
        try:
            with self._open_for_csv(self.train_file) as file:
                self.image_data = self._read_annotations(csv.reader(file, delimiter=','),classes=self.genral_classes)
        except ValueError as e:
            raise_from(ValueError('invalid CSV annotations file: {}: {}'.format(self.train_file, e)), None)

        self.image_names = []
        image_list = os.listdir(image_dir)
        for image_id in self.image_data:
            if str(image_id) + '.tiff' in image_list:
                new_line = image_dir + str(image_id) + '.tiff'
            elif str(image_id) + '.jpg' in image_list:
                new_line = image_dir + str(image_id) + '.jpg'
            elif str(image_id) + '.tif' in image_list:
                new_line = image_dir + str(image_id) + '.tif'
            else:
                continue
            self.image_names.append(new_line)

    def _parse(self, value, function, fmt):
        """
        Parse a string into a value, and format a nice ValueError if it fails.
        Returns `function(value)`.
        Any `ValueError` raised is catched and a new `ValueError` is raised
        with message `fmt.format(e)`, where `e` is the caught `ValueError`.
        """
        try:
            return function(value)
        except ValueError as e:
            raise_from(ValueError(fmt.format(e)), None)

    def _open_for_csv(self, path):
        """
        Open a file with flags suitable for csv.reader.
        This is different for python2 it means with mode 'rb',
        for python3 this means 'r' with "universal newlines".
        """
        if sys.version_info[0] < 3:
            return open(path, 'rb')
        else:
            return open(path, 'r', newline='')

    def load_classes(self, csv_reader):
        result = {}

        for line, row in enumerate(csv_reader):
            line += 1

            try:
                class_name, class_id = row
            except ValueError:
                raise_from(ValueError('line {}: format should be \'class_name,class_id\''.format(line)), None)
            class_id = self._parse(class_id, int, 'line {}: malformed class ID: {{}}'.format(line))

            if class_name in result:
                raise ValueError('line {}: duplicate class name: \'{}\''.format(line, class_name))
            result[class_name] = class_id
        return result


    def __len__(self):
        return len(self.image_names)

    def __getitem__(self, idx):

        img = self.load_image(idx)
        annot = self.load_annotations(idx)
        sample = {'img': img, 'annot': annot}
        # print ('transforming image:' + self.image_names[idx])
        if self.transform:
            sample = self.transform(sample)

        return sample

    def load_image(self, image_index):
        img = skimage.io.imread(self.image_names[image_index])

        if len(img.shape) == 2:
            img = skimage.color.gray2rgb(img)

        return img.astype(np.float32)/255.0

    def load_annotations(self, image_index):
        #BB: Changed the entire function
        # get ground truth annotations
        annotation_list = self.image_data[self.image_names[image_index].split('/')[-1].split('.')[0]]
        annotations     = np.zeros((0, 21))

        # some images appear to miss annotations (like image with id 257034)
        if len(annotation_list) == 0:
            return annotations

        # parse annotations
        for idx, annot in enumerate(annotation_list):
            # some annotations have basically no width / height, skip them
            general_class = annot['general_class']
            sub_class = annot['sub_class']
            color = annot['color']
            sunroof = annot['sunroof']
            ac = annot['ac_vents']
            cart = annot['harnessed_to_a_cart']
            soft = annot['soft_shell_box']
            enclosed_box = annot['enclosed_box']
            ladder = annot['ladder']
            flatbed = annot['flatbed']
            wrecked = annot['wrecked']
            wheel = annot['spare_wheel']
            cabin = annot['enclosed_cab']
            cargo = annot['open_cargo_area']
            luggage = annot['luggage_carrier']

            annotation = np.zeros((1,21))

            annotation[0, 4]  = annot['tag_id']
            annotation[0, 0]  = float(annot['x1'])
            annotation[0, 1]  = float(annot['y1'])
            annotation[0, 2]  = float(annot['x2'])
            annotation[0, 3]  = float(annot['y2'])
            annotation[0, 5]  = self.genral_classes[general_class]
            annotation[0, 6]  = self.type_classes[sub_class]
            annotation[0, 7]  = sunroof
            annotation[0, 8]  = luggage
            annotation[0, 9]  = cargo
            annotation[0, 10] = cabin
            annotation[0, 11] = wheel
            annotation[0, 12] = wrecked
            annotation[0, 13] = flatbed
            annotation[0, 14] = ladder
            annotation[0, 15] = enclosed_box
            annotation[0, 16] = soft
            annotation[0, 17] = cart
            annotation[0, 18] = ac
            if (color in ["red", "yellow", "blue", "white", "black", "silver/gray"]):
                annotation[0, 19] = self.color_classes[color]
            else:
                annotation[0, 19] = self.color_classes["other"]

            annotations = np.append(annotations, annotation,axis=0)

        return annotations

    def _read_annotations(self, csv_reader, classes):
        result = {}
        for line, row in enumerate(csv_reader):
            line += 1

            try:

                tag_id, image_id, p1_x, p1_y, p2_x, p2_y, p3_x, p3_y, p4_x, p4_y, general_class, sub_class, sunroof, luggage_carrier, open_cargo_area,\
                enclosed_cab, spare_wheel, wrecked, flatbed, ladder, enclosed_box, soft_shell_box, harnessed_to_a_cart, ac_vents, color = row[:25]

              #  img_file, x1, y1, x2, y2, class_name = row[:6]
            except ValueError:
                raise_from(ValueError('line {}: format should be \'img_file,x1,y1,x2,y2,class_name\' or \'img_file,,,,,\''.format(line)), None)

            if image_id not in result:
                result[image_id] = []

            # If a row contains only an image path, it's an image without annotations.

            #if (x1, y1, x2, y2, class_name) == ('', '', '', '', ''):
            #                continue

            p1_x = self._parse(p1_x, float, 'line {}: malformed x1: {{}}'.format(line))
            p1_y = self._parse(p1_y, float, 'line {}: malformed y1: {{}}'.format(line))
            p2_x = self._parse(p2_x, float, 'line {}: malformed x2: {{}}'.format(line))
            p2_y = self._parse(p2_y, float, 'line {}: malformed y2: {{}}'.format(line))
            p3_x = self._parse(p3_x, float, 'line {}: malformed x1: {{}}'.format(line))
            p3_y = self._parse(p3_y, float, 'line {}: malformed y1: {{}}'.format(line))
            p4_x = self._parse(p4_x, float, 'line {}: malformed x2: {{}}'.format(line))
            p4_y = self._parse(p4_y, float, 'line {}: malformed y2: {{}}'.format(line))

            x1 = min(int(p1_x), int(p2_x), int(p3_x), int(p4_x))
            x2 = max(int(p1_x), int(p2_x), int(p3_x), int(p4_x))
            y1 = min(int(p1_y), int(p2_y), int(p3_y), int(p4_y))
            y2 = max(int(p1_y), int(p2_y), int(p3_y), int(p4_y))

            # x1 = min(int(line[1]['p1_x']), int(line[1]['p2_x']), int(line[1]['p3_x']), int(line[1]['p4_x']))
            # x2 = max(int(line[1]['p1_x']), int(line[1]['p2_x']), int(line[1]['p3_x']), int(line[1]['p4_x']))
            # y1 = min(int(line[1]['p1_y']), int(line[1]['p2_y']), int(line[1]['p3_y']), int(line[1]['p4_y']))
            # y2 = max(int(line[1]['p1_y']), int(line[1]['p2_y']), int(line[1]['p3_y']), int(line[1]['p4_y']))



            result[image_id].append({'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2,'tag_id':tag_id ,
                                     'general_class': general_class,'sub_class':sub_class,'sunroof':sunroof,
                                     'ac_vents':ac_vents,'harnessed_to_a_cart':harnessed_to_a_cart,
                                     'soft_shell_box':soft_shell_box,'enclosed_box':enclosed_box,'ladder':ladder,
                                     'wrecked':wrecked ,'flatbed':flatbed,'spare_wheel':spare_wheel,
                                     'enclosed_cab':enclosed_box,'open_cargo_area' : open_cargo_area,
                                     'luggage_carrier':luggage_carrier, 'color' : color})
        return result

    def name_to_label(self, name):
        return self.genral_classes[name]

    def label_to_name(self, label):
        return self.labels[label]

    def num_classes(self):
        return max(self.genral_classes.values()) + 1

    def image_aspect_ratio(self, image_index):
        image = Image.open(self.image_names[image_index])
        return float(image.width) / float(image.height)


def collater(data):

    imgs = [s['img'] for s in data]
    annots = [s['annot'] for s in data]
    scales = [s['scale'] for s in data]

    widths = [int(s.shape[0]) for s in imgs]
    heights = [int(s.shape[1]) for s in imgs]
    batch_size = len(imgs)

    max_width = np.array(widths).max()
    max_height = np.array(heights).max()

    padded_imgs = torch.zeros(batch_size, max_width, max_height, 3)

    for i in range(batch_size):
        img = imgs[i]
        padded_imgs[i, :int(img.shape[0]), :int(img.shape[1]), :] = img

    max_num_annots = max(annot.shape[0] for annot in annots)

    if max_num_annots > 0:

        annot_padded = torch.ones((len(annots), max_num_annots, 21)) * -1

        if max_num_annots > 0:
            for idx, annot in enumerate(annots):
                #print(annot.shape)
                if annot.shape[0] > 0:
                    annot_padded[idx, :annot.shape[0], :] = annot
    else:
        annot_padded = torch.ones((len(annots), 1, 21)) * -1


    padded_imgs = padded_imgs.permute(0, 3, 1, 2)

    return {'img': padded_imgs, 'annot': annot_padded, 'scale': scales}

class Resizer(object):
    """Convert ndarrays in sample to Tensors."""

    def __call__(self, sample, min_side=608, max_side=1024):
        image, annots = sample['img'], sample['annot']

        rows, cols, cns = image.shape

        smallest_side = min(rows, cols)

        # rescale the image so the smallest side is min_side
        scale = min_side / smallest_side

        # check if the largest side is now greater than max_side, which can happen
        # when images have a large aspect ratio
        largest_side = max(rows, cols)

        if largest_side * scale > max_side:
            scale = max_side / largest_side

        # resize the image with the computed scale
        image = skimage.transform.resize(image, (int(round(rows*scale)), int(round((cols*scale)))))
        rows, cols, cns = image.shape

        pad_w = 32 - rows%32
        pad_h = 32 - cols%32

        new_image = np.zeros((rows + pad_w, cols + pad_h, cns)).astype(np.float32)
        new_image[:rows, :cols, :] = image.astype(np.float32)

        annots[:, :4] *= scale

        return {'img': torch.from_numpy(new_image), 'annot': torch.from_numpy(annots), 'scale': scale}


class Augmenter(object):
    """Convert ndarrays in sample to Tensors."""

    def __call__(self, sample, flip_x=0.5):

        if np.random.rand() < flip_x:
            image, annots = sample['img'], sample['annot']
            image = image[:, ::-1, :]

            rows, cols, channels = image.shape

            x1 = annots[:, 0].copy()
            x2 = annots[:, 2].copy()
            
            x_tmp = x1.copy()

            annots[:, 0] = cols - x2
            annots[:, 2] = cols - x_tmp

            sample = {'img': image, 'annot': annots}

        return sample


class Normalizer(object):

    def __init__(self):
        self.mean = np.array([[[0.485, 0.456, 0.406]]])
        self.std = np.array([[[0.229, 0.224, 0.225]]])

    def __call__(self, sample):

        image, annots = sample['img'], sample['annot']
        if image.shape[2] == 4:
            image = image[:, :, :3]
        return {'img':((image.astype(np.float32)-self.mean)/self.std), 'annot': annots}

class UnNormalizer(object):
    def __init__(self, mean=None, std=None):
        if mean == None:
            self.mean = [0.485, 0.456, 0.406]
        else:
            self.mean = mean
        if std == None:
            self.std = [0.229, 0.224, 0.225]
        else:
            self.std = std

    def __call__(self, tensor):
        """
        Args:
            tensor (Tensor): Tensor image of size (C, H, W) to be normalized.
        Returns:
            Tensor: Normalized image.
        """
        for t, m, s in zip(tensor, self.mean, self.std):
            t.mul_(s).add_(m)
        return tensor


class AspectRatioBasedSampler(Sampler):

    def __init__(self, data_source, batch_size, drop_last):
        self.data_source = data_source
        self.batch_size = batch_size
        self.drop_last = drop_last
        self.groups = self.group_images()

    def __iter__(self):
        random.shuffle(self.groups)
        for group in self.groups:
            yield group

    def __len__(self):
        if self.drop_last:
            return len(self.data_source) // self.batch_size
        else:
            return (len(self.data_source) + self.batch_size - 1) // self.batch_size

    def group_images(self):
        # determine the order of the images
        order = list(range(len(self.data_source)))
        order.sort(key=lambda x: self.data_source.image_aspect_ratio(x))

        # divide into groups, one group = one batch
        return [[order[x % len(order)] for x in range(i, i + self.batch_size)] for i in range(0, len(order), self.batch_size)]
