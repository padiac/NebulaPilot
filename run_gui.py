
import sys
import os

# Add 'src' to sys.path so we can import 'nebulapilot' package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nebulapilot.app_gui import main

if __name__ == "__main__":
    main()
