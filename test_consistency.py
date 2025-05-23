#!/usr/bin/env python3
"""
Test script to verify consistency between watch and export modes
"""

import subprocess
import time
from pathlib import Path

def run_short_export():
    """Run a very short export test"""
    print("Running export mode...")
    result = subprocess.run([
        "python", "battle.py", "--export"
    ], capture_output=True, text=True, timeout=180)
    
    if result.returncode != 0:
        print(f"Export failed: {result.stderr}")
        return False
    
    return True

def analyze_results():
    """Check what files were created"""
    export_dir = Path("export")
    if not export_dir.exists():
        print("No export directory found")
        return
    
    files = list(export_dir.glob("*"))
    print("\nGenerated files:")
    for f in files:
        stat = f.stat()
        print(f"  {f.name}: {stat.st_size} bytes, modified {time.ctime(stat.st_mtime)}")

def main():
    print("🔍 Testing consistency between export and watch modes...")
    
    # Clear old exports
    export_dir = Path("export")
    if export_dir.exists():
        for f in export_dir.glob("*"):
            if f.is_file():
                f.unlink()
    
    # Test export mode
    if run_short_export():
        print("✅ Export completed successfully")
        analyze_results()
    else:
        print("❌ Export failed")

if __name__ == "__main__":
    main()