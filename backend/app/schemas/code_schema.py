from pydantic import BaseModel


class CodeSnippetRead(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    relevance_score: float
    reason: str
