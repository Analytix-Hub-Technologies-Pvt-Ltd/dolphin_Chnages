#!/usr/bin/env python3
"""
Cleanup script to remove invalid/junk images from storage directories.
This script validates existing images and removes those that don't meet quality standards.

# Dry run - preview what would be deleted (safe)
python scripts/cleanup_invalid_images.py --all
# Clean specific directories (dry run)
python scripts/cleanup_invalid_images.py --images
python scripts/cleanup_invalid_images.py --pdf-images
# Actually delete invalid images (use with caution)
python scripts/cleanup_invalid_images.py --all --live
"""

import os
import sys
from pathlib import Path
from PIL import Image
import io

# Add parent directory to path to import from course_sync
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_image_file(file_path: str, min_width: int = 10, min_height: int = 10, 
                        min_size: int = 100, max_size: int = 10 * 1024 * 1024) -> bool:
    """Validate an image file."""
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size < min_size or file_size > max_size:
            return False
        
        # Verify it's a valid image
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        
        # Re-open for dimension checks
        img = Image.open(io.BytesIO(image_data))
        
        # Check minimum dimensions
        if img.width < min_width or img.height < min_height:
            return False
        
        return True
        
    except Exception:
        return False

def cleanup_directory(directory: str, dry_run: bool = True):
    """Clean up invalid images in a directory."""
    if not os.path.exists(directory):
        print(f"Directory does not exist: {directory}")
        return
    
    total_files = 0
    invalid_files = 0
    removed_files = 0
    
    print(f"\nScanning directory: {directory}")
    print(f"Mode: {'DRY RUN (no files will be deleted)' if dry_run else 'LIVE (files will be deleted)'}")
    print("-" * 80)
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # Skip non-image files
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                continue
            
            file_path = os.path.join(root, filename)
            total_files += 1
            
            if not validate_image_file(file_path):
                invalid_files += 1
                file_size = os.path.getsize(file_path)
                print(f"Invalid: {filename} ({file_size} bytes)")
                
                if not dry_run:
                    try:
                        os.remove(file_path)
                        removed_files += 1
                        print(f"  → Removed")
                    except Exception as e:
                        print(f"  → Failed to remove: {e}")
    
    print("-" * 80)
    print(f"Total images scanned: {total_files}")
    print(f"Invalid images found: {invalid_files}")
    if not dry_run:
        print(f"Files removed: {removed_files}")
    print()

def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up invalid/junk images from storage')
    parser.add_argument('--live', action='store_true', help='Actually delete files (default is dry-run)')
    parser.add_argument('--images', action='store_true', help='Clean ./storage/images directory')
    parser.add_argument('--pdf-images', action='store_true', help='Clean ./storage/pdf_images directory')
    parser.add_argument('--all', action='store_true', help='Clean all storage directories')
    
    args = parser.parse_args()
    
    # Determine dry run mode
    dry_run = not args.live
    
    # Determine which directories to clean
    clean_images = args.images or args.all
    clean_pdf_images = args.pdf_images or args.all
    
    if not (clean_images or clean_pdf_images):
        print("Please specify which directories to clean:")
        print("  --images       Clean regular images")
        print("  --pdf-images   Clean PDF-extracted images")
        print("  --all          Clean all directories")
        print("\nAdd --live flag to actually delete files (default is dry-run)")
        return
    
    print("=" * 80)
    print("IMAGE CLEANUP SCRIPT")
    print("=" * 80)
    
    if clean_images:
        cleanup_directory('./storage/images', dry_run)
    
    if clean_pdf_images:
        cleanup_directory('./storage/pdf_images', dry_run)
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN. No files were deleted.")
        print("Run with --live flag to actually remove invalid images.")
    else:
        print("\n✅ Cleanup completed!")

if __name__ == '__main__':
    main()
