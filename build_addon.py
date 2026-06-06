#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""
Kodi Addon Build Script
Automatically packages the addon into a distributable ZIP file
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

# Files and directories to exclude from the package
EXCLUDE_PATTERNS = [
    ".git",
    ".gitignore",
    ".env",
    ".env.example",
    "venv",
    ".venv",  # Exclude .venv directory
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    "*.md",  # Exclude all markdown documentation files
    "*.log",  # Exclude log files
    "test_",  # Exclude test files (test_*.py)
    "api_explorer",  # Exclude API exploration scripts
    "api_test",
    "compare_",
    "auth_info_response.json",
    "api_test_results.json",
    "streams_response.json",
    "swagger-docs.json",
    "FILES_CREATED.txt",
    "PACKAGING_NOTES.txt",
    "BUILD_SUMMARY.txt",
    "INSTALL.md",
    "build_addon.py",  # Exclude this build script
    "dist",  # Exclude dist folder
    ".kiro",  # Exclude Kiro config
    ".vscode",  # Exclude VSCode config
]


def should_exclude(path, base_path):
    """Check if a file/directory should be excluded from the package"""
    rel_path = os.path.relpath(path, base_path)
    filename = os.path.basename(path)

    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*."):
            # File extension pattern
            if path.endswith(pattern[1:]):
                return True
        elif pattern.endswith("*"):
            # Prefix pattern
            if filename.startswith(pattern[:-1]):
                return True
        elif "*" in pattern:
            # Wildcard pattern
            import fnmatch

            if fnmatch.fnmatch(filename, pattern):
                return True
        else:
            # Exact match or directory name or prefix
            if pattern in rel_path.split(os.sep) or filename.startswith(pattern):
                return True

    return False


def get_addon_info():
    """Extract addon ID and version from addon.xml"""
    tree = ET.parse("addon.xml")
    root = tree.getroot()

    addon_id = root.get("id")
    version = root.get("version")

    return addon_id, version


def create_zip_package(addon_id, version, output_dir="dist"):
    """Create a ZIP package with proper Kodi addon structure"""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # ZIP filename
    zip_filename = f"{addon_id}-{version}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    # Remove existing ZIP if present
    if os.path.exists(zip_path):
        os.remove(zip_path)
        print(f"Removed existing: {zip_path}")

    # Get current directory
    base_path = os.getcwd()

    print(f"Creating package: {zip_filename}")
    print(f"Addon ID: {addon_id}")
    print(f"Version: {version}")
    print()

    # Create ZIP file
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Walk through all files
        for root, dirs, files in os.walk("."):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), base_path)]

            for file in files:
                file_path = os.path.join(root, file)

                # Skip excluded files
                if should_exclude(file_path, base_path):
                    continue

                # Create archive path with addon folder structure
                # Remove leading './' or '.\'
                rel_path = os.path.relpath(file_path, ".")
                archive_path = os.path.join(addon_id, rel_path)

                # Add file to ZIP
                zipf.write(file_path, archive_path)
                print(f"  Added: {rel_path}")

    print()
    print(f"✓ Package created successfully: {zip_path}")
    print(f"  Size: {os.path.getsize(zip_path) / 1024:.2f} KB")

    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="Build Kodi addon package",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_addon.py                 # Build with current version
  python build_addon.py --output build  # Output to 'build' directory
        """,
    )

    parser.add_argument("--output", "-o", default="dist", help="Output directory for the ZIP file (default: dist)")

    args = parser.parse_args()

    # Check if addon.xml exists
    if not os.path.exists("addon.xml"):
        print("Error: addon.xml not found in current directory")
        sys.exit(1)

    try:
        # Get addon information
        addon_id, version = get_addon_info()

        # Create package
        zip_path = create_zip_package(addon_id, version, args.output)

        print()
        print("Installation instructions:")
        print(f"  1. Copy {os.path.basename(zip_path)} to your Kodi device")
        print("  2. In Kodi: Settings → Add-ons → Install from zip file")
        print(f"  3. Select {os.path.basename(zip_path)}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
