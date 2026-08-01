from pydantic import BaseModel, Field


class CodebaseIndexRequest(BaseModel):
    local_repo_path: str = Field(min_length=1, max_length=4096)


class GitHubCodebaseIndexRequest(BaseModel):
    github_url: str = Field(min_length=10, max_length=2048, pattern=r"^https://github\.com/[^/\s]+/[^/\s]+/?$")


class CodebaseIndexResponse(BaseModel):
    repo_path: str
    source_url: str | None = None
    indexed_files: int
    indexed_chunks: int
    skipped_files: int
    message: str
    errors: list[str] = []


class CodebaseStatusResponse(BaseModel):
    indexed_files: int
    indexed_chunks: int
    last_indexed_at: str | None = None


class CodeChunkRead(BaseModel):
    id: int
    repo_path: str
    file_path: str
    language: str
    contextualized_text: str | None = None
    function_or_class_name: str | None = None
    chunk_type: str
    start_line: int
    end_line: int
    embedding_id: str | None = None

    model_config = {"from_attributes": True}


class CodeSnippetRead(BaseModel):
    evidence_id: int | None = None
    code_chunk_id: int | None = None
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    relevance_score: float
    evidence_type: str | None = None
    reason: str


class CodeRetrievalResponse(BaseModel):
    cluster_id: int
    query: str
    snippets: list[CodeSnippetRead]
    message: str
