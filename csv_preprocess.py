import pandas as pd
import csv
import os


def create_net_format(path, new_path,image_path):
    csv_data = pd.read_csv(path)
    image_dir = os.listdir(image_path)
    class_list = []
    class_list_path = '/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/class_list.csv'
    class_num = 0
    with open(new_path,'w') as f:
        for i,line in enumerate(csv_data.iterrows()):
            minx = min(int(line[1]['p1_x']), int(line[1]['p2_x']), int(line[1]['p3_x']), int(line[1]['p4_x']))
            maxx = max(int(line[1]['p1_x']), int(line[1]['p2_x']), int(line[1]['p3_x']), int(line[1]['p4_x']))
            miny = min(int(line[1]['p1_y']), int(line[1]['p2_y']), int(line[1]['p3_y']), int(line[1]['p4_y']))
            maxy = max(int(line[1]['p1_y']), int(line[1]['p2_y']), int(line[1]['p3_y']), int(line[1]['p4_y']))
            class_name = line[1]['general_class'] + ' ' + line[1]['sub_class'] + ' ' + line[1]['color']
            if str(line[1]['image_id']) + '.tiff' in image_dir:
                new_line = ['/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/training imagery/' + str(line[1]['image_id']) + '.tiff', minx, miny, maxx, maxy, class_name]
            elif str(line[1]['image_id']) + '.jpg' in image_dir:
                new_line = ['/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/training imagery/' + str(line[1]['image_id']) + '.jpg', minx, miny, maxx, maxy, class_name]
            elif str(line[1]['image_id']) + '.tif' in image_dir:
                new_line = ['/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/training imagery/' + str(line[1]['image_id']) + '.tif', minx, miny, maxx, maxy, class_name]
            else:
                continue


            if class_name not in class_list:
                class_list.append(class_name)
                with open(class_list_path, 'a') as c:
                    new_class = [str(class_name), str(class_num)]
                    writer = csv.writer(c)
                    writer.writerow(new_class)
                    class_num = class_num + 1

            writer = csv.writer(f)
            writer.writerow(new_line)
            print('add ' + str(line[1]['tag_id']) + ' to train_new.csv')


create_net_format('/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/train.csv',
                      '/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/train_new.csv',
                  '/media/ophir/DATA1/Ophir/MAFAT/Dataset for participants V2/training imagery')