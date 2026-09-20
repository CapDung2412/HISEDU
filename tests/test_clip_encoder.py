from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from hisedu.clip_encoder import ClipEncoder, EmbeddingError


class FakeModel:
    max_seq_length = 128

    def __init__(self, dimension: int = 3, vector=None) -> None:
        self.dimension = dimension
        self.vector = vector or [3.0, 4.0, 0.0]

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, inputs, **kwargs):
        return [list(self.vector) for _ in inputs]


class FailingImageModel(FakeModel):
    def get_sentence_embedding_dimension(self) -> int:
        raise AssertionError("image tower must stay lazy for text-only encoding")


class ClipEncoderTests(unittest.TestCase):
    def encoder(self, **kwargs) -> ClipEncoder:
        return ClipEncoder(
            text_model_name="text-test",
            image_model_name="image-test",
            text_model=kwargs.get("text_model", FakeModel()),
            image_model=kwargs.get("image_model", FakeModel()),
        )

    def test_text_vectors_are_float_l2_normalized(self) -> None:
        vectors = self.encoder().encode_texts(["xin chào", "lịch sử"])
        self.assertEqual(2, len(vectors))
        self.assertAlmostEqual(1.0, math.sqrt(sum(v * v for v in vectors[0])))
        self.assertEqual([0.6, 0.8, 0.0], vectors[0])

    def test_mismatched_tower_dimensions_are_rejected(self) -> None:
        encoder = self.encoder(image_model=FakeModel(dimension=4))
        with self.assertRaises(EmbeddingError):
            _ = encoder.dimension

    def test_non_finite_embedding_is_rejected(self) -> None:
        encoder = self.encoder(text_model=FakeModel(vector=[float("nan"), 0.0, 1.0]))
        with self.assertRaises(EmbeddingError):
            encoder.encode_texts(["test"])

    def test_text_encoding_does_not_initialize_image_dimension(self) -> None:
        encoder = self.encoder(image_model=FailingImageModel())
        self.assertEqual([0.6, 0.8, 0.0], encoder.encode_texts(["lịch sử"])[0])

    def test_local_only_flag_is_forwarded_to_sentence_transformer(self) -> None:
        calls = []

        def factory(model_name, **kwargs):
            calls.append((model_name, kwargs))
            return FakeModel()

        encoder = ClipEncoder(
            text_model_name="cached-text-model",
            image_model_name="cached-image-model",
            local_files_only=True,
        )
        with patch.object(ClipEncoder, "_sentence_transformer", return_value=factory):
            self.assertEqual(3, encoder.text_dimension)

        self.assertEqual("cached-text-model", calls[0][0])
        self.assertTrue(calls[0][1]["local_files_only"])


if __name__ == "__main__":
    unittest.main()
