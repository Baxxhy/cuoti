"""Keep complete formula source in display summaries and recover old auto-titles."""


def academic_summary(value: str, limit: int) -> str:
    return value if "$" in value or "\\" in value else value[:limit]
