import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class VectorStore:

    def __init__(self):

        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        self.index = faiss.IndexFlatL2(384)

        self.documents = []

    def add(self, text):

        embedding = self.model.encode([text])

        self.index.add(
            np.array(embedding).astype("float32")
        )

        self.documents.append(text)

    def search(self, query, k=3):

        embedding = self.model.encode([query])

        distances, indices = self.index.search(
            np.array(embedding).astype("float32"),
            k
        )

        return [
            self.documents[i]
            for i in indices[0]
            if i < len(self.documents)
        ]

   