"""Load documents into the knowledge base.

  uv run python -m app.ingest                          # everything in data/docs/
  uv run python -m app.ingest --url https://site.com/faq --url https://site.com/shipping
  uv run python -m app.ingest --reset                  # wipe and rebuild
"""

import argparse
import logging

from app.config import get_settings
from app.knowledge import SUPPORTED_EXTENSIONS, KnowledgeBase, load_file, load_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Index documents for the support agent.")
    parser.add_argument("--url", action="append", default=[], help="Web page to index (repeatable)")
    parser.add_argument("--reset", action="store_true", help="Delete everything before indexing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    kb = KnowledgeBase(settings)
    if args.reset:
        kb.reset()
        print("Knowledge base cleared.")

    files = sorted(p for p in settings.docs_dir.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    for path in files:
        try:
            count = kb.add_document(path.name, load_file(path))
            print(f"  [file] {path.name}: {count} chunks")
        except Exception as exc:
            print(f"  [skip] {path.name}: {exc}")

    for url in args.url:
        try:
            count = kb.add_document(url, load_url(url))
            print(f"  [url]  {url}: {count} chunks")
        except Exception as exc:
            print(f"  [skip] {url}: {exc}")

    print(f"Done. {len(kb.sources())} sources indexed.")


if __name__ == "__main__":
    main()
