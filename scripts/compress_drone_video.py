import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import compress_drone_video, traverse

dir = input("📁 Enter directory path: ").strip().strip("'").strip('"')

# Check if directory exists
if not os.path.exists(dir):
    print(f"❌ Error: Directory not found: {dir}")
    print("Please check the path and try again.")
    sys.exit(1)

if not os.path.isdir(dir):
    print(f"❌ Error: Path is not a directory: {dir}")
    sys.exit(1)

# Compress drone videos to 1080p @ 15Mbps (keeps original fps)
# Compressed files are saved to 'compressed/' subdirectory
# Original files remain untouched in their original location
try:
    traverse(dir, ".mp4", compress_drone_video, "1920:1080", "15M", None)
    print("\n✅ Processing completed!")
except KeyboardInterrupt:
    print("\n⚠️  Processing interrupted by user.")
except Exception as e:
    print(f"\n❌ An error occurred: {e}")
    print("Some files may have been processed successfully.")