#!/usr/bin/env python3
"""
Featured Files Extractor

This script extracts featured files based on raw/export directory contents:
1. Extract all file names (without extensions) from the 'raw/export' subdirectory
2. Find all files with matching names (case-insensitive) in the target directory 
   and common image subdirectories (heif, hif, jpeg, jpg, etc.)
3. Copy these matching files to a new 'featured' subdirectory

Usage:
    python extract_featured_raw.py [directory_path]
    
    If no directory is provided, the script will prompt for one interactively.
    
Examples:
    python extract_featured_raw.py /path/to/photos
    python extract_featured_raw.py "C:\\Users\\Photos\\Event"
    python extract_featured_raw.py  # Interactive mode
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# Common image format subdirectories to search
# Empty string represents the base directory itself
IMAGE_SUBDIRS = ['', 'heif', 'hif', 'jpeg', 'jpg', 'HEIF', 'HIF', 'JPEG', 'JPG']


def get_target_directory():
    """
    Get the target directory from command line arguments or interactive user input.
    
    Returns:
        Path: The validated target directory path
    """
    parser = argparse.ArgumentParser(
        description='Extract featured files based on raw directory contents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/photos              # Use specific directory
  %(prog)s "C:\\Photos\\Event"           # Windows path with spaces
  %(prog)s                             # Interactive mode
        """
    )
    parser.add_argument(
        'directory', 
        nargs='?', 
        help='Target directory path containing the "raw/export" subdirectory (optional - will prompt if not provided)'
    )
    parser.add_argument(
        '--version', 
        action='version', 
        version='%(prog)s 1.5'
    )
    
    args = parser.parse_args()
    
    if args.directory:
        # Command line argument provided
        target_dir = Path(args.directory).resolve()
        if not target_dir.exists():
            print(f"Error: Directory '{target_dir}' does not exist.")
            sys.exit(1)
        if not target_dir.is_dir():
            print(f"Error: '{target_dir}' is not a directory.")
            sys.exit(1)
        return target_dir
    else:
        # Interactive mode: prompt user for directory
        print("Interactive mode: Please specify the target directory.")
        while True:
            user_input = input("Enter the target directory path (or press Enter for current directory): ").strip().strip('\'"')
            
            if not user_input:
                target_dir = Path.cwd()
                print(f"Using current directory: {target_dir}")
                return target_dir
            else:
                target_dir = Path(user_input).expanduser().resolve()
                if target_dir.exists() and target_dir.is_dir():
                    return target_dir
                else:
                    print(f"Error: '{target_dir}' does not exist or is not a directory.")
                    print("Please try again or press Enter to use current directory.")

def process_files(base_dir):
    """
    Process files in the specified directory.
    
    Args:
        base_dir (Path): The base directory containing 'raw' subdirectory
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    raw_dir = base_dir / "raw"
    featured_dir = base_dir / "featured"
    
    print(f"\n{'='*60}")
    print(f"FEATURED FILES EXTRACTOR")
    print(f"{'='*60}")
    print(f"Working directory: {base_dir}")
    
    # Check if raw directory exists
    if not raw_dir.exists():
        print(f"\nError: 'raw' subdirectory does not exist in '{base_dir}'")
        return False

    print(f"Raw directory: {raw_dir}")
    print(f"Featured directory: {featured_dir}")

    # Step 1: Extract all file names (without extensions) from raw directory and all its subdirectories
    print(f"\n{'Step 1: Scanning raw directory (all subdirectories)':-<50}")
    raw_file_names = set()

    # Collect dirs to scan: raw/ itself + all subdirectories
    dirs_to_scan = [raw_dir]
    try:
        for entry in raw_dir.iterdir():
            if entry.is_dir():
                dirs_to_scan.append(entry)
                print(f"   📂 Found subdirectory: {entry.name}")
    except PermissionError:
        print(f"Error: Permission denied accessing '{raw_dir}'")
        return False

    for scan_dir in dirs_to_scan:
        try:
            for file_path in scan_dir.iterdir():
                if file_path.is_file():
                    file_stem = file_path.stem.lower()
                    if not file_stem.startswith('.'):
                        raw_file_names.add(file_stem)
        except PermissionError:
            print(f"   ⚠️  Permission denied: {scan_dir}")
    
    if not raw_file_names:
        print("   Warning: No valid files found in raw directory.")
        return False
        
    print(f"   📊 Total unique file names: {len(raw_file_names)}")
    
    # Step 2: Find all matching files in target directory and image subdirectories
    print(f"\n{'Step 2: Finding matching files':-<50}")
    print(f"   Searching in: base directory + {[d for d in IMAGE_SUBDIRS if d]}")
    matching_files = []
    searched_dirs = []
    
    for subdir in IMAGE_SUBDIRS:
        if subdir:
            search_dir = base_dir / subdir
        else:
            search_dir = base_dir
        
        # Skip if directory doesn't exist
        if not search_dir.exists() or not search_dir.is_dir():
            continue
        
        # Skip raw and featured directories
        if search_dir.name.lower() in ('raw', 'featured'):
            continue
            
        searched_dirs.append(search_dir)
        
        try:
            for file_path in search_dir.iterdir():
                if file_path.is_file():
                    # Use lowercase for case-insensitive matching
                    file_stem = file_path.stem.lower()
                    # Skip system files
                    if file_stem.startswith('.'):
                        continue
                    if file_stem in raw_file_names:
                        matching_files.append(file_path)
                        # Show relative path for subdirectory files
                        if subdir:
                            print(f"   ✓ Match: {subdir}/{file_path.name}")
                        else:
                            print(f"   ✓ Match: {file_path.name}")
        except PermissionError:
            print(f"   ⚠️  Permission denied: {search_dir}")
            continue
    
    print(f"   📂 Searched directories: {len(searched_dirs)}")
    
    if not matching_files:
        print("   Warning: No matching files found in any searched directory.")
        return False
        
    print(f"   📊 Total matching files: {len(matching_files)}")
    
    # Step 3: Create featured directory and copy files
    print(f"\n{'Step 3: Copying files to featured directory':-<50}")
    
    try:
        # Create featured directory (if it doesn't exist)
        featured_dir.mkdir(exist_ok=True)
        print(f"   📁 Directory ready: {featured_dir}")
        
        # Copy files
        copied_count = 0
        failed_count = 0
        skipped_count = 0
        
        for file_path in matching_files:
            try:
                destination = featured_dir / file_path.name
                # Check for duplicate filenames from different directories
                if destination.exists():
                    print(f"   ⏭️  Skipped (already exists): {file_path.name}")
                    skipped_count += 1
                    continue
                shutil.copy2(file_path, destination)
                # Show source directory for clarity
                rel_path = file_path.relative_to(base_dir) if file_path.is_relative_to(base_dir) else file_path.name
                print(f"   ✓ Copied: {rel_path}")
                copied_count += 1
            except Exception as e:
                print(f"   ✗ Failed: {file_path.name} - {e}")
                failed_count += 1
        
        # Summary
        print(f"\n{'SUMMARY':-<50}")
        print(f"   ✅ Successfully copied: {copied_count} files")
        if skipped_count > 0:
            print(f"   ⏭️  Skipped (duplicates): {skipped_count} files")
        if failed_count > 0:
            print(f"   ❌ Failed to copy: {failed_count} files")
        print(f"   📂 Destination: {featured_dir}")
        
        return copied_count > 0
        
    except Exception as e:
        print(f"Error creating featured directory: {e}")
        return False


def main():
    """Main function to orchestrate the file extraction process."""
    try:
        # Get target directory from user input or command line
        base_dir = get_target_directory()
        
        # Process files
        success = process_files(base_dir)
        
        if success:
            print(f"\n🎉 Operation completed successfully!")
        else:
            print(f"\n⚠️  Operation completed with issues.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()