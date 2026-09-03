"""Registers all agent-callable tools with the ToolRegistry.

Permission rules gate high-impact operations. The tool layer is generic:
there is no youtube.py, fiverr.py or gmail.py — the agent composes these
primitives.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from luna.automation import browser as browser_mod
from luna.automation import desktop as desktop_mod
from luna.automation import filesystem as fs
from luna.automation.terminal import Terminal
from luna.core.tools import ToolRegistry


def register_core_tools(registry: ToolRegistry, workspace: Path | None = None) -> None:
    scope = workspace or Path.home()

    registry.add(
        "list_directory",
        "List files and folders in a directory.",
        lambda path=".": fs.list_directory(path, scope=scope),
        {"path": {"type": "string", "description": "Directory path.", "required": False}},
        category="filesystem",
    )
    registry.add(
        "read_file",
        "Read a text file from disk.",
        lambda path: fs.read_file(path, scope=scope),
        {"path": {"type": "string", "description": "File path.", "required": True}},
        permission="read_file",
        category="filesystem",
    )
    registry.add(
        "create_file",
        "Create or overwrite a text file.",
        lambda path, content: fs.write_file(path, content, scope=scope),
        {
            "path": {"type": "string", "description": "File path.", "required": True},
            "content": {"type": "string", "description": "File content.", "required": True},
        },
        permission="create_file",
        category="filesystem",
    )
    registry.add(
        "modify_file",
        "Append content to an existing file.",
        lambda path, content: fs.write_file(path, content, append=True, scope=scope),
        {
            "path": {"type": "string", "description": "File path.", "required": True},
            "content": {"type": "string", "description": "Content to append.", "required": True},
        },
        permission="modify_file",
        category="filesystem",
    )
    registry.add(
        "move_file",
        "Move or rename a file.",
        lambda source, destination, overwrite=False: fs.move_file(
            source, destination, overwrite=overwrite, scope=scope
        ),
        {
            "source": {"type": "string", "description": "Source path.", "required": True},
            "destination": {"type": "string", "description": "Destination path.", "required": True},
            "overwrite": {"type": "boolean", "description": "Overwrite destination.", "required": False},
        },
        permission="move_file",
        category="filesystem",
    )
    registry.add(
        "delete_file",
        "Delete a file. High-impact: gated by permission.",
        lambda path: fs.delete_file(path, scope=scope),
        {"path": {"type": "string", "description": "File path.", "required": True}},
        permission="delete_file",
        category="filesystem",
    )
    registry.add(
        "create_directory",
        "Create a directory.",
        lambda path: fs.create_directory(path, scope=scope),
        {"path": {"type": "string", "description": "Directory path.", "required": True}},
        category="filesystem",
    )
    registry.add(
        "search_files",
        "Search for files by regex name pattern.",
        lambda pattern, directory=".": fs.search_files(pattern, directory, scope=scope),
        {
            "pattern": {"type": "string", "description": "Regex pattern.", "required": True},
            "directory": {"type": "string", "description": "Directory.", "required": False},
        },
        category="filesystem",
    )
    registry.add(
        "organize_downloads",
        "Group loose files into folders by type (images, documents...).",
        lambda directory: fs.organize_downloads(directory, scope=scope),
        {"directory": {"type": "string", "description": "Directory to organize.", "required": True}},
        permission="move_file",
        category="filesystem",
    )
    registry.add(
        "run_command",
        "Run a shell command, capturing stdout/stderr and exit status. Logged and permission-gated.",
        lambda command, timeout=60: Terminal().run(command, timeout=timeout),
        {
            "command": {"type": "string", "description": "Command to execute in the system shell.", "required": True},
            "timeout": {"type": "number", "description": "Timeout in seconds.", "required": False},
        },
        permission="run_command",
        category="terminal",
    )


def register_browser_tools(registry: ToolRegistry, browser: browser_mod.PlaywrightBrowser) -> None:
    registry.add(
        "browser_navigate",
        "Open a URL in the browser. Example: browser_navigate('https://www.youtube.com').",
        lambda url: browser.navigate(url),
        {"url": {"type": "string", "description": "URL or hostname.", "required": True}},
        permission="browser_navigate",
        category="browser",
    )
    registry.add(
        "browser_open_tab",
        "Open a new browser tab.",
        lambda url=None: browser.open_tab(url),
        {"url": {"type": "string", "description": "Optional URL.", "required": False}},
        permission="browser_navigate",
        category="browser",
    )
    registry.add(
        "browser_list_tabs",
        "List open browser tabs.",
        lambda: browser.list_tabs(),
        category="browser",
    )
    registry.add(
        "browser_switch_tab",
        "Switch to another open tab by index.",
        lambda index: browser.switch_tab(int(index)),
        {"index": {"type": "integer", "description": "Tab index.", "required": True}},
        category="browser",
    )
    registry.add(
        "browser_close_tab",
        "Close the current (or indexed) tab.",
        lambda index=None: browser.close_tab(int(index) if index is not None else None),
        {"index": {"type": "integer", "description": "Tab index (optional).", "required": False}},
        category="browser",
    )
    registry.add(
        "browser_read_page",
        "Read the visible text of the current page. Use after navigation to verify state.",
        lambda max_chars=8000: browser.read_page(max_chars=max_chars),
        {"max_chars": {"type": "integer", "description": "Max characters.", "required": False}},
        category="browser",
    )
    registry.add(
        "browser_find",
        "Find elements on the page by CSS selector, role, name or placeholder.",
        lambda **kwargs: browser.find(**kwargs),
        {
            "selector": {"type": "string", "description": "CSS selector.", "required": False},
            "role": {"type": "string", "description": "ARIA role (e.g. searchbox, button, link).", "required": False},
            "name": {"type": "string", "description": "Text to match.", "required": False},
            "placeholder": {"type": "string", "description": "Placeholder text.", "required": False},
        },
        category="browser",
    )
    registry.add(
        "browser_click",
        "Click an element by selector or role+name.",
        lambda **kwargs: browser.click(**kwargs),
        {
            "selector": {"type": "string", "description": "CSS selector.", "required": False},
            "role": {"type": "string", "description": "ARIA role.", "required": False},
            "name": {"type": "string", "description": "Element text.", "required": False},
            "index": {"type": "integer", "description": "Match index.", "required": False},
        },
        permission="browser_click",
        category="browser",
    )
    registry.add(
        "browser_type",
        "Type text into a field by selector, role or placeholder.",
        lambda text, **kwargs: browser.type_text(text, **kwargs),
        {
            "text": {"type": "string", "description": "Text to type.", "required": True},
            "selector": {"type": "string", "description": "CSS selector.", "required": False},
            "role": {"type": "string", "description": "ARIA role.", "required": False},
            "placeholder": {"type": "string", "description": "Placeholder text.", "required": False},
            "clear": {"type": "boolean", "description": "Clear field first.", "required": False},
            "press_enter": {"type": "boolean", "description": "Press Enter after typing.", "required": False},
        },
        permission="browser_type",
        category="browser",
    )
    registry.add(
        "browser_press",
        "Press a keyboard key (Enter, Escape, Tab...).",
        lambda key: browser.press(key),
        {"key": {"type": "string", "description": "Key name.", "required": True}},
        category="browser",
    )
    registry.add(
        "browser_scroll",
        "Scroll the page.",
        lambda amount=600: browser.scroll(int(amount)),
        {"amount": {"type": "integer", "description": "Scroll amount.", "required": False}},
        category="browser",
    )
    registry.add(
        "browser_wait",
        "Wait for page state: CSS selector visibility, URL contains text, or seconds.",
        lambda **kwargs: browser.wait(**kwargs),
        {
            "selector": {"type": "string", "description": "Selector to wait for.", "required": False},
            "url_contains": {"type": "string", "description": "URL substring.", "required": False},
            "seconds": {"type": "number", "description": "Wait seconds.", "required": False},
        },
        category="browser",
    )
    registry.add(
        "browser_screenshot",
        "Capture the current page to a PNG file.",
        lambda path: browser.screenshot(os.path.expanduser(path)),
        {"path": {"type": "string", "description": "Output PNG path.", "required": True}},
        permission="screenshot",
        category="browser",
    )
    registry.add(
        "browser_extract",
        "Extract matching element texts from the page.",
        lambda **kwargs: browser.extract(**kwargs),
        {
            "selector": {"type": "string", "description": "CSS selector.", "required": False},
            "role": {"type": "string", "description": "ARIA role.", "required": False},
            "name": {"type": "string", "description": "Text to match.", "required": False},
            "max_items": {"type": "integer", "description": "Max items.", "required": False},
        },
        category="browser",
    )


def register_desktop_tools(registry: ToolRegistry, desktop: desktop_mod.DesktopAutomation | None, cache_dir: Path) -> None:
    if desktop is None:
        return

    registry.add(
        "desktop_list_windows",
        "List open application windows.",
        lambda: [w.to_dict() for w in desktop.list_windows()],
        category="desktop",
    )
    registry.add(
        "desktop_launch_app",
        "Open a desktop application by name.",
        lambda name: desktop.open_application(name),
        {"name": {"type": "string", "description": "Application name.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_focus_window",
        "Bring a window to the foreground by title.",
        lambda title: desktop.focus_window(title).to_dict(),
        {"title": {"type": "string", "description": "Window title.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_minimize_window",
        "Minimize a window by title.",
        lambda title: {"ok": desktop.minimize_window(title)},
        {"title": {"type": "string", "description": "Window title.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_read_accessibility",
        "Read the accessibility tree of the focused window.",
        lambda: desktop.read_accessible_ui().to_dict(),
        category="desktop",
    )
    registry.add(
        "desktop_read_screen",
        "Read the accessible text of the focused window (structured UI info).",
        lambda: desktop.read_accessible_ui().text,
        category="desktop",
    )
    registry.add(
        "desktop_screenshot",
        "Capture the desktop screen to a PNG.",
        lambda path: desktop.screenshot(os.path.expanduser(path)),
        {"path": {"type": "string", "description": "Output PNG path.", "required": True}},
        permission="screenshot",
        category="desktop",
    )
    registry.add(
        "desktop_type",
        "Type text into the focused control.",
        lambda text: desktop.type_text(text),
        {"text": {"type": "string", "description": "Text to type.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_press_key",
        "Press a keyboard key.",
        lambda key: desktop.press_key(key),
        {"key": {"type": "string", "description": "Key name.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_hotkey",
        "Press a hotkey (e.g. 'ctrl+s').",
        lambda keys: desktop.hotkey(keys),
        {"keys": {"type": "string", "description": "Hotkey string.", "required": True}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_copy",
        "Copy selected text to the clipboard and return it.",
        lambda: desktop.copy(),
        category="desktop",
    )
    registry.add(
        "desktop_paste",
        "Paste clipboard contents (optional text to set first).",
        lambda text=None: desktop.paste(text),
        {"text": {"type": "string", "description": "Text to paste.", "required": False}},
        permission="desktop_control",
        category="desktop",
    )
    registry.add(
        "desktop_click",
        "Click at screen coordinates (fallback when accessibility is unavailable).",
        lambda x, y: desktop.click(int(x), int(y)),
        {
            "x": {"type": "integer", "description": "Screen x.", "required": True},
            "y": {"type": "integer", "description": "Screen y.", "required": True},
        },
        permission="desktop_control",
        category="desktop",
    )
