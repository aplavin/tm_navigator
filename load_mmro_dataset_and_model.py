#!/usr/bin/env python3

import os

os.system('./db_manage.py add_dataset')
os.system('./db_manage.py load_dataset --dataset-id 1 --title "Simplest MMRO dataset" -dir data_mmro')
os.system('./db_manage.py add_topicmodel --dataset-id 1')
os.system('./db_manage.py load_topicmodel --topicmodel-id 1 --title "Simplest model" -dir data_mmro')
