from radar.documents import (
    document_section_text,
    parse_document_outline,
    render_markdown,
)


SAMPLE = """# 测试文档

## 1. 一页结论

**文档**是主体，图谱只导航。

| 层次 | 用途 |
|---|---|
| 文档 | 完整论证 |

### 1.1 边界

AI 会话不是外部事实证据。

## 2. 实施路线

> 先做小型 PoC。
"""

MERMAID_SAMPLE = """## 1. 流程

```mermaid
flowchart TD
    A[输入] --> B[核验]
```
"""


def test_document_outline_and_section_extraction_are_stable() -> None:
    outline = parse_document_outline(SAMPLE)
    assert [item.anchor for item in outline] == [
        "section-d37ff805c9",
        "section-1",
        "section-1-1",
        "section-2",
    ]
    section, text = document_section_text(SAMPLE, "section-1")
    assert section.title == "1. 一页结论"
    assert "图谱只导航" in text
    assert "2. 实施路线" not in text


def test_document_markdown_renders_as_readable_html() -> None:
    rendered = str(render_markdown(SAMPLE))
    assert 'id="section-1"' in rendered
    assert "<strong>文档</strong>" in rendered
    assert "<table>" in rendered
    assert "<blockquote>" in rendered


def test_mermaid_block_renders_as_progressive_diagram_container() -> None:
    rendered = str(render_markdown(MERMAID_SAMPLE))
    assert 'data-mermaid-diagram' in rendered
    assert 'data-mermaid-canvas' in rendered
    assert "查看 Mermaid 源码" in rendered
    assert "flowchart TD" in rendered
    assert "A[输入] --&gt; B[核验]" in rendered
