from __future__ import annotations

import unittest

from hisedu.config import Settings
from hisedu.pinecone_store import PineconeVectorStore, VectorStoreError


class FakeDocuments:
    def __init__(self) -> None:
        self.records = {}

    def upsert(self, *, namespace, documents):
        bucket = self.records.setdefault(namespace, {})
        for document in documents:
            bucket[document["_id"]] = dict(document)
        return {"upserted_count": len(documents)}

    def search(self, *, namespace, top_k, score_by, include_fields, filter=None):
        values = list(self.records.get(namespace, {}).values())[:top_k]
        return {
            "matches": [
                {
                    "id": value["_id"],
                    "score": 0.9 - index * 0.1,
                    "fields": {
                        field: value[field] for field in include_fields if field in value
                    },
                }
                for index, value in enumerate(values)
            ]
        }


class FakeIndex:
    def __init__(self) -> None:
        self.documents = FakeDocuments()


class SdkV10Document:
    """Minimal stand-in for Pinecone v10's open-schema Document."""

    def __init__(self, data):
        self._data = data

    @property
    def id(self):
        return self._data["_id"]

    @property
    def score(self):
        return self._data["_score"]

    def to_dict(self):
        return dict(self._data)


class FakeIndexes:
    def __init__(self) -> None:
        self.descriptions = {}

    def list(self):
        return [{"name": name} for name in self.descriptions]

    def create(self, *, name, schema, deployment):
        self.descriptions[name] = {"name": name, "schema": schema}

    def describe(self, name):
        return self.descriptions[name]


class FakeClient:
    def __init__(self) -> None:
        self.indexes = FakeIndexes()
        self.data_indexes = {}

    def index(self, name):
        return self.data_indexes.setdefault(name, FakeIndex())


class PineconeStoreTests(unittest.TestCase):
    def settings(self) -> Settings:
        return Settings(pinecone_api_key="test-key")

    def test_create_upsert_is_idempotent_and_query_returns_fields(self) -> None:
        client = FakeClient()
        store = PineconeVectorStore(
            self.settings(), client=client, sleep=lambda _: None
        )
        store.ensure_index(3)
        document = {
            "_id": "chunk-1",
            "embedding": [1.0, 0.0, 0.0],
            "question": "Câu hỏi",
            "answer": "Câu trả lời",
        }
        self.assertEqual(1, store.upsert_documents([document]))
        self.assertEqual(1, store.upsert_documents([document]))
        bucket = client.data_indexes[store.settings.pinecone_index_name].documents.records[
            store.settings.pinecone_namespace
        ]
        self.assertEqual(1, len(bucket))
        matches = store.query([1.0, 0.0, 0.0])
        self.assertEqual("chunk-1", matches[0]["id"])
        self.assertEqual("Câu hỏi", matches[0]["fields"]["question"])

    def test_existing_dimension_mismatch_is_not_recreated(self) -> None:
        client = FakeClient()
        name = self.settings().pinecone_index_name
        client.indexes.descriptions[name] = {
            "schema": {
                "fields": {
                    "embedding": {
                        "type": "dense_vector",
                        "dimension": 4,
                        "metric": "cosine",
                    }
                }
            }
        }
        store = PineconeVectorStore(self.settings(), client=client)
        with self.assertRaises(VectorStoreError):
            store.ensure_index(3)

    def test_query_reads_open_schema_fields_from_sdk_v10_document(self) -> None:
        client = FakeClient()
        store = PineconeVectorStore(
            self.settings(), client=client, sleep=lambda _: None
        )
        store.ensure_index(3)
        client.data_indexes[store.settings.pinecone_index_name].documents.search = (
            lambda **_: type(
                "Response",
                (),
                {
                    "matches": [
                        SdkV10Document(
                            {
                                "_id": "chunk-1",
                                "_score": 0.95,
                                "question": "Câu hỏi",
                                "answer": "Câu trả lời",
                            }
                        )
                    ]
                },
            )()
        )

        match = store.query([1.0, 0.0, 0.0])[0]
        self.assertEqual("chunk-1", match["id"])
        self.assertEqual(0.95, match["score"])
        self.assertEqual("Câu hỏi", match["fields"]["question"])
        self.assertEqual("Câu trả lời", match["fields"]["answer"])


if __name__ == "__main__":
    unittest.main()
