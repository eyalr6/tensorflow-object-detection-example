#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import base64
import io
import os
import pathlib
import sys
import tempfile
import argparse
import json
import re

parser = argparse.ArgumentParser(description='Deploy control element detection app.')
parser.add_argument("-m", "--model-path", default='my_model', help="Path to model directory.")
parser.add_argument("-l", "--label-path", default='label_map.pbtxt', help="Path to label map file.")
parser.add_argument("-t", "--threshold", default=0.5, type=float, help="Object detection threshold")
BASE_DIR="/opt/object_detection"
args = parser.parse_args()
THRESHOLD=args.threshold
if THRESHOLD > 1 or THRESHOLD < 0:
  raise Exception("Threshold value must be between 0.0 and 1.0")
print(f"Model path is {args.model_path}")
print(f"Label map path is {args.label_path}")
print(f"Control element detection threshold: {THRESHOLD}")
MODEL_BASE = '/opt/models/research'
sys.path.append(MODEL_BASE)
sys.path.append(MODEL_BASE + '/object_detection')
sys.path.append(MODEL_BASE + '/slim')
PATH_TO_LABELS = f"{BASE_DIR}/{args.label_path}"
PATH_TO_DETAILS_FILE = f"{BASE_DIR}/category_description.json"

if not os.path.isfile(PATH_TO_LABELS):
  raise Exception(f"No label map found in {PATH_TO_LABELS}")

from decorator import requires_auth
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_wtf.file import FileField
import numpy as np
from PIL import Image
from PIL import ImageDraw
import tensorflow as tf
from utils import label_map_util
from werkzeug.datastructures import CombinedMultiDict, FileStorage
from wtforms import Form
from wtforms import ValidationError
from category import Category

with open(f"{BASE_DIR}/category_description.json", 'r') as details:
  category_description = json.load(details)

# Patch the location of gfile
tf.gfile = tf.io.gfile


app = Flask(__name__, static_url_path='/static')
    



@app.before_request
@requires_auth
def before_request():
  pass



content_types = {'jpg': 'image/jpeg',
                 'jpeg': 'image/jpeg',
                 'png': 'image/png'}
extensions = sorted(content_types.keys())


def is_image():
  def _is_image(form, field):
    if not field.data:
      raise ValidationError()
    elif field.data.filename.split('.')[-1].lower() not in extensions:
      raise ValidationError()

  return _is_image


class PhotoForm(Form):
  input_photo = FileField(
      'File extension should be: %s (case-insensitive)' % ', '.join(extensions),
      validators=[is_image()])


class ObjectDetector(object):
  

  def __init__(self):

    label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
    categories = label_map_util.convert_label_map_to_categories(
        label_map, max_num_classes=90, use_display_name=True)
    self.category_index = label_map_util.create_category_index(categories)

    model_dir = f"{BASE_DIR}/{args.model_path}/saved_model"

    if not os.path.isdir(model_dir):
      raise Exception(f"Model dir {model_dir} does not exist or cannot be found.")
    model = tf.saved_model.load(model_dir)
    self.model = model

  def _load_image_into_numpy_array(self, image):
    (im_width, im_height) = image.size
    return np.array(image.getdata()).reshape(
        (im_height, im_width, 3)).astype(np.uint8)

  def detect(self, image):
    image_np = self._load_image_into_numpy_array(image)
    input_tensor = tf.convert_to_tensor(image_np)
    input_tensor = input_tensor[tf.newaxis,...]
    output_dict = self.model(input_tensor)
    num_detections = int(output_dict.pop('num_detections'))
    output_dict = {key:value[0, :num_detections].numpy() 
                   for key,value in output_dict.items()}
    boxes = output_dict['detection_boxes']
    classes = output_dict['detection_classes'].astype(np.int64)
    scores = output_dict['detection_scores']
    return boxes, scores, classes, num_detections


def find_detections_from_xml(image_name):
  object_counter = 0
  pat = '<object>'
  xml_dir = f"{BASE_DIR}/annotations"
  xml_file = image_name.split('.')[0]+'.xml'
  xml_path = f"{xml_dir}/{xml_file}"
  if os.path.isfile(xml_path):
    with open(xml_path, 'r') as label_file:
      for line in label_file:
        if pat in line:
          object_counter += 1
    return object_counter
  else:
    return False


def draw_bounding_box_on_image(image, box, color='red', thickness=4):
  draw = ImageDraw.Draw(image)
  im_width, im_height = image.size
  ymin, xmin, ymax, xmax = box
  (left, right, top, bottom) = (xmin * im_width, xmax * im_width,
                                ymin * im_height, ymax * im_height)
  draw.line([(left, top), (left, bottom), (right, bottom),
             (right, top), (left, top)], width=thickness, fill=color)


def encode_image(image):
  image_buffer = io.BytesIO()
  image.save(image_buffer, format='PNG')
  imgstr = 'data:image/png;base64,{:s}'.format(
      base64.b64encode(image_buffer.getvalue()).decode().replace("'", ""))
  return imgstr


def detect_objects(image_path):
  image = Image.open(image_path).convert('RGB')
  boxes, scores, classes, num_detections = client.detect(image)
  global NUMOFDETECTIONS
  
  image.thumbnail((640, 640), Image.ANTIALIAS)
  new_images = {}
  counter=0
  for i in range(num_detections):
    if scores[i] < args.threshold : continue
    cls = classes[i]
    counter+=1
    if cls not in new_images.keys():
      new_images[cls] = image.copy()
    draw_bounding_box_on_image(new_images[cls], boxes[i],
                               thickness=int(scores[i]*10)-4)
    
  NUMOFDETECTIONS=counter
  results = []
  original_category = Category('original', encode_image(image.copy()))
  results.append(original_category)

  for cls, new_image in new_images.items():
    name = client.category_index[cls]['name']
    new_category = Category(name, encode_image(new_image))
    new_category.description = category_description.get(name)
    results.append(new_category)
  
  return results


@app.route('/')
def upload():
  photo_form = PhotoForm(request.form)
  return render_template('upload.html', photo_form=photo_form, result={})


@app.route('/post', methods=['GET', 'POST'])
def post():
  form = PhotoForm(CombinedMultiDict((request.files, request.form)))
  if request.method == 'POST' and form.validate():
    with tempfile.NamedTemporaryFile() as temp:
      form.input_photo.data.save(temp)
      temp.flush()
      result = detect_objects(temp.name)
    original_file = request.files.get('input_photo').filename
    num_objects = find_detections_from_xml(original_file)
    print(f"num_objects: {num_objects}")
    global NUMOFDETECTIONS
    num_detections=NUMOFDETECTIONS
    NUMOFDETECTIONS=0

    
    photo_form = PhotoForm(request.form)
    return render_template('upload.html',
                           photo_form=photo_form, result=result,num_objects=num_objects,num_detections=num_detections)
  else:
    return redirect(url_for('upload'))

@app.route('/trsvalue', methods=['GET','POST'])
def trsvalue():
  if request.method == 'POST':
    x=request.form['tt']
    if x!='':
      args.threshold=float(x)
    #print(args)

  return redirect(url_for('upload'))



client = ObjectDetector()
NUMOFDETECTIONS=0

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=80, debug=False)
