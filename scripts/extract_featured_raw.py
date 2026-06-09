#!/usr/bin/env python3
"""
Featured Files Extractor

This script extracts featured files based on raw directory contents:
1. Extract RAW file names (without extensions) recursively from the 'raw' subdirectory
2. Find original HIF previews with matching names in hif/ directories
3. Copy these matching HIF files to a new 'featured' subdirectory

Supports recursive mode (-r) to process every subdirectory tree that contains its own 'raw' folder.

Usage:
    python extract_featured_raw.py [directory_path] [--recursive | -r]
    
    If no directory is provided, the script will prompt for one interactively.
    With --recursive, it will find and process every subdirectory containing a "raw" folder.
    
Examples:
    python extract_featured_raw.py /path/to/photos
    python extract_featured_raw.py "C:\\Users\\Photos\\Event"
    python extract_featured_raw.py  # Interactive mode
    python extract_featured_raw.py /path/to/event_root --recursive
    python extract_featured_raw.py -r  # Interactive + recursive over subdirs
"""

import argparse
import os
import shlex
import shutil
import sys
from pathlib import Path

RAW_EXTS = {".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2", ".dng"}
FEATURED_EXTS = {".hif"}


def _normalize_directory_input(raw_input: str) -> Path:
    """
    Normalize a user-provided directory string.

    Handles:
    - Surrounding quotes (single or double)
    - Shell-style backslash escapes (e.g. paths copied from terminal prompts
      or history that contain "\ " for spaces, "\~" etc.)
    - Tilde expansion (~)

    This is especially useful in interactive mode where users often paste
    escaped paths directly.
    """
    s = raw_input.strip()

    # First remove one layer of surrounding quotes if present (users sometimes paste
    # ".... " or '....' into the prompt, especially when copying from other tools).
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1]

    # If the (now unquoted) string still contains backslashes, interpret it as a
    # shell-escaped path (the common case when pasting from zsh/bash prompts,
    # command history, or "ls" output that shows escapes).
    if '\\' in s:
        try:
            parts = shlex.split(s)
            if parts:
                s = parts[0]
        except ValueError:
            # Malformed; keep what we have after quote stripping
            pass

    return Path(s).expanduser().resolve()


def _get_image_search_directories(base_dir: Path) -> list[Path]:
    """
    Return the directories to search for candidate featured files.

    - Includes root-level `hif/`.
    - Includes grouped preview directories such as `portrait/<n>/hif/` and
      `panorama/<n>/hif/`.
    - Does not search Export folders. Featured files are original HIF previews.

    On case-insensitive filesystems (macOS, Windows), this deduplicates paths.
    The real on-disk directory name/casing is preserved for display.

    This avoids duplicate "Match" lines and spurious "Skipped (already exists)"
    messages when the only reason for duplicates is case variants of the folder name.
    """
    search_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_dir(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        real = path.resolve()
        if real not in seen:
            seen.add(real)
            search_dirs.append(path)

    add_dir(base_dir / "hif")
    for group_root in (base_dir / "portrait", base_dir / "panorama"):
        if not group_root.exists():
            continue
        try:
            for child in group_root.iterdir():
                if child.is_dir():
                    add_dir(child / "hif")
        except PermissionError:
            pass

    return search_dirs


def _display_search_dir(base_dir: Path, search_dir: Path) -> str:
    try:
        return str(search_dir.relative_to(base_dir))
    except ValueError:
        return search_dir.name


def _scan_raw_stems(raw_dir: Path) -> set[str]:
    raw_file_names: set[str] = set()
    for file_path in raw_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.stem.startswith("."):
            continue
        if file_path.suffix.lower() in RAW_EXTS:
            raw_file_names.add(file_path.stem.lower())
    return raw_file_names


def get_target_directory():
    """
    Get the target directory from command line arguments or interactive user input.
    
    Returns:
        tuple[Path, bool]: The validated target directory path and whether recursive mode is enabled
    """
    parser = argparse.ArgumentParser(
        description='Extract featured files based on raw directory contents (supports recursive processing of multiple event dirs)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/photos              # Use specific directory
  %(prog)s "C:\\Photos\\Event"           # Windows path with spaces
  %(prog)s                             # Interactive mode
  %(prog)s /path/to/root -r             # Recursive: process all subdirs with raw/
  %(prog)s -r                           # Interactive + recursive
        """
    )
    parser.add_argument(
        'directory', 
        nargs='?', 
        help='Target directory path. In recursive mode, finds all subdirs under it containing "raw" (optional - will prompt if not provided)'
    )
    parser.add_argument(
        '--version', 
        action='version', 
        version='%(prog)s 1.6'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively find and process all subdirectories (including the target) that contain a "raw" subdirectory'
    )
    
    args = parser.parse_args()
    
    if args.directory:
        # Command line argument provided
        target_dir = _normalize_directory_input(args.directory)
        if not target_dir.exists():
            print(f"Error: Directory '{target_dir}' does not exist.")
            sys.exit(1)
        if not target_dir.is_dir():
            print(f"Error: '{target_dir}' is not a directory.")
            sys.exit(1)
        return target_dir, args.recursive
    else:
        # Interactive mode: prompt user for directory
        print("Interactive mode: Please specify the target directory.")
        print("  (Tip: you can paste paths copied from your terminal, including ones shown with \\ escapes for spaces.)")
        while True:
            raw_input = input("Enter the target directory path (or press Enter for current directory): ")
            user_input = raw_input.strip()
            
            if not user_input:
                target_dir = Path.cwd()
                print(f"Using current directory: {target_dir}")
                return target_dir, args.recursive
            else:
                target_dir = _normalize_directory_input(raw_input)
                if target_dir.exists() and target_dir.is_dir():
                    return target_dir, args.recursive
                else:
                    print(f"Error: '{target_dir}' does not exist or is not a directory.")
                    print("Please try again or press Enter to use current directory.")


def find_directories_with_raw(root: Path) -> list[Path]:
    """
    Recursively find all directories under root (including root itself) that
    directly contain a 'raw' subdirectory. Prunes traversal into raw/ and
    featured/ to avoid spurious matches.
    
    Args:
        root (Path): Starting directory to search from.
        
    Returns:
        list[Path]: List of base directories each containing a 'raw' folder.
    """
    found: list[Path] = []
    root = Path(root).resolve()
    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        raw_dir = current / "raw"
        if raw_dir.is_dir():
            found.append(current)
            # Do not descend into raw/ or featured/ for other potential bases
            dirnames[:] = [
                d for d in dirnames if d.lower() not in ("raw", "featured")
            ]
    return sorted(found)


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

    # Step 1: Extract RAW file names (without extensions) from raw directory and subdirectories.
    print(f"\n{'Step 1: Scanning raw directory (recursively all RAW files)':-<50}")

    try:
        raw_file_names = _scan_raw_stems(raw_dir)
    except PermissionError:
        print(f"Error: Permission denied accessing '{raw_dir}'")
        return False
    
    if not raw_file_names:
        print("   Warning: No valid files found in raw directory.")
        return False
        
    print(f"   📊 Total unique file names: {len(raw_file_names)}")
    
    # Step 2: Find all matching files in target directory and image subdirectories
    print(f"\n{'Step 2: Finding matching files':-<50}")
    search_dirs = _get_image_search_directories(base_dir)
    subdir_names = [d.name for d in search_dirs if d != base_dir]
    if search_dirs:
        print(
            "   Searching in HIF directories: "
            + ", ".join(_display_search_dir(base_dir, directory) for directory in search_dirs)
        )
    elif subdir_names:
        print(f"   Searching in HIF directories: {subdir_names}")
    else:
        print("   Searching in HIF directories: none found")
    matching_files_by_stem: dict[str, Path] = {}
    searched_dirs: list[Path] = []
    seen_matches: set[Path] = set()  # dedup by real filesystem path (handles any edge cases)

    for search_dir in search_dirs:
        searched_dirs.append(search_dir)
        is_base = (search_dir.resolve() == base_dir.resolve())

        try:
            for file_path in search_dir.iterdir():
                if file_path.is_file():
                    # Use lowercase for case-insensitive matching
                    file_stem = file_path.stem.lower()
                    # Skip system files
                    if file_stem.startswith('.'):
                        continue
                    if file_stem in raw_file_names and file_path.suffix.lower() in FEATURED_EXTS:
                        if file_stem in matching_files_by_stem:
                            continue
                        real = file_path.resolve()
                        if real in seen_matches:
                            continue
                        seen_matches.add(real)
                        matching_files_by_stem[file_stem] = file_path

                        # Show relative path for subdirectory files, using the *real* dir name on disk
                        if is_base:
                            print(f"   ✓ Match: {file_path.name}")
                        else:
                            print(f"   ✓ Match: {_display_search_dir(base_dir, search_dir)}/{file_path.name}")
        except PermissionError:
            print(f"   ⚠️  Permission denied: {search_dir}")
            continue
    
    print(f"   📂 Searched directories: {len(searched_dirs)}")
    
    matching_files = [matching_files_by_stem[stem] for stem in sorted(matching_files_by_stem)]

    if not matching_files:
        print("   Warning: No matching files found in any searched directory.")
        return False
        
    print(f"   📊 Total matching files: {len(matching_files)}")
    missing_hif = sorted(raw_file_names - set(matching_files_by_stem))
    if missing_hif:
        print(f"   ⚠️  Missing matching HIF files: {', '.join(missing_hif)}")
    
    # Step 3: Create featured directory and copy files
    print(f"\n{'Step 3: Copying files to featured directory':-<50}")
    
    try:
        # Create featured directory (if it doesn't exist)
        featured_dir.mkdir(exist_ok=True)
        print(f"   📁 Directory ready: {featured_dir}")
        for existing in featured_dir.iterdir():
            if existing.is_file():
                existing.unlink()
            elif existing.is_dir() and existing.name == "contact_sheets":
                shutil.rmtree(existing)
        
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
        base_dir, recursive = get_target_directory()
        
        if recursive:
            bases = find_directories_with_raw(base_dir)
            print(f"\n{'='*60}")
            print(f"RECURSIVE MODE ENABLED")
            print(f"{'='*60}")
            print(f"Root search directory: {base_dir}")
            print(f"Found {len(bases)} directory(ies) containing a 'raw' subdirectory.")
            
            if not bases:
                print("No directories with 'raw' found. Nothing to do.")
                sys.exit(1)
            
            overall_success = True
            for idx, b in enumerate(bases, 1):
                print(f"\n--- [{idx}/{len(bases)}] {b} ---")
                if not process_files(b):
                    overall_success = False
            
            print(f"\n{'='*60}")
            if overall_success:
                print(f"🎉 All recursive operations completed successfully!")
            else:
                print(f"⚠️  Recursive operations completed with some issues.")
                sys.exit(1)
        else:
            # Process files (original single-directory behavior)
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
