from functools import lru_cache

import numpy as np

from app.config import get_settings


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingDependencyError(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device
        self._model = _load_model(self.model_name, self.device)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0))
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=np.float32)


@lru_cache(maxsize=4)
def _load_model(model_name: str, device: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingDependencyError(
            "sentence-transformers is not installed. Install backend requirements before clustering."
        ) from exc

    try:
        return SentenceTransformer(model_name, device=device)
    except Exception as exc:
        raise EmbeddingDependencyError(
            f"Unable to load embedding model {model_name}. "
            "Ensure the model can be downloaded once or is already cached locally."
        ) from exc
