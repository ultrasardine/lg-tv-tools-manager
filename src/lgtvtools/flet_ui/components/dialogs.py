"""Dialog components for the Flet UI."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from lgtvtools.flet_ui.theme import AppColors


async def show_error_dialog(
    page: ft.Page,
    title: str,
    message: str,
) -> None:
    """Show an error dialog.

    Args:
        page: The Flet page.
        title: Dialog title.
        message: Error message to display.
    """
    def close_dialog(e: ft.ControlEvent) -> None:
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        title=ft.Text(title, color=AppColors.ERROR),
        content=ft.Text(message, color=AppColors.TEXT_PRIMARY),
        actions=[
            ft.TextButton("OK", on_click=close_dialog),
        ],
        bgcolor=AppColors.SURFACE,
        open=True,
    )
    page.overlay.append(dialog)
    page.update()


async def show_info_dialog(
    page: ft.Page,
    title: str,
    message: str,
) -> None:
    """Show an information dialog.

    Args:
        page: The Flet page.
        title: Dialog title.
        message: Message to display.
    """
    def close_dialog(e: ft.ControlEvent) -> None:
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        title=ft.Text(title, color=AppColors.TEXT_PRIMARY),
        content=ft.Text(message, color=AppColors.TEXT_PRIMARY),
        actions=[
            ft.TextButton("OK", on_click=close_dialog),
        ],
        bgcolor=AppColors.SURFACE,
        open=True,
    )
    page.overlay.append(dialog)
    page.update()


async def show_url_input_dialog(
    page: ft.Page,
    title: str = "Cast URL",
    hint: str = "Enter URL to cast",
    on_submit: Callable[[str], None] | None = None,
) -> str | None:
    """Show a dialog for URL input.

    Args:
        page: The Flet page.
        title: Dialog title.
        hint: Placeholder text for the input field.
        on_submit: Callback with the entered URL.

    Returns:
        The entered URL or None if cancelled.
    """
    url_field = ft.TextField(
        hint_text=hint,
        autofocus=True,
        bgcolor=AppColors.SURFACE_VARIANT,
        border_color=AppColors.BORDER,
        focused_border_color=AppColors.BORDER_FOCUS,
        cursor_color=AppColors.PRIMARY,
        text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
        border_radius=8,
        expand=True,
    )

    result: str | None = None

    def close_dialog() -> None:
        dialog.open = False
        page.update()

    def on_cancel(e: ft.ControlEvent) -> None:
        close_dialog()

    def on_ok(e: ft.ControlEvent) -> None:
        nonlocal result
        url = url_field.value or ""
        if url.strip():
            # Normalize URL
            if not url.startswith(("http://", "https://")):
                url = "http://" + url
            result = url
            if on_submit:
                import inspect

                ret = on_submit(url)
                if inspect.isawaitable(ret):

                    async def _run_awaitable() -> None:
                        await ret

                    page.run_task(_run_awaitable)
        close_dialog()

    def on_submit_field(e: ft.ControlEvent) -> None:
        on_ok(e)

    url_field.on_submit = on_submit_field

    dialog = ft.AlertDialog(
        title=ft.Text(title, color=AppColors.TEXT_PRIMARY),
        content=ft.Container(
            content=url_field,
            width=400,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=on_cancel),
            ft.ElevatedButton(
                "Cast",
                on_click=on_ok,
                bgcolor=AppColors.PRIMARY,
                color=AppColors.TEXT_PRIMARY,
            ),
        ],
        bgcolor=AppColors.SURFACE,
        open=True,
    )

    page.overlay.append(dialog)
    page.update()
    return result


async def show_confirmation_dialog(
    page: ft.Page,
    title: str,
    message: str,
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    on_confirm: Callable[[], None] | None = None,
) -> bool:
    """Show a confirmation dialog.

    Args:
        page: The Flet page.
        title: Dialog title.
        message: Confirmation message.
        confirm_text: Text for confirm button.
        cancel_text: Text for cancel button.
        on_confirm: Callback when confirmed.

    Returns:
        True if confirmed, False if cancelled.
    """
    confirmed = False

    def close_dialog() -> None:
        dialog.open = False
        page.update()

    def on_cancel(e: ft.ControlEvent) -> None:
        close_dialog()

    def on_ok(e: ft.ControlEvent) -> None:
        nonlocal confirmed
        confirmed = True
        if on_confirm:
            on_confirm()
        close_dialog()

    dialog = ft.AlertDialog(
        title=ft.Text(title, color=AppColors.TEXT_PRIMARY),
        content=ft.Text(message, color=AppColors.TEXT_PRIMARY),
        actions=[
            ft.TextButton(cancel_text, on_click=on_cancel),
            ft.ElevatedButton(
                confirm_text,
                on_click=on_ok,
                bgcolor=AppColors.PRIMARY,
                color=AppColors.TEXT_PRIMARY,
            ),
        ],
        bgcolor=AppColors.SURFACE,
        open=True,
    )

    page.overlay.append(dialog)
    page.update()
    return confirmed
