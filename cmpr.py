import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Tuple

import typer

DOCS_ROOT = os.getenv("DOCS_ROOT", "docs")
TMP_DOCS_PATH = os.getenv("TMP_DOCS_PATH", "non-git/translations")


non_translated_sections = (
    f"reference{os.sep}",
    "release-notes.md",
    "fastapi-people.md",
    "external-links.md",
    "newsletter.md",
    "management-tasks.md",
    "management.md",
    "contributing.md",
)


class Retry(Exception):
    pass


class CompareError(Exception):
    pass


# ===================================================================================
# Multiline code blocks

LANG_RE = re.compile(r"^```([\w-]*)", re.MULTILINE)


def get_code_block_lang(line: str) -> str:
    match = LANG_RE.match(line)
    if match:
        return match.group(1)
    return ""


def extract_multiline_blocks(text: str) -> List[Tuple[str, int, str]]:
    lines = text.splitlines()
    blocks = []

    in_code_block3 = False
    in_code_block4 = False
    current_block_lang = ""
    current_block_start_line = -1
    current_block_lines = []

    for line_no, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        # --- Detect opening fence ---
        if not (in_code_block3 or in_code_block4):
            if stripped.startswith("```"):
                current_block_start_line = line_no
                count = len(stripped) - len(stripped.lstrip("`"))
                if count == 3:
                    in_code_block3 = True
                    current_block_lang = get_code_block_lang(stripped)
                    current_block_lines = [line]
                    continue
                elif count >= 4:
                    in_code_block4 = True
                    current_block_lang = get_code_block_lang(stripped)
                    current_block_lines = [line]
                    continue

        # --- Detect closing fence ---
        elif in_code_block3:
            if stripped.startswith("```"):
                count = len(stripped) - len(stripped.lstrip("`"))
                if count == 3:
                    current_block_lines.append(line)
                    blocks.append(
                        (
                            current_block_lang,
                            current_block_start_line,
                            "\n".join(current_block_lines),
                        )
                    )
                    in_code_block3 = False
                    current_block_lang = ""
                    current_block_start_line = -1
                    continue
            current_block_lines.append(line)

        elif in_code_block4:
            if stripped.startswith("````"):
                count = len(stripped) - len(stripped.lstrip("`"))
                if count >= 4:
                    current_block_lines.append(line)
                    blocks.append(
                        (
                            current_block_lang,
                            current_block_start_line,
                            "\n".join(current_block_lines),
                        )
                    )
                    in_code_block4 = False
                    current_block_lang = ""
                    current_block_start_line = -1
                    continue
            current_block_lines.append(line)

    return blocks


def replace_blocks(source_text: str, target_text: str) -> str:
    source_blocks = extract_multiline_blocks(source_text)
    target_blocks = extract_multiline_blocks(target_text)

    if len(source_blocks) != len(target_blocks):
        raise CompareError(
            f"Number of code blocks differs: "
            f"{len(source_blocks)} in source vs {len(target_blocks)} in target."
        )

    for i, ((src_lang, *_), (tgt_lang, tgt_line_no, *_)) in enumerate(
        zip(source_blocks, target_blocks), 1
    ):
        if src_lang != tgt_lang:
            raise CompareError(
                f"Type mismatch in block #{i} (line {tgt_line_no}): "
                f"'{src_lang or '(no lang)'}' vs '{tgt_lang or '(no lang)'}'"
            )

    # Sequentially replace each block in target with the one from source
    result = target_text
    for (*_, src_block), (*_, tgt_block) in zip(source_blocks, target_blocks):
        result = result.replace(tgt_block, src_block, 1)

    return result


# ===================================================================================
# Headers and permalinks

header_with_permalink_pattern = re.compile(r"^(#{1,6}) (.+?)(\s*\{\s*#.*\s*\})?\s*$")


def extract_headers_and_permalinks(lines: list[str]) -> List[Tuple[str, int, str]]:
    headers = []
    in_code_block3 = False
    in_code_block4 = False

    for line_no, line in enumerate(lines, start=1):
        if not (in_code_block3 or in_code_block4):
            if line.startswith("```"):
                count = len(line) - len(line.lstrip("`"))
                if count == 3:
                    in_code_block3 = True
                    continue
                elif count >= 4:
                    in_code_block4 = True
                    continue

            header_match = header_with_permalink_pattern.match(line)
            if header_match:
                hashes, _title, permalink = header_match.groups()
                headers.append((hashes, line_no, permalink))

        elif in_code_block3:
            if line.startswith("```"):
                count = len(line) - len(line.lstrip("`"))
                if count == 3:
                    in_code_block3 = False
                    continue

        elif in_code_block4:
            if line.startswith("````"):
                count = len(line) - len(line.lstrip("`"))
                if count >= 4:
                    in_code_block4 = False
                    continue

    return headers


def replace_headers_and_permalinks(source_text: str, target_text: str) -> str:
    target_lines = target_text.splitlines()

    source_headers = extract_headers_and_permalinks(source_text.splitlines())
    target_headers = extract_headers_and_permalinks(target_lines)

    if len(source_headers) != len(target_headers):
        raise CompareError(
            f"Number of headers differs: "
            f"{len(source_headers)} in source vs {len(target_headers)} in target."
        )

    for i, ((src_hashes, *_), (tgt_hashes, tgt_line_no, *_)) in enumerate(
        zip(source_headers, target_headers), 1
    ):
        if src_hashes != tgt_hashes:
            raise CompareError(
                f"Header level mismatch in #{i} (line {tgt_line_no}): "
                "'{src_hashes}' vs '{tgt_hashes}'"
            )

    # Sequentially replace each header permalink in target with the one from source
    for src_header, tgt_header in zip(source_headers, target_headers):
        src_permalink = src_header[2]
        tgt_line_no = tgt_header[1] - 1  # Convert from 1-based to 0-based
        header_match = header_with_permalink_pattern.match(target_lines[tgt_line_no])
        if header_match:
            hashes, title, _ = header_match.groups()
            target_lines[tgt_line_no] = (
                f"{hashes} {title}{src_permalink or ' (ERROR - MISSING PERMALINK)'}"
            )

    target_lines.append("")  # To preserve the empty line in the end of the file
    return "\n".join(target_lines)


# ===================================================================================
# Links

MARKDOWN_LINK_RE = re.compile(
    r"(?<!\!)"  # not an image ![...]
    r"\[(?P<text>.*?)\]"  # link text (non-greedy)
    r"\("
    r"(?P<url>\S+?)"  # url (no spaces, non-greedy)
    r'(?:\s+["\'](?P<title>.*?)["\'])?'  # optional title in "" or ''
    r"\)"
)


def extract_markdown_links(lines: str) -> Dict[str, List[Tuple[str, int]]]:
    links = []
    for line_no, line in enumerate(lines, start=1):
        for m in MARKDOWN_LINK_RE.finditer(line):
            url = m.group("url")
            links.append((url, line_no))
    return links


def replace_markdown_links(source_text: str, target_text: str, lang: str) -> str:
    target_lines = target_text.splitlines()
    source_links = extract_markdown_links(source_text.splitlines())
    target_links = extract_markdown_links(target_lines)

    if len(source_links) != len(target_links):
        raise CompareError(
            f"Number of markdown links differs: "
            f"{len(source_links)} in source vs {len(target_links)} in target."
        )

    # Sequentially replace each link URL in target with the one from source
    for (src_link, _), (tgt_link, tgt_line_no) in zip(source_links, target_links):
        real_line_no = tgt_line_no - 1  # Convert to zero-based
        line = target_lines[real_line_no]
        link_replace = add_lang_code_if_needed(src_link, tgt_link, lang)
        target_lines[real_line_no] = line.replace(tgt_link, link_replace)

    target_lines.append("")  # To preserve the empty line in the end of the file
    return "\n".join(target_lines)


HTML_LINK_RE = re.compile(r"<a\s+[^>]*>.*?</a>")
HTML_LINK_TEXT = re.compile(r"<a\b([^>]*)>(.*?)</a>")
HTML_LINK_OPEN_TAG_RE = re.compile(r"<a\b([^>]*)>")
HTML_ATTR_RE = re.compile(r'(\w+)\s*=\s*([\'"])(.*?)\2')


def extract_html_links(lines: str) -> Dict[str, List[Tuple[str, list[str], str]]]:
    links = []
    for line_no, line in enumerate(lines, start=1):
        for html_link in HTML_LINK_RE.finditer(line):
            link_str = html_link.group(0)
            link_text = HTML_LINK_TEXT.match(link_str).group(2)
            link_data = (link_str, [], link_text)
            link_open_tag = HTML_LINK_OPEN_TAG_RE.match(link_str).group(1)
            attributes = re.findall(HTML_ATTR_RE, link_open_tag)
            for attr_name, quotes, attr_value in attributes:
                link_data[1].append((attr_name, quotes, attr_value))
            links.append((link_data, line_no))
    return links


TIANGOLO_COM = "https://fastapi.tiangolo.com"


def add_lang_code_if_needed(url: str, prev_url: str, lang_code: str) -> str:
    if url.startswith(TIANGOLO_COM):
        if prev_url.startswith(f"{TIANGOLO_COM}/{lang_code}"):
            url = url.replace(TIANGOLO_COM, f"{TIANGOLO_COM}/{lang_code}")
    return url


def reconstruct_html_link(
    attributes: List[Tuple[str, str, str]],
    link_text: str,
    prev_attributes: List[Tuple[str, str, str]],
    lang_code: str,
) -> str:
    prev_attributes_dict = {attr[0]: attr[2] for attr in prev_attributes}
    prev_url = prev_attributes_dict["href"]
    attributes_upd = []
    for attr_name, attr_quotes, attr_value in attributes:
        if attr_name == "href":
            attr_value = add_lang_code_if_needed(attr_value, prev_url, lang_code)
        attributes_upd.append((attr_name, attr_quotes, attr_value))

    attrs_str = " ".join(
        f"{name}={quetes}{value}{quetes}" for name, quetes, value in attributes_upd
    )
    return f"<a {attrs_str}>{link_text}</a>"


def replace_html_links(source_text: str, target_text: str, lang: str) -> str:
    target_lines = target_text.splitlines()
    source_links = extract_html_links(source_text.splitlines())
    target_links = extract_html_links(target_lines)

    if len(source_links) != len(target_links):
        raise CompareError(
            f"Number of HTML links differs: "
            f"{len(source_links)} in source vs {len(target_links)} in target."
        )

    # Sequentially replace attributes of each link URL in target with the one from source
    for (src_link_data, _), (tgt_link_data, tgt_line_no) in zip(
        source_links, target_links
    ):
        real_line_no = tgt_line_no - 1  # Convert to zero-based
        line = target_lines[real_line_no]
        tgt_link_text = tgt_link_data[2]

        tgt_link_original = tgt_link_data[0]
        tgt_link_override = reconstruct_html_link(
            src_link_data[1], tgt_link_text, tgt_link_data[1], lang
        )
        target_lines[real_line_no] = line.replace(tgt_link_original, tgt_link_override)

    target_lines.append("")  # To preserve the empty line in the end of the file
    return "\n".join(target_lines)


# ===================================================================================
# Images



# ===================================================================================
# Helper functions


def get_lang_doc_root_dir(lang: str) -> str:
    return Path(DOCS_ROOT) / lang / "docs"


def iter_all_en_paths() -> Iterable[Path]:
    """
    Iterate on the markdown files to translate in order of priority.
    """
    en_path = Path(get_lang_doc_root_dir("en"))

    first_dirs = [
        en_path / "learn",
        en_path / "tutorial",
        en_path / "advanced",
        en_path / "about",
        en_path / "how-to",
    ]
    first_parent = en_path
    yield from first_parent.glob("*.md")
    for dir_path in first_dirs:
        yield from dir_path.rglob("*.md")
    first_dirs_str = tuple(str(d) for d in first_dirs)
    for path in en_path.rglob("*.md"):
        if str(path).startswith(first_dirs_str):
            continue
        if path.parent == first_parent:
            continue
        yield path


def get_all_paths():
    res: list[str] = []
    en_docs_root = get_lang_doc_root_dir("en")
    for path in iter_all_en_paths():
        relpath = path.relative_to(en_docs_root)
        if not str(relpath).startswith(non_translated_sections):
            res.append(str(relpath))
    return res


# ===================================================================================
# Main


def process_one_file_with_retry(document_path: str, lang: str):
    en_docs_root_path = Path(get_lang_doc_root_dir("en"))
    lang_docs_root_path = Path(get_lang_doc_root_dir(lang))
    while True:
        try:
            process_one_file(
                en_docs_root_path / document_path,
                lang_docs_root_path / document_path,
                lang=lang,
            )
        except Retry:
            pass
        else:
            return


def process_one_file(en_doc_path_str: str, lang_doc_path_str: str, lang: str):
    en_doc_path = Path(en_doc_path_str)
    lang_doc_path = Path(lang_doc_path_str)
    if not en_doc_path.exists():
        print(f"❌🔎 {en_doc_path_str} - doesn't exist")
        return
    if not lang_doc_path.exists():
        print(f"❌🔎 {lang_doc_path_str} - doesn't exist")
        return

    en_doc_text = en_doc_path.read_text(encoding="utf-8")
    lang_doc_text = lang_doc_path.read_text(encoding="utf-8")
    lang_doc_text_orig = lang_doc_text

    try:
        lang_doc_text = replace_blocks(en_doc_text, lang_doc_text)
        lang_doc_text = replace_headers_and_permalinks(en_doc_text, lang_doc_text)
        lang_doc_text = replace_markdown_links(en_doc_text, lang_doc_text, lang=lang)
        lang_doc_text = replace_html_links(en_doc_text, lang_doc_text, lang=lang)

    except CompareError as e:
        print(f"❔❌ {lang_doc_path_str} Error: {e}")
        subprocess.run(["code", "--diff", lang_doc_path_str, en_doc_path_str])
        resp = ""
        while resp not in ("f", "e"):
            resp = input(
                "  Check the diff, fix the problem, and then type F if it's fixed or E to mark as invalid and skip: "
            )
            if resp.lower() == "e":
                print(f"❌ {lang_doc_path_str} skipped with error")
                return
        print(f"Check {lang_doc_path_str} again")
        raise Retry() from None

    # Images

    if lang_doc_text_orig != lang_doc_text:
        print(f"❔🆚 {lang_doc_path_str} - non-empty diff")
        tmp_path = Path(TMP_DOCS_PATH) / Path(lang_doc_path_str)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(lang_doc_text, encoding="utf-8")
        subprocess.run(["code", "--diff", str(lang_doc_path_str), str(tmp_path)])
        resp = ""
        while resp not in ("f", "e"):
            resp = input(
                "  Check the diff, fix the problem, and then type F to mark it as fixed or E to to mark as invalid and skip: "
            ).lower()
            if resp == "e":
                print(f"❌ {lang_doc_path_str} skipped with non-empty diff")
                return

    print(f"✅ {lang_doc_path_str}")


# ===================================================================================
# Typer app

cli = typer.Typer()


@cli.callback()
def callback():
    pass


LANGS = Literal["es", "de", "ru", "pt"]


@cli.command()
def process_all(
    lang: Annotated[LANGS, typer.Option()],
):
    """
    Go through all EN documents and compare special blocks with the corresponding
    blocks in translated versions ot those documents.
    """
    docs = get_all_paths()

    for doc in docs:
        process_one_file_with_retry(doc, lang)


@cli.command()
def process_pages(
    doc_paths: Annotated[
        list[str],
        typer.Argument(
            help="List of relative paths to the EN documents. Should be relative to docs/en/docs/",
        ),
    ],
    lang: Annotated[LANGS, typer.Option()],
):
    """
    Compare special blocks of specified EN documents with the corresponding blocks in
    translated versions of those documents.
    """

    for doc_path in doc_paths:
        process_one_file_with_retry(doc_path, lang)


if __name__ == "__main__":
    cli()
