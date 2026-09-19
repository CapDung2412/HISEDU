from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hisedu.ocr import PaddleOcrExtractor
from hisedu.query import ImageQueryService


class FakeOcrPayload:
    json = {
        "res": {
            "rec_texts": ["Cách mạng tư sản Anh", "năm nào?", "nhiễu"],
            "rec_scores": [0.99, 0.95, 0.10],
        }
    }


class FakeOcrPipeline:
    def predict(self, path):
        return [FakeOcrPayload()]


class FakeEncoder:
    def encode_images(self, paths):
        return [[1.0, 0.0, 0.0] for _ in paths]

    def encode_texts(self, texts):
        return [[0.0, 1.0, 0.0] for _ in texts]


class FakeStore:
    def query(self, vector, *, top_k):
        if vector[0] == 1.0:
            return [
                {"id": "a", "score": 0.70, "fields": {"question": "A"}},
                {"id": "b", "score": 0.60, "fields": {"question": "B"}},
            ]
        return [
            {"id": "b", "score": 0.92, "fields": {"question": "B"}},
            {"id": "a", "score": 0.80, "fields": {"question": "A"}},
        ]


class OcrAndQueryTests(unittest.TestCase):
    def test_paddle_result_parsing_and_score_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "photo.jpg"
            image.write_bytes(b"test")
            extractor = PaddleOcrExtractor(
                min_line_score=0.5, pipeline=FakeOcrPipeline()
            )
            result = extractor.extract(image)
        self.assertEqual("Cách mạng tư sản Anh năm nào?", result.text)
        self.assertEqual(2, len(result.lines))

    def test_hybrid_query_fuses_clip_and_ocr_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "photo.jpg"
            image.write_bytes(b"test")
            service = ImageQueryService(
                FakeEncoder(),
                FakeStore(),
                ocr=PaddleOcrExtractor(
                    min_line_score=0.5, pipeline=FakeOcrPipeline()
                ),
                min_score=0.75,
            )
            result = service.query_image(image, top_k=2, mode="hybrid")
        self.assertEqual(["clip", "ocr"], result["branches_used"])
        self.assertEqual("b", result["matches"][0]["id"])
        self.assertEqual("reciprocal_rank_fusion", result["matches"][0]["score_kind"])
        self.assertEqual("accepted", result["matches"][0]["confidence_status"])


if __name__ == "__main__":
    unittest.main()

