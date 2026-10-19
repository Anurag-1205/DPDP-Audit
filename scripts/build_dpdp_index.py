"""Embed DPDP units with bge-small and write the FAISS index to outputs/cache/."""
from dpdp_audit.retrieval import build_index

if __name__ == "__main__":
    idx = build_index()
    print(f"indexed {idx.ntotal} DPDP units")
