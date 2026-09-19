from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hisedu.config import Settings
from hisedu.dataset import HISEduDataset
from hisedu.ingest import run_ingest


ROOT = Path(__file__).resolve().parents[1]


class FakeEncoder:
    dimension = 3
    model_fingerprint = "fake-aligned-clip"

    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeStore:
    def __init__(self) -> None:
        self.settings = Settings(pinecone_api_key="test-key")
        self.dimension = None
        self.records = {}

    def ensure_index(self, dimension, *, create_if_missing=True):
        self.dimension = dimension

    def upsert_documents(self, documents, *, batch_size=None):
        for document in documents:
            self.records[document["_id"]] = document
        return len(documents)


class IngestTests(unittest.TestCase):
    def test_ingest_all_records_and_rerun_is_idempotent(self) -> None:
        dataset = HISEduDataset(ROOT / "questions", ROOT / "answers")
        store = FakeStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            first = run_ingest(
                dataset,
                FakeEncoder(),
                store,
                embedding_batch_size=64,
                manifest_path=manifest_path,
            )
            second = run_ingest(
                dataset,
                FakeEncoder(),
                store,
                embedding_batch_size=64,
            )
            self.assertTrue(manifest_path.is_file())
        self.assertEqual(327, first["record_count"])
        self.assertEqual(327, second["upserted_count"])
        self.assertEqual(327, len(store.records))
        self.assertEqual(3, store.dimension)


if __name__ == "__main__":
    unittest.main()

