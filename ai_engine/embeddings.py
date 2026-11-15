from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Loaded once per server process (not per request) — loading the model
# takes a second or two, so we keep it in memory rather than reloading
# it every time a gig/job is saved or a recommendation is computed.
_model = None


def get_model():
    global _model
    if _model is None:
        # all-MiniLM-L6-v2: a small, fast pretrained sentence-embedding
        # model — good accuracy-to-speed tradeoff for CPU-only inference,
        # which matters since this runs on a normal Django server with
        # no GPU.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_embedding(text):
    """
    Converts a piece of text into a fixed-length vector of numbers
    (384 dimensions for this model). Texts with similar MEANING end up
    with similar vectors, even if they share few or no exact words —
    this is what lets us match "React developer" to "frontend engineer"
    without keyword overlap.
    """
    if not text or not text.strip():
        return None
    model = get_model()
    vector = model.encode(text)
    return vector.tolist()  # convert numpy array -> plain list, so it can be stored as JSON


def compute_similarity(vector_a, vector_b):
    """
    Cosine similarity: measures the angle between two vectors, ignoring
    their length. Returns a score from -1 to 1, where 1 means "point in
    exactly the same direction" (very similar meaning) and 0 means
    "unrelated." In practice for real sentences this usually ranges
    roughly 0 to 1.
    """
    if vector_a is None or vector_b is None:
        return 0.0
    a = np.array(vector_a).reshape(1, -1)
    b = np.array(vector_b).reshape(1, -1)
    return float(cosine_similarity(a, b)[0][0])