#!/usr/bin/env python3
"""
Clear FAISS rebuild checkpoint files.
Run this if you want to start a fresh rebuild without resuming from checkpoint.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    checkpoint_dir = Path("data/checkpoints")
    checkpoint_file = checkpoint_dir / "faiss_rebuild_checkpoint.pkl"
    
    if checkpoint_file.exists():
        print(f"Found checkpoint file: {checkpoint_file}")
        checkpoint_file.unlink()
        print("✓ Checkpoint file deleted. Next rebuild will start from scratch.")
    else:
        print("No checkpoint file found. Nothing to delete.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
