#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pip install twine

import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command

# Package meta-data.
NAME = 'gamethreads'
DESCRIPTION = 'Post and update reddit gamethreads'
URL = 'https://github.com/redditnfl/gamethreads'
EMAIL = 'rasher@rasher.dk'
AUTHOR = 'Jonas Häggqvist'

# What packages are required for this module to be executed?
REQUIRED = [
    'Jinja2>=2.10.1,<3',
    'beautifulsoup4>=4.6.0,<5',
    'html5lib>=1.1,<1.2',
    'praw>=5.1.0,<6',
    'pytz',
    'python-yr>=1.4.5,<2',
    'PyYAML>=5.1,<6',
    'SQLAlchemy>=1.3.0,<1.4',
    'ujson>=1.35,<2',
    'psycopg2>=2.7.3.1,<3',
    'roman>=3.3,<4',
    'MarkupSafe==2.0.1',
    'nflapi @ git+https://git@github.com/rasher/nflapi@6846df73b0#egg=nflapi',
]

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.rst' is present in your MANIFEST.in file!
with io.open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Load the package's __version__.py module as a dictionary.
about = {}
with open(os.path.join(here, NAME, '__version__.py')) as f:
    exec(f.read(), about)


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPi via Twine…')
        os.system('twine upload dist/*')

        sys.exit()


# Where the magic happens:
setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    # If your package is a single module, use this instead of 'packages':
    # py_modules=['mypackage'],

    entry_points={
        'console_scripts': [
            'gamethreads=gamethreads.gamethreader:main',
            'models=gamethreads.models:main',
            'redzone=gamethreads.plugins.nfl.redzone:main',
            'schedule=gamethreads.plugins.nfl.schedule:main',
            ],
    },
    install_requires=REQUIRED,
    include_package_data=True,
    license='ISC',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Message Boards',
    ],
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
    },
)
