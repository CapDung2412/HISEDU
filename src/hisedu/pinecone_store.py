from __future__ import annotations

import math
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

from .config import Settings
from .dataset import chunks


class VectorStoreError(RuntimeError):
    """Raised when a Pinecone index is incompatible or an operation fails."""


DEFAULT_RETURN_FIELDS = [
    "record_id",
    "chunk_id",
    "dataset_version",
    "title",
    "question",
    "answer",
    "answer_type",
    "difficulty",
    "chapter_title",
    "lesson_title",
    "source_txt",
    "source_json",
    "source_name",
    "source_url",
    "source_locator",
    "source_page_number",
    "review_status",
    "provenance_note",
    "content_checksum",
    "embedding_model",
]


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        return converter()
    return value


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


class PineconeVectorStore:
    """Pinecone 10 schema-based dense-vector document index."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.settings = settings
        self._client = client
        self._index = None
        self._dimension: int | None = None
        self._sleep = sleep
        self._max_attempts = max_attempts

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.settings.pinecone_api_key:
            raise VectorStoreError("PINECONE_API_KEY is not configured")
        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise VectorStoreError(
                "pinecone is not installed; run `python -m pip install -e .`"
            ) from exc
        self._client = Pinecone(api_key=self.settings.pinecone_api_key)
        return self._client

    @staticmethod
    def _index_names(client: Any) -> set[str]:
        names: set[str] = set()
        for item in client.indexes.list():
            name = _get(item, "name")
            if name:
                names.add(str(name))
        return names

    @staticmethod
    def _embedding_field(description: Any) -> dict[str, Any] | None:
        document = _plain(description)
        schema = _get(document, "schema", {})
        schema = _plain(schema)
        fields = _get(schema, "fields", {})
        fields = _plain(fields)
        field = _get(fields, "embedding")
        field = _plain(field)
        return field if isinstance(field, dict) else None

    @staticmethod
    def _validate_field(field: dict[str, Any] | None, dimension: int) -> None:
        if not field:
            raise VectorStoreError("Existing index has no dense `embedding` field")
        field_type = str(field.get("type", "")).lower()
        if "dense_vector" not in field_type:
            raise VectorStoreError(
                f"Existing `embedding` field is not dense_vector: {field_type!r}"
            )
        actual_dimension = int(field.get("dimension", -1))
        if actual_dimension != dimension:
            raise VectorStoreError(
                f"Pinecone dimension mismatch: index={actual_dimension}, encoder={dimension}"
            )
        metric = str(field.get("metric", "")).lower()
        if not metric.endswith("cosine"):
            raise VectorStoreError(
                f"Pinecone metric mismatch: expected cosine, found {metric!r}"
            )

    def ensure_index(self, dimension: int, *, create_if_missing: bool = True) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        client = self._ensure_client()
        name = self.settings.pinecone_index_name
        names = self._retry(lambda: self._index_names(client))
        if name not in names:
            if not create_if_missing:
                raise VectorStoreError(f"Pinecone index does not exist: {name}")
            self._retry(
                lambda: client.indexes.create(
                    name=name,
                    schema={
                        "fields": {
                            "embedding": {
                                "type": "dense_vector",
                                "dimension": dimension,
                                "metric": "cosine",
                            }
                        }
                    },
                    deployment={
                        "deployment_type": "managed",
                        "cloud": self.settings.pinecone_cloud,
                        "region": self.settings.pinecone_region,
                    },
                )
            )
        description = self._retry(lambda: client.indexes.describe(name))
        self._validate_field(self._embedding_field(description), dimension)
        self._index = client.index(name)
        self._dimension = dimension

    def _require_index(self) -> Any:
        if self._index is None or self._dimension is None:
            raise VectorStoreError("Call ensure_index(dimension) before data operations")
        return self._index

    def _retry(self, operation: Callable[[], Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return operation()
            except Exception as exc:  # SDK errors vary by transport/version
                last_error = exc
                if attempt < self._max_attempts:
                    self._sleep(float(2 ** (attempt - 1)))
        raise VectorStoreError(
            f"Pinecone operation failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error

    def upsert_documents(
        self, documents: Sequence[dict[str, Any]], *, batch_size: int | None = None
    ) -> int:
        index = self._require_index()
        size = batch_size or self.settings.upsert_batch_size
        total = 0
        for batch in chunks(documents, size):
            payload = list(batch)
            self._retry(
                lambda payload=payload: index.documents.upsert(
                    namespace=self.settings.pinecone_namespace,
                    documents=payload,
                )
            )
            total += len(payload)
        return total

    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 5,
        fields: Sequence[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        index = self._require_index()
        values = [float(value) for value in vector]
        if len(values) != self._dimension:
            raise VectorStoreError(
                f"Query dimension {len(values)} does not match index {self._dimension}"
            )
        if not all(math.isfinite(value) for value in values):
            raise VectorStoreError("Query vector contains NaN or Infinity")
        if not 1 <= top_k <= 10_000:
            raise ValueError("top_k must be between 1 and 10000")
        response = self._retry(
            lambda: index.documents.search(
                namespace=self.settings.pinecone_namespace,
                top_k=top_k,
                score_by=[
                    {
                        "type": "dense_vector",
                        "field": "embedding",
                        "values": values,
                    }
                ],
                include_fields=list(fields or DEFAULT_RETURN_FIELDS),
                filter=metadata_filter,
            )
        )
        matches = _get(response, "matches", []) or []
        output: list[dict[str, Any]] = []
        for match in matches:
            # Pinecone SDK v10 exposes requested document fields directly on the
            # Document object (and in ``to_dict()``), alongside ``_id`` and
            # ``_score``. Keep support for the older/nested fake response shape
            # used by callers and tests as well.
            document = _plain(match)
            nested_fields = _get(document, "fields")
            if isinstance(nested_fields, Mapping):
                returned_fields = dict(nested_fields)
            elif isinstance(document, Mapping):
                returned_fields = {
                    key: value
                    for key, value in document.items()
                    if key not in {"_id", "_score", "id", "score"}
                }
            else:
                returned_fields = {}

            match_id = _get(match, "id") or _get(document, "_id", "")
            match_score = _get(match, "score")
            if match_score is None:
                match_score = _get(document, "_score", 0.0)
            output.append(
                {
                    "id": str(match_id),
                    "score": float(match_score),
                    "fields": returned_fields,
                }
            )
        return output
