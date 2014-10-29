# Topic Model Visualization

## Dependencies

* Python
* Pandoc for TeX to HTML conversion: http://johnmacfarlane.net/pandoc/installing.html
* Packages (can be installed with `pip install <name>`):
    * General numeric data processing: numpy, scipy, h5py
    * My ARTM implementation: py_artm
    * Web interface: Flask, Flask-Classy, Flask-Assets, python-slugify
    * Web interface debugging (currently they are required for normal use too): Flask-DebugToolbar, Flask-DebugToolbar-LineProfilerPanel
    * Search: whoosh
    * Other: ipy-progressbar, pymorphy2, recordtype

## Components

### Collection preprocessing

All the scripts described in this section are located in `collection-processing` directory. They are written in Python and most probably have to be slightly changed to process other collections (currently only MMRO IOI collection has been confirmed to work). Command-line arguments for a script are shown when called with `-h` argument.

The source collection is assumed to consist of TeX or HTML documents. TeX collections have to be converted to HTML with `tex_to_html.py`. By default it converts all mathematical formulae to images, but as this stage is very time-consuming it can be disabled (see the script options).

The next stage of preprocessing is lemmatization, morphological normalization and building the N_wd matrix. It is done with `process.py` script with `--nwd-only` option. The matrix will be saved to the specified HDF5 file in two formats: dense as `n_wd` and sparse (in coordinate format) as `n_wd_coo`.

After the N_wd matrix is built, a topic model should be fit to get P_wt and P_td matrices. For an very simplistic example of doing this with my `py-artm` package, see or call `fit_model.py`. However, a topic model can be fit using any instrument or tool you like, the only requirement is to save `p_wt` and `p_td` float matrices to the same HDF5 file.

After fitting a topic model, the remaining probabilities and quantities are to be computed. For this call the `process.py` script again, but without `--nwd-only` option this time.

Now the only thing that is left is the search indices. They are build with `build_index.py` script in one pass.

For other components only the HTML collection folder, output HDF5 file and search index directory are required.

### Web interface

The web interface is located in the `web` directory and should require less changes (if any) to word with other collections.

Assuming that collection preprocessing is done, copy/move or symlink the outputs into the following places:

* HTML collection folder to `web/static/docsdata`
* HDF5 data file to `data.hdf`
* search index folder to `whoosh_ix`

Having done this, run `web/app.py` script, which starts the web server at `http://localhost:5000` by default. This url will have the fully working visualization now.


### Tests

Currently the tests are located in a single file: `tests.py`. They check mostly the data consistency after the preprocessing.
