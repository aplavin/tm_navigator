from setuptools import setup, find_packages

setup(
    name='tm_navigator',
    version='1.0',
    packages=find_packages(),
    install_requires=[
        'flask',
        'watchdog',
        'flask-sqlalchemy',
        'flask-mako',
        'flask-debugtoolbar',
        'flask-debugtoolbar-lineprofilerpanel',
        'pygments',
        'flask',
        'sqlalchemy',
        'sqlalchemy-searchable',
        'inflection',
        'psycopg2',
        'webassets',
        'flask-assets',
        'cssmin',
        'cached-property',
    ],
    url='',
    license='MIT',
    author='Alexander Plavin',
    author_email='alexander@plav.in',
    description='',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Visualization',
    ]
)
