import sys
import pickle
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.faiss_store import FAISSStore

def main():
    checkpoint_file = Path("data/checkpoints/faiss_rebuild_checkpoint.pkl")
    if not checkpoint_file.exists():
        print("Checkpoint file not found!")
        return 1
        
    print(f"Loading checkpoint from {checkpoint_file}...")
    with open(checkpoint_file, 'rb') as f:
        checkpoint_data = pickle.load(f)
        
    embeddings = checkpoint_data.get('embeddings', [])
    metadatas = checkpoint_data.get('metadatas', [])
    
    print(f"Loaded {len(embeddings)} embeddings and {len(metadatas)} metadatas.")
    if not embeddings:
        print("No embeddings in checkpoint.")
        return 1
        
    store = FAISSStore()
    emb_array = np.array(embeddings, dtype="float32")
    print(f"Embedding array shape: {emb_array.shape}")
    
    print("Building FAISS index...")
    store.build_from_embeddings(emb_array, metadatas)
    
    print("Saving to disk...")
    store.save()
    print("✓ FAISS index successfully created from checkpoint!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
