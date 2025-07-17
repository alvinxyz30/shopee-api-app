#!/usr/bin/python3

import sys
import os

# Add your project directory to the sys.path
path = '/home/alvinnovendra2/shopee_api_app'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application

if __name__ == "__main__":
    application.run()