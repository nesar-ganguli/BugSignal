from dataclasses import dataclass

import httpx

from app.config import Settings
from app.models import IssueDraft


class GitHubIssueCreationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubIssueCreateResult:
    created: bool
    url: str | None
    message: str


class GitHubService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(
            self.settings.github_token
            and self.settings.github_repo_owner
            and self.settings.github_repo_name
        )

    async def create_issue(self, issue: IssueDraft) -> GitHubIssueCreateResult:
        if not self.is_configured():
            return GitHubIssueCreateResult(
                created=False,
                url=None,
                message=(
                    "Issue approved locally. Set GITHUB_TOKEN, GITHUB_REPO_OWNER, "
                    "and GITHUB_REPO_NAME to create it on GitHub."
                ),
            )

        owner = self.settings.github_repo_owner
        repo = self.settings.github_repo_name
        assert owner is not None
        assert repo is not None

        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        payload = {
            "title": issue.title,
            "body": issue.body_markdown,
            "labels": _github_labels(issue.priority_label),
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.settings.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise GitHubIssueCreationError(
                f"GitHub issue creation failed with {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise GitHubIssueCreationError(f"GitHub issue creation failed: {exc}") from exc

        data = response.json()
        html_url = data.get("html_url")
        if not isinstance(html_url, str):
            raise GitHubIssueCreationError("GitHub did not return an issue URL.")

        return GitHubIssueCreateResult(
            created=True,
            url=html_url,
            message="Issue approved and created on GitHub.",
        )


def _github_labels(priority_label: str) -> list[str]:
    labels = ["bugsignal-ai", priority_label]
    if priority_label.startswith("P0"):
        labels.append("critical")
    elif priority_label.startswith("P1"):
        labels.append("high-priority")
    return labels
