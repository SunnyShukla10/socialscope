def collection_terminal_status(
    total_posts: int,
    errors: list[str],
    successful_platforms: int | None = None,
) -> str:
    if errors and (
        successful_platforms == 0
        or (successful_platforms is None and total_posts == 0)
    ):
        return "failed"
    if errors:
        return "completed_with_errors"
    return "completed"
