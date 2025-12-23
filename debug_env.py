import sys
import os
import site

print("--- Python Environment Debug ---")
print(f"Python Version: {sys.version}")
print(f"Executable: {sys.executable}")
print(f"Working Directory: {os.getcwd()}")
print("\n--- sys.path ---")
for p in sys.path:
    print(f"  {p}")

print("\n--- site-packages contents (ALL) ---")
for sp in site.getsitepackages():
    print(f"\nChecking: {sp}")
    if os.path.exists(sp):
        try:
            items = os.listdir(sp)
            for item in items:
                print(f"  {item}")
        except Exception as e:
            print(f"  Error listing directory: {e}")
    else:
        print("  Path does not exist.")

from importlib import metadata
print("\n--- Package Metadata ---")
try:
    dist = metadata.distribution('py3-pinterest')
    print(f"py3-pinterest found via metadata")
    print(f"Location: {dist.locate_file('')}")
    print("Files in package:")
    if dist.files:
        for f in list(dist.files)[:10]: # show first 10 files
            print(f"  {f}")
    else:
        print("  No files listed in metadata!")
except Exception as e:
    print(f"Metadata check failed: {e}")

print("\n--- Trying imports ---")
try:
    import py3_pinterest
    print("SUCCESS: import py3_pinterest")
    print(f"  File: {py3_pinterest.__file__}")
except ImportError as e:
    print(f"FAILED: import py3_pinterest ({e})")

try:
    import pinterest
    print("SUCCESS: import pinterest")
except ImportError as e:
    print(f"FAILED: import pinterest ({e})")

input("\nPress Enter to finish diagnostic...")
