import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import traverse, compress_image

dir = input("📁 Enter directory path: ").strip().strip("'").strip('"')

# Convert PNG to JPG, keeping original resolution
traverse(dir, ".png", compress_image, "iw:ih", "jpg")