#!/usr/bin/env python2
import os, os.path, os
import argparse
import sys
import re
import codecs
import logging
from distutils.dir_util import create_tree
import shutil
import subprocess
from ipy_progressbar import ProgressBar


logging.basicConfig(format='%(levelname)s: %(message)s')


# parsing command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('input', help='input directory with TeX files')
parser.add_argument('output', help='output directory, which will contain HTML files')
parser.add_argument('--temp', default='tmp', help='temporary directory')
parser.add_argument('--noeqs', action='store_true', help='do not convert equations to images - much faster')
parser.add_argument('-c', '--cont', action='store_true', help='continue processing (if not given then always start from scratch)')
args = parser.parse_args()


# find files in input directory
files = []
for directory, subdirs, fnames in os.walk(args.input):
    # make paths relative to input directory
    assert directory.startswith(args.input)
    directory = directory[len(args.input):].strip('/')
    fnames = map(lambda name: os.path.join(directory, name), fnames)
    files += fnames

texfiles = [f for f in files if os.path.splitext(f)[1].lower() == '.tex']
if files != texfiles:
    logging.warning('%d files in the input directory have extension different from .tex, ignoring them', len(files) - len(texfiles))
    files = texfiles

if not files:
    logging.error('no TeX files to process - stopping now')
    sys.exit()


# check output directory
if not os.path.isdir(args.output) or (not args.cont and os.listdir(args.output)):
    logging.error('output directory does not exist or is not empty - stopping now')
    sys.exit()

# check temp directory
if not os.path.isdir(args.temp) or (not args.cont and os.listdir(args.temp)):
    logging.error('temporary directory does not exist or is not empty - stopping now')
    sys.exit()


create_tree(args.temp, files, verbose=True)


# preprocess .tex
for fname in ProgressBar(files, title='Preprocess'):
    infname = os.path.join(args.input, fname)
    outfname = os.path.join(args.temp, fname)
    if args.cont and os.path.exists(outfname):
        continue

    with codecs.open(infname, mode='r', encoding='cp1251') as inf, \
         codecs.open(outfname, mode='w', encoding='utf-8') as outf:
        for line in inf:
            line = re.sub(r'(?<!\\)%.*', '', line)
            line = line.rstrip('\r\n')
            if line.strip():
                outf.write(line + '\n')


# convert .tex to .htex (gladtex format)
for fname in ProgressBar(files, title='TeX -> GladTeX'):
    infname = os.path.join(args.temp, fname)
    outfname = os.path.join(args.temp, os.path.splitext(fname)[0] + '.htex')
    if args.cont and os.path.exists(outfname):
        continue

    try:
        subprocess.check_output(['pandoc', infname, '-o', outfname, '-f', 'latex', '-t', 'html5', '--standalone', '--gladtex'], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logging.error('while processing "%s"', infname)
        logging.error(e.output)
        sys.exit()


# convert .htex to html with images
for fname in ProgressBar(files, title='GladTeX -> HTML'):
    infname = os.path.join(args.temp, os.path.splitext(fname)[0] + '.htex')
    outfname = os.path.join(args.temp, os.path.splitext(fname)[0] + '.html')
    outdir = os.path.join(args.temp, os.path.splitext(fname)[0])
    if args.cont and os.path.exists(outdir):
        continue

    if args.noeqs:
        shutil.copyfile(infname, outfname)
    else:
        try:
            subprocess.check_output(['gladtex', '-d', outdir, infname], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logging.error('while processing "%s"', infname)
            logging.error(e.output)
            sys.exit()


if not args.noeqs:
    # convert images to single sprite with css
    dirs = set(map(lambda f: os.path.dirname(f), files))
    for d in ProgressBar(dirs, title='Combine images'):
        d = os.path.join(args.temp, d)
        try:
            subprocess.check_output(['glue', d, d, '--recursive', '--project', '--sprite-namespace='], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logging.error('while processing "%s"', d)
            logging.error(e.output)
            continue


    # post-edit csses
    for fname in ProgressBar(files, title='Postprocess'):
        cssfname = os.path.join(args.temp, os.path.splitext(fname)[0] + '.css')
        if not os.path.exists(cssfname):
            continue
        with open(cssfname, mode='r') as inf:
            content = inf.read()
        content = re.sub('background-image', 'display: inline-block; \nbackground-image', content)
        with codecs.open(cssfname, mode='w') as outf:
            outf.write(content)


create_tree(args.output, files, verbose=True)


# copy from temp to output
for fname in ProgressBar(files, title='Copy to out'):
    base = os.path.splitext(fname)[0]
    fnames = [base + '.html', base + '.css', base + '.png']
    for f in fnames:
        inf = os.path.join(args.temp, f)
        if not os.path.exists(inf):
            continue
        outf = os.path.join(args.output, f)
        shutil.copyfile(inf, outf)
