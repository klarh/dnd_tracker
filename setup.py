#!/usr/bin/env python

import os
from setuptools import setup

with open('dnd_tracker/version.py') as version_file:
    exec(version_file.read())

setup(name='dnd-tracker',
      author='Matthew Spellings',
      author_email='matthew.p.spellings@gmail.com',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
      ],
      description='Library to keep track of tabletop games',
      entry_points={},
      extras_require={},
      install_requires=['numpy'],
      license='MIT',
      packages=[
          'dnd_tracker',
      ],
      python_requires='>=3',
      version=__version__
)
