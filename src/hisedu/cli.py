from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .clip_encoder import ClipEncoder
from .config import ConfigurationError, Settings
from .dataset import HISEduDataset
from .ingest import run_ingest, validate_dataset
from .ocr import PaddleOcrExtractor
from .pinecone_store import PineconeVectorStore
from .query import ImageQueryService


def configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_dataset(settings: Settings) -> HISEduDataset:
    return HISEduDataset(settings.questions_dir, settings.answers_dir)


def build_encoder(settings: Settings) -> ClipEncoder:
    return ClipEncoder(
        text_model_name=settings.text_model,
        image_model_name=settings.image_model,
        device=settings.device,
        batch_size=settings.embedding_batch_size,
    )


def cmd_validate_data(_: argparse.Namespace) -> int:
    settings = Settings.from_env(require_pinecone=False)
    emit(validate_dataset(build_dataset(settings)))
    return 0


def cmd_ingest(_: argparse.Namespace) -> int:
    settings = Settings.from_env(require_pinecone=True)
    encoder = build_encoder(settings)
    store = PineconeVectorStore(settings)
    manifest = run_ingest(
        build_dataset(settings),
        encoder,
        store,
        embedding_batch_size=settings.embedding_batch_size,
        manifest_path=settings.reports_dir / "ingest_manifest.json",
    )
    emit(manifest)
    return 0


def cmd_query_image(args: argparse.Namespace) -> int:
    settings = Settings.from_env(require_pinecone=True)
    encoder = build_encoder(settings)
    store = PineconeVectorStore(settings)
    store.ensure_index(encoder.dimension, create_if_missing=False)
    ocr = None
    if args.mode in {"ocr", "hybrid"}:
        ocr = PaddleOcrExtractor(
            language=settings.ocr_language,
            min_line_score=settings.ocr_min_line_score,
        )
    threshold = args.min_score if args.min_score is not None else settings.min_score
    service = ImageQueryService(
        encoder, store, ocr=ocr, min_score=threshold
    )
    emit(
        service.query_image(
            Path(args.image), top_k=args.top_k, mode=args.mode
        )
    )
    return 0


def cmd_query_text(args: argparse.Namespace) -> int:
    settings = Settings.from_env(require_pinecone=True)
    encoder = build_encoder(settings)
    store = PineconeVectorStore(settings)
    # A text-only query must not initialize the image tower or OCR stack.
    store.ensure_index(encoder.text_dimension, create_if_missing=False)
    vector = encoder.encode_texts([args.text])[0]
    matches = store.query(vector, top_k=args.top_k)
    emit({"text": args.text, "matches": matches})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hisedu", description="HISEDU CLIP + Pinecone retrieval pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-data", help="Validate all normalized TXT/JSON pairs locally"
    )
    validate_parser.set_defaults(handler=cmd_validate_data)

    ingest_parser = subparsers.add_parser(
        "ingest", help="Encode all questions and idempotently upsert to Pinecone"
    )
    ingest_parser.set_defaults(handler=cmd_ingest)

    image_parser = subparsers.add_parser(
        "query-image", help="Find question records from a local image"
    )
    image_parser.add_argument("image")
    image_parser.add_argument("--top-k", type=int, default=5)
    image_parser.add_argument(
        "--mode", choices=("clip", "ocr", "hybrid"), default="hybrid"
    )
    image_parser.add_argument("--min-score", type=float)
    image_parser.set_defaults(handler=cmd_query_image)

    text_parser = subparsers.add_parser(
        "query-text", help="Text-query smoke test in the aligned CLIP index"
    )
    text_parser.add_argument("text")
    text_parser.add_argument("--top-k", type=int, default=5)
    text_parser.set_defaults(handler=cmd_query_text)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ConfigurationError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print(
            json.dumps(
                {"status": "error", "type": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
