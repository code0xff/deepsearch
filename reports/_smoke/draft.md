## Abstract

This report exercises the Deepsearch rendering pipeline. It verifies that headings, paragraphs, footnote citations, code blocks, math, and the References section all render correctly from `draft.md` into the published HTML artefact[^s01].

## Introduction

The Deepsearch harness converts a Markdown draft and a JSON-lines source file into a single self-contained `index.html`. The canonical paper layout and monotone palette are defined in `assets/style.css`, and the template into which the body is injected lives at `assets/report-template.html`[^s01].

## A brief inline example

Inline code like `render_report.py` should pick up the monospace face. A fenced block:

```python
def greet(name: str) -> str:
    return f"hello, {name}"
```

Inline math such as $E = mc^2$ and a display equation

$$\int_0^1 x^2\,dx = \tfrac{1}{3}$$

should both render through KaTeX after page load[^s02].

## Limitations

This is a fixture, not a real research artefact. It exists only to confirm the rendering toolchain. Any real report must collect sources before drafting, per the protocol in `CLAUDE.md`.
