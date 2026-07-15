"""Download the fastembed model at build time.

Run in Dockerfile to pre-cache the model so first startup is fast.
"""
import sys
from fastembed import TextEmbedding
m = TextEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    max_length=128,
)
print("✓ fastembed model downloaded and cached")
sys.exit(0)
