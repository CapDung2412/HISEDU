from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence


class EmbeddingError(RuntimeError):
    """Raised when an encoder returns incompatible or unsafe embeddings."""


class TextTooLongError(EmbeddingError):
    """Raised instead of silently truncating text at the model token limit."""


def _rows(value: Any) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise EmbeddingError(f"Encoder returned unsupported type: {type(value).__name__}")
    if not value:
        return []
    if isinstance(value[0], (int, float)):
        value = [value]
    rows: list[list[float]] = []
    for row in value:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)):
            raise EmbeddingError("Encoder returned a non-vector row")
        rows.append([float(item) for item in row])
    return rows


def normalize_vector(vector: Sequence[float]) -> list[float]:
    result = [float(value) for value in vector]
    if not result:
        raise EmbeddingError("Embedding must not be empty")
    if not all(math.isfinite(value) for value in result):
        raise EmbeddingError("Embedding contains NaN or Infinity")
    norm = math.sqrt(sum(value * value for value in result))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingError("Embedding has zero or invalid L2 norm")
    return [value / norm for value in result]


class ClipEncoder:
    """Aligned Vietnamese text and image CLIP encoders.

    The default multilingual text model was distilled into the original
    clip-ViT-B-32 image space. Model loading is lazy so data validation and
    unit tests do not download model weights.
    """

    def __init__(
        self,
        *,
        text_model_name: str,
        image_model_name: str,
        device: str | None = None,
        batch_size: int = 32,
        text_model: Any = None,
        image_model: Any = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.text_model_name = text_model_name
        self.image_model_name = image_model_name
        self.device = device
        self.batch_size = batch_size
        self._text_model = text_model
        self._image_model = image_model
        self._dimension: int | None = None

    @property
    def model_fingerprint(self) -> str:
        return f"text={self.text_model_name}|image={self.image_model_name}"

    @staticmethod
    def _sentence_transformer() -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is not installed; run `python -m pip install -e .`"
            ) from exc
        return SentenceTransformer

    def _ensure_text_model(self) -> None:
        if self._text_model is not None:
            return
        SentenceTransformer = self._sentence_transformer()
        kwargs = {"device": self.device} if self.device else {}
        self._text_model = SentenceTransformer(self.text_model_name, **kwargs)

    def _ensure_image_model(self) -> None:
        if self._image_model is not None:
            return
        SentenceTransformer = self._sentence_transformer()
        kwargs = {"device": self.device} if self.device else {}
        self._image_model = SentenceTransformer(self.image_model_name, **kwargs)

    @staticmethod
    def _declared_dimension(model: Any) -> int | None:
        getter = getattr(model, "get_embedding_dimension", None)
        if getter is None:
            getter = getattr(model, "get_sentence_embedding_dimension", None)
        if getter is None:
            return None
        dimension = getter()
        return int(dimension) if dimension is not None else None

    @property
    def text_dimension(self) -> int:
        self._ensure_text_model()
        dimension = self._declared_dimension(self._text_model)
        if dimension is None:
            raise EmbeddingError("The CLIP text tower must declare its output dimension")
        return dimension

    @property
    def image_dimension(self) -> int:
        self._ensure_image_model()
        dimension = self._declared_dimension(self._image_model)
        if dimension is None:
            raise EmbeddingError("The CLIP image tower must declare its output dimension")
        return dimension

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            text_dimension = self.text_dimension
            image_dimension = self.image_dimension
            if text_dimension != image_dimension:
                raise EmbeddingError(
                    "Text/image CLIP dimensions differ: "
                    f"{text_dimension} != {image_dimension}"
                )
            self._dimension = text_dimension
        return self._dimension

    def _audit_token_lengths(self, texts: Sequence[str]) -> None:
        model = self._text_model
        limit = getattr(model, "max_seq_length", None)
        first_module = getattr(model, "_first_module", None)
        module = first_module() if callable(first_module) else None
        tokenizer = getattr(module, "tokenizer", None)
        if not limit or tokenizer is None:
            return
        encoded = tokenizer(
            list(texts), add_special_tokens=True, truncation=False, padding=False
        )
        input_ids = encoded.get("input_ids", [])
        too_long = [
            {"index": index, "tokens": len(token_ids), "limit": int(limit)}
            for index, token_ids in enumerate(input_ids)
            if len(token_ids) > int(limit)
        ]
        if too_long:
            raise TextTooLongError(
                f"Refusing silent CLIP truncation; over-limit inputs: {too_long[:10]}"
            )

    def _encode(
        self, model: Any, inputs: Sequence[Any], *, expected_dimension: int
    ) -> list[list[float]]:
        if not inputs:
            return []
        raw = model.encode(
            list(inputs),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = [normalize_vector(row) for row in _rows(raw)]
        if len(vectors) != len(inputs):
            raise EmbeddingError(
                f"Encoder returned {len(vectors)} vectors for {len(inputs)} inputs"
            )
        for index, vector in enumerate(vectors):
            if len(vector) != expected_dimension:
                raise EmbeddingError(
                    f"Embedding {index} has dimension {len(vector)}, expected "
                    f"{expected_dimension}"
                )
        return vectors

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self._ensure_text_model()
        normalized = [str(text).strip() for text in texts]
        if any(not text for text in normalized):
            raise EmbeddingError("Text inputs must not be empty")
        self._audit_token_lengths(normalized)
        return self._encode(
            self._text_model, normalized, expected_dimension=self.text_dimension
        )

    def encode_images(self, image_paths: Sequence[Path | str]) -> list[list[float]]:
        self._ensure_image_model()
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise EmbeddingError("Pillow is required for image encoding") from exc
        images = []
        for raw_path in image_paths:
            path = Path(raw_path)
            if not path.is_file():
                raise FileNotFoundError(path)
            with Image.open(path) as image:
                # Phone photos commonly rely on EXIF orientation. Apply it in
                # memory before encoding so a portrait question is not rotated.
                images.append(ImageOps.exif_transpose(image).convert("RGB"))
        return self._encode(
            self._image_model, images, expected_dimension=self.image_dimension
        )
