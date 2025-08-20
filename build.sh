#!/bin/bash

# Upgrade pip first
python -m pip install --upgrade pip

# Install setuptools and wheel first
pip install setuptools==68.2.2 wheel==0.41.2

# Install numpy and pandas first (core dependencies)
pip install numpy==1.23.5 pandas==1.5.3

# Install the rest of the packages
pip install -r requirements.txt
