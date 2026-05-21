import base64
from pathlib import Path

import desktop_mineru


def test_embed_images_as_data_uris_rewrites_relative_markdown_images(tmp_path: Path):
    md_dir = tmp_path / "doc" / "txt"
    image_dir = md_dir / "images"
    image_dir.mkdir(parents=True)
    image_bytes = b"\xff\xd8\xff\xe0fake-jpeg"
    image_path = image_dir / "figure.jpg"
    image_path.write_bytes(image_bytes)
    md_path = md_dir / "paper.md"
    md_path.write_text("before\n![](images/figure.jpg)\nafter\n", encoding="utf-8")

    changed = desktop_mineru.embed_images_as_data_uris(md_path)

    expected = base64.b64encode(image_bytes).decode("ascii")
    assert changed is True
    assert md_path.read_text(encoding="utf-8-sig") == f"before\n![](data:image/jpeg;base64,{expected})\nafter\n"
    assert md_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_normalize_markdown_encoding_adds_bom_without_changing_text(tmp_path: Path):
    md_path = tmp_path / "paper.md"
    md_path.write_text("中文\n# title\n", encoding="utf-8")

    desktop_mineru.normalize_markdown_encoding(md_path)

    assert md_path.read_text(encoding="utf-8-sig") == "中文\n# title\n"
    assert md_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_collect_supported_files_recursively(tmp_path: Path):
    folder = tmp_path / "batch"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    pdf_path = folder / "a.pdf"
    image_path = nested / "b.png"
    ignored_path = nested / "notes.txt"
    pdf_path.write_bytes(b"%PDF")
    image_path.write_bytes(b"png")
    ignored_path.write_text("ignore", encoding="utf-8")

    paths = desktop_mineru.collect_supported_files(folder)

    assert paths == [pdf_path, image_path]


def test_summarize_input_paths_for_single_and_batch(tmp_path: Path):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"

    assert desktop_mineru.summarize_input_paths([]) == ""
    assert desktop_mineru.summarize_input_paths([first]) == str(first)
    assert desktop_mineru.summarize_input_paths([first, second]) == "已选择 2 个文件"


def test_keep_only_markdown_outputs_removes_extra_files_and_empty_dirs(tmp_path: Path):
    output_dir = tmp_path / "output"
    txt_dir = output_dir / "doc" / "txt"
    image_dir = txt_dir / "images"
    image_dir.mkdir(parents=True)
    md_path = txt_dir / "doc.md"
    md_path.write_text("# doc\n", encoding="utf-8")
    (txt_dir / "doc_model.json").write_text("{}", encoding="utf-8")
    (txt_dir / "doc_origin.pdf").write_bytes(b"%PDF")
    (image_dir / "figure.jpg").write_bytes(b"jpg")

    kept = desktop_mineru.keep_only_markdown_outputs(output_dir)

    assert kept == [md_path]
    assert md_path.exists()
    assert not (txt_dir / "doc_model.json").exists()
    assert not (txt_dir / "doc_origin.pdf").exists()
    assert not image_dir.exists()


def test_extract_progress_from_mineru_log_lines():
    first = desktop_mineru.extract_progress("Pipeline processing window batch 3/16: 3/16 pages")
    second = desktop_mineru.extract_progress("Completed batch 1/1 | Processed 16/16 pages")

    assert first == (3, 16)
    assert second == (16, 16)
