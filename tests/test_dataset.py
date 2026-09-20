from __future__ import annotations

import unittest
from pathlib import Path

from hisedu.dataset import HISEduDataset


ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def test_normalized_dataset_loads_and_is_unique(self) -> None:
        records = HISEduDataset(ROOT / "questions", ROOT / "answers").load()
        self.assertEqual(327, len(records))
        self.assertEqual(327, len({record.record_id for record in records}))
        self.assertEqual(327, len({record.chunk_id for record in records}))
        self.assertTrue(all(record.question for record in records))
        self.assertTrue(all(record.answer for record in records))
        self.assertTrue(all(record.source_txt.startswith("questions/") for record in records))
        self.assertTrue(all(record.source_json.startswith("answers/") for record in records))

    def test_pinecone_document_is_flat_and_uses_chunk_id(self) -> None:
        record = HISEduDataset(ROOT / "questions", ROOT / "answers").load()[0]
        document = record.pinecone_document(
            [1.0, 0.0, 0.0], embedding_model="test-model"
        )
        self.assertEqual(record.chunk_id, document["_id"])
        self.assertEqual(3, document["embedding_dimension"])
        self.assertNotIn("source_page_number", document)
        self.assertEqual(8, document["source_grade"])
        self.assertIn("Kết nối tri thức", document["source_book_series"])
        self.assertEqual("unverified", document["source_page_status"])
        self.assertTrue(all(not isinstance(value, dict) for value in document.values()))


if __name__ == "__main__":
    unittest.main()
