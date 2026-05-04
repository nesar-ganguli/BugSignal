from app.config import get_settings


class ChromaDependencyError(RuntimeError):
    pass


def get_code_collection():
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as exc:
        raise ChromaDependencyError(
            "chromadb is not installed. Install backend requirements before indexing code."
        ) from exc

    settings = get_settings()
    client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(name="code_chunks")
