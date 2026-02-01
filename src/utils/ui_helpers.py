"""UI helper functions."""

from textual.widgets import DataTable


def update_table_preserving_scroll(table: DataTable, populate_function):
    """
    Clear a DataTable and repopulate it while attempting to preserve the scroll position
    and cursor position.
    """
    # Store current state
    current_row = table.cursor_row
    scroll_y = table.scroll_y

    # Repopulate
    table.clear()
    populate_function(table)

    # Restore cursor position
    if current_row is not None and table.is_valid_row_index(current_row):
        table.move_cursor(row=current_row)

    # Restore scroll position after refresh
    def restore_scroll():
        if scroll_y is not None:
            table.scroll_to(y=scroll_y, animate=False)

    table.call_after_refresh(restore_scroll)


def bytes_to_human_readable(num: float, suffix: str = "B") -> str:
    """Convert bytes to a human-readable format (e.g., KB, MB, GB)."""
    if num is None:
        return "N/A"
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Y{suffix}"
