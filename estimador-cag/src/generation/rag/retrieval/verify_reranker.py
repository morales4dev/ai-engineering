"""Download and load the configured cross-encoder to verify local setup."""

from dependencies import get_reranker


def main() -> None:
    reranker = get_reranker()
    reranker.load()
    print(f"Reranker loaded: {reranker.model_name}")


if __name__ == "__main__":
    main()
