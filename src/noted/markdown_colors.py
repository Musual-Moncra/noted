import re
from typing import Optional
from textual.content import Content, Span
from textual.style import Style as TStyle
from textual.color import Color as TColor
from textual.widgets._markdown import MarkdownBlock
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import (
    Markdown as RMarkdown,
    MarkdownContext,
    Link as RLink,
    UnknownElement as RUnknownElement,
)
from rich.style import Style as RStyle
from rich.segment import Segment

# Tokyo Night / Rich Modern palette mapping for named colors
COLOR_MAP: dict[str, str] = {
    "red": "#f7768e",
    "green": "#9ece6a",
    "yellow": "#e0af68",
    "blue": "#7aa2f7",
    "purple": "#bb9af7",
    "magenta": "#bb9af7",
    "cyan": "#7dcfff",
    "orange": "#ff9e64",
    "pink": "#f5c2e7",
    "white": "#c0caf5",
    "gray": "#565f89",
    "grey": "#565f89",
}

def parse_html_color(html_tag: str) -> Optional[str]:
    """Extract hex color code or mapped color name from HTML tag."""
    # Match <span style="color: ..."> or style='color: ...'
    m = re.search(r'style=[\"\'][^\"\']*color:\s*([^;\"\'\s]+)', html_tag, re.IGNORECASE)
    if m:
        c = m.group(1).strip()
        return COLOR_MAP.get(c.lower(), c)

    # Match <font color="...">
    m = re.search(r'color=[\"\']([^\"\']+)[\"\']', html_tag, re.IGNORECASE)
    if m:
        c = m.group(1).strip()
        return COLOR_MAP.get(c.lower(), c)

    # Match direct tag like <red>, <blue>, <green>, etc.
    m = re.match(r"^<([a-zA-Z]+)>$", html_tag)
    if m:
        tag_name = m.group(1).lower()
        if tag_name in COLOR_MAP:
            return COLOR_MAP[tag_name]

    return None

def is_html_color_close(html_tag: str) -> bool:
    """Check if tag is a closing tag for a color span, font, or custom tag."""
    m = re.match(r"^</([a-zA-Z]+)>$", html_tag)
    if m:
        tag_name = m.group(1).lower()
        return tag_name in ("span", "font") or tag_name in COLOR_MAP
    return False

# ---------------------------------------------------------------------------
# Textual MarkdownBlock Patch
# ---------------------------------------------------------------------------

_orig_textual_token_to_content = MarkdownBlock._token_to_content

def _textual_token_to_content(self: MarkdownBlock, token) -> Content:
    if token.children is None:
        return Content("")

    tokens: list[str] = []
    spans: list[Span] = []
    style_stack: list[tuple[TStyle | str, int]] = []
    position: int = 0

    def add_content(text: str) -> None:
        nonlocal position
        tokens.append(text)
        position += len(text)

    def add_style(style: TStyle | str) -> None:
        style_stack.append((style, position))

    def close_tag() -> None:
        if style_stack:
            style, start = style_stack.pop()
            spans.append(Span(start, position, style))

    for child in token.children:
        child_type = child.type
        if child_type == "text":
            add_content(re.sub(r"\s+", " ", child.content))
        elif child_type == "hardbreak":
            add_content("\n")
        elif child_type == "softbreak":
            add_content(" ")
        elif child_type == "code_inline":
            add_style(".code_inline")
            add_content(child.content)
            close_tag()
        elif child_type == "em_open":
            add_style(".em")
        elif child_type == "strong_open":
            add_style(".strong")
        elif child_type == "s_open":
            add_style(".s")
        elif child_type == "link_open":
            href = child.attrs.get("href", "")
            action = f"link({href!r})"
            add_style(TStyle.from_meta({"@click": action}))
        elif child_type == "image":
            href = child.attrs.get("src", "")
            alt = child.attrs.get("alt", "")
            action = f"link({href!r})"
            add_style(TStyle.from_meta({"@click": action}))
            add_content("🖼  ")
            if alt:
                add_content(f"({alt})")
            if child.children is not None:
                for grandchild in child.children:
                    add_content(grandchild.content)
            close_tag()
        elif child_type == "html_inline":
            tag = child.content.strip()
            color = parse_html_color(tag)
            if color:
                try:
                    c = TColor.parse(color)
                    add_style(TStyle(foreground=c))
                except Exception:
                    pass
            elif is_html_color_close(tag):
                close_tag()
        elif child_type.endswith("_close"):
            close_tag()

    return Content("".join(tokens), spans=spans)

# ---------------------------------------------------------------------------
# Rich Markdown Patch
# ---------------------------------------------------------------------------

_orig_rich_console = RMarkdown.__rich_console__

def _rich_markdown_console(
    self: RMarkdown, console: Console, options: ConsoleOptions
) -> RenderResult:
    style = console.get_style(self.style, default="none")
    options = options.update(height=None)
    context = MarkdownContext(
        console,
        options,
        style,
        inline_code_lexer=self.inline_code_lexer,
        inline_code_theme=self.inline_code_theme,
    )
    tokens = self.parsed
    inline_style_tags = self.inlines
    new_line = False
    _new_line_segment = Segment.line()

    for token in self._flatten_tokens(tokens):
        node_type = token.type
        tag = token.tag

        entering = token.nesting == 1
        exiting = token.nesting == -1
        self_closing = token.nesting == 0

        if node_type == "text":
            context.on_text(token.content, node_type)
        elif node_type == "hardbreak":
            context.on_text("\n", node_type)
        elif node_type == "softbreak":
            context.on_text(" ", node_type)
        elif node_type == "link_open":
            href = str(token.attrs.get("href", ""))
            if self.hyperlinks:
                link_style = console.get_style("markdown.link_url", default="none")
                link_style += RStyle(link=href)
                context.enter_style(link_style)
            else:
                context.stack.push(RLink.create(self, token))
        elif node_type == "html_inline":
            c = parse_html_color(token.content)
            if c:
                try:
                    context.enter_style(RStyle(color=c))
                except Exception:
                    pass
            elif is_html_color_close(token.content):
                try:
                    context.leave_style()
                except Exception:
                    pass
            elif token.content == "<kbd>":
                kbd_style = console.get_style("markdown.kbd", default="bold")
                context.enter_style(kbd_style)
            elif token.content == "</kbd>":
                context.leave_style()
        elif node_type == "link_close":
            if self.hyperlinks:
                context.leave_style()
            else:
                element = context.stack.pop()
                assert isinstance(element, RLink)
                link_style = console.get_style("markdown.link", default="none")
                context.enter_style(link_style)
                context.on_text(element.text.plain, node_type)
                context.leave_style()
                context.on_text(" (", node_type)
                link_url_style = console.get_style("markdown.link_url", default="none")
                context.enter_style(link_url_style)
                context.on_text(element.href, node_type)
                context.leave_style()
                context.on_text(")", node_type)
        elif (
            tag in inline_style_tags
            and node_type != "fence"
            and node_type != "code_block"
        ):
            if entering:
                context.enter_style(f"markdown.{tag}")
            elif exiting:
                context.leave_style()
            else:
                context.enter_style(f"markdown.{tag}")
                if token.content:
                    context.on_text(token.content, node_type)
                context.leave_style()
        else:
            element_class = self.elements.get(token.type) or RUnknownElement
            element = element_class.create(self, token)

            if entering or self_closing:
                context.stack.push(element)
                element.on_enter(context)

            if exiting:
                element = context.stack.pop()
                should_render = not context.stack or (
                    context.stack and context.stack.top.on_child_close(context, element)
                )
                if should_render:
                    if new_line:
                        yield _new_line_segment
                    yield from console.render(element, context.options)
            elif self_closing:
                context.stack.pop()
                text = token.content
                if text is not None:
                    element.on_text(context, text)

                should_render = not context.stack or (
                    context.stack and context.stack.top.on_child_close(context, element)
                )
                if should_render:
                    if new_line and node_type != "inline":
                        yield _new_line_segment
                    yield from console.render(element, context.options)

            if exiting or self_closing:
                element.on_leave(context)
                new_line = element.new_line

def apply_markdown_color_patches() -> None:
    """Applies color rendering patches to Textual and Rich markdown components."""
    MarkdownBlock._token_to_content = _textual_token_to_content
    RMarkdown.__rich_console__ = _rich_markdown_console

# Apply automatically on import
apply_markdown_color_patches()
