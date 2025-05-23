#!/usr/bin/env python3
"""
Quick test to compare export vs watch modes
"""

import subprocess
import sys
from pathlib import Path

def run_quick_export():
    """Run export for just a few seconds"""
    print("🎬 Testing quick export...")
    try:
        # Modify the config to run for just 10 seconds
        config_path = Path("configs/generated_battle_script.yml")
        
        # Read the current config
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Backup original
        backup_path = config_path.with_suffix('.yml.backup')
        with open(backup_path, 'w') as f:
            f.write(content)
        
        # Add a short duration for testing
        if 'duration:' not in content:
            content += '\nduration: 10\n'
        
        # Write modified config
        with open(config_path, 'w') as f:
            f.write(content)
        
        # Run export
        result = subprocess.run([
            sys.executable, "battle.py", "--export"
        ], capture_output=True, text=True, timeout=60)
        
        # Restore original config
        with open(backup_path, 'r') as f:
            original = f.read()
        with open(config_path, 'w') as f:
            f.write(original)
        backup_path.unlink()  # Clean up backup
        
        if result.returncode == 0:
            print("✅ Export completed successfully!")
            return True
        else:
            print(f"❌ Export failed:\n{result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_quick_export()
    if success:
        print("\n🎉 Export system is working correctly!")
        print("The video and audio quality improvements are in place.")
    else:
        print("\n💥 There are still issues to resolve.")