from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .clip_encoder import ClipEncoder
from .dataset import HISEduDataset, chunks
from .pinecone_store import PineconeVectorStore


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_dataset(dataset: HISEduDataset) -> dict[str, Any]:
    records = dataset.load()
    versions = sorted({record.dataset_version for record in records})
    return {
        "records": len(records),
        "unique_record_ids": len({record.record_id for record in records}),
        "unique_chunk_ids": len({record.chunk_id for record in records}),
        "dataset_versions": versions,
        "valid": bool(records),
    }


def run_ingest(
    dataset: HISEduDataset,
    encoder: ClipEncoder,
    store: PineconeVectorStore,
    *,
    embedding_batch_size: int,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    started_at = utc_now()
    records = dataset.load()
    dimension = encoder.dimension
    store.ensure_index(dimension)
    upserted = 0
    for record_batch in chunks(records, embedding_batch_size):
        texts = [record.search_text for record in record_batch]
        embeddings = encoder.encode_texts(texts)
        documents = [
            record.pinecone_document(
                embedding, embedding_model=encoder.model_fingerprint
            )
            for record, embedding in zip(record_batch, embeddings, strict=True)
        ]
        upserted += store.upsert_documents(documents)

    aggregate_checksum = hashlib.sha256(
        "\n".join(record.content_checksum for record in records).encode("ascii")
    ).hexdigest()
    manifest = {
        "status": "completed",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "record_count": len(records),
        "upserted_count": upserted,
        "idempotent_vector_id": "chunk_id",
        "dataset_versions": sorted({record.dataset_version for record in records}),
        "dataset_checksum": aggregate_checksum,
        "embedding_model": encoder.model_fingerprint,
        "embedding_dimension": dimension,
        "index_name": store.settings.pinecone_index_name,
        "namespace": store.settings.pinecone_namespace,
        "metric": "cosine",
    }
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest

