from __future__ import annotations

import unittest
from unittest.mock import patch

from hisedu.config import Settings
from hisedu.dataset import HISEduDataset
from hisedu.webapi.services import HISEduRetrievalService


class RetrievalFastPathTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_dataset_question_skips_clip_and_pinecone(self) -> None:
        settings = Settings.from_env(require_pinecone=False)
        record = HISEduDataset(settings.questions_dir, settings.answers_dir).load()[0]
        service = HISEduRetrievalService(
            timeout_seconds=1.0, pinecone_timeout_seconds=1.0
        )
        local_index = service._ensure_exact_text_index()

        self.assertEqual(327, sum(len(matches) for matches in local_index.values()))

        with patch.object(
            service,
            "_runtime",
            side_effect=AssertionError("remote retrieval must not run"),
        ):
            result = await service.search_text(
                f"  {record.question.upper()}  ", top_k=3
            )

        self.assertEqual("mixed", result.score_kind)
        self.assertEqual(1, len(result.matches))
        self.assertEqual(record.chunk_id, result.matches[0]["id"])
        self.assertEqual("exact_match", result.matches[0]["confidence_status"])
        self.assertEqual("local_exact", result.matches[0]["retrieval_path"])
        self.assertEqual(record.answer, result.matches[0]["fields"]["answer"])


if __name__ == "__main__":
    unittest.main()
