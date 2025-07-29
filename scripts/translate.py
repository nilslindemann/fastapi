import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import git
import typer
import yaml
from pydantic_ai import Agent
from rich import print

non_translated_sections = (
    "reference/",
    "release-notes.md",
    "fastapi-people.md",
    "external-links.md",
    "newsletter.md",
    "management-tasks.md",
    "management.md",
    "contributing.md",
)


general_prompt = """
For technical terms in English that don't have a common translation term use the original term in English.

For code snippets or fragments, surrounded by backticks (`), don't translate the content, keep the original in English. For example, `list`, `dict`, keep them as is.

The content is written in markdown, write the translation in markdown as well. Don't add triple backticks (`) around the generated translation content.

The original content will be surrounded by triple percentage signs (%) and you should translate it to the target language. Do not include the triple percentage signs in the translation.

There are special blocks of notes, tips and others that look like:

/// note

To translate it, keep the same line and add the translation after a vertical bar.

For example, if you were translating to Spanish, you would write:

/// note | Nota

Some examples in Spanish:

Source:

/// tip

Result:

/// tip | Consejo

Source:

/// details | Preview

Result:

/// details | Vista previa
"""

app = typer.Typer()


@lru_cache
def get_langs() -> dict[str, str]:
    return yaml.safe_load(Path("docs/language_names.yml").read_text(encoding='utf-8'))


def generate_lang_path(*, lang: str, path: Path) -> Path:
    en_docs_path = Path("docs/en/docs")
    assert str(path).startswith(str(en_docs_path)), (
        f"Path must be inside {en_docs_path}"
    )
    lang_docs_path = Path(f"docs/{lang}/docs")
    out_path = Path(str(path).replace(str(en_docs_path), str(lang_docs_path)))
    return out_path


def generate_en_path(*, lang: str, path: Path) -> Path:
    en_docs_path = Path("docs/en/docs")
    assert not str(path).startswith(str(en_docs_path)), (
        f"Path must not be inside {en_docs_path}"
    )
    lang_docs_path = Path(f"docs/{lang}/docs")
    out_path = Path(str(path).replace(str(lang_docs_path), str(en_docs_path)))
    return out_path


def extract_codeblocks(text: str) -> tuple[str, dict[int, str]]:
    lines = text.splitlines(keepends=True)
    if not lines: raise Exception('text is empty')

    line_ = lines[0]
    line = line_.splitlines(keepends=False)[0]
    len_line_end = len(line_)-len(line)
    line_end = line_[-len_line_end:]
    del line_, line, len_line_end

    stripped: list[str] = []
    blocks: dict[int, str] = {}
    block = []
    blockindent = ''
    blockstartlinenum = 0
    blockstartcolnum = 0
    blockindex = 1
    in_block = False
    lookingfor = re.compile(r'^(\s*)(?:(`__CODEBLOCK_[0-9]+_PLACEHOLDER__`)|```)')
    for linenum, line in enumerate(lines):
        if found:=lookingfor.match(line):
            indent = found.group(1)
            existingplaceholder = found.group(2)
            if existingplaceholder:
                raise Exception(f'line {linenum}:{len(indent)}: Found "{existingplaceholder}", this confuses the translation script, as it inserts such markers itself')
            if in_block:
                if indent != blockindent:
                    raise Exception(f'line {blockstartlinenum}:{blockstartcolnum}, line {linenum}:{len(indent)}: Opening triple backticks inconsistent aligned to closing triple backticks')
                block.append(line)
                blocks[blockindex] = ''.join(block)
                block = []
                stripped.append(f'{blockindent}`__CODEBLOCK_{blockindex}_PLACEHOLDER__`{line_end}')
                blockindex += 1
                in_block = False
            else:
                blockindent = indent
                blockstartlinenum = linenum
                blockstartcolnum = len(indent)
                block.append(line)
                in_block = True
        else:
            (block if in_block else stripped).append(line)

    if in_block:
        raise Exception(f'line {blockstartlinenum}:{blockstartcolnum}: This codeblock was never closed')

    return ''.join(stripped), blocks


def add_back_codeblocks(translation: str, blocks: dict[int, str]) -> str:
    stripped = translation.splitlines(keepends=True)
    if not stripped: raise Exception('Text is empty')

    result: list[str] = []
    blockindent = ''
    lookingfor = re.compile(r'^(^\s*)`__CODEBLOCK_([1-9][0-9]*)_PLACEHOLDER__`')
    for linenum, line in enumerate(stripped):
        if found:=lookingfor.match(line):
            blockindent = found.group(1)
            blockindex = int(found.group(2))
            if blockindex not in blocks:
                raise Exception(f'line {linenum}:{len(blockindent)}: No codeblock with index {blockindex} available')
            result.append(blocks[blockindex])
            del blocks[blockindex]
        else:
            result.append(line)

    if blocks:
        raise Exception(f'Found no placeholders for block{'s' if len(blocks) > 1 else ''} {', '.join(str(k) for k in sorted(blocks.keys()))}')

    return ''.join(result)


@app.command()
def translate_page(*, lang: str, path: Path) -> None:
    langs = get_langs()
    language = langs[lang]
    lang_path = Path(f"docs/{lang}")
    lang_path.mkdir(exist_ok=True)
    lang_prompt_path = lang_path / "llm-prompt.md"
    assert lang_prompt_path.exists(), f"Prompt file not found: {lang_prompt_path}"
    lang_prompt_content = lang_prompt_path.read_text(encoding='utf-8')

    en_docs_path = Path("docs/en/docs")
    assert str(path).startswith(str(en_docs_path)), (
        f"Path must be inside {en_docs_path}"
    )
    out_path = generate_lang_path(lang=lang, path=path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    original_content = path.read_text(encoding='utf-8')
    original_content_without_codeblocks, codeblocks = extract_codeblocks(original_content)
    old_translation: str | None = None
    if out_path.exists():
        print(f"Found existing translation: {out_path}")
        old_translation, _ = extract_codeblocks(out_path.read_text(encoding='utf-8'))
    print(f"Translating {path} to {lang} ({language})")
    agent = Agent("openai:gpt-4o")

    prompt_segments = [
        general_prompt,
        lang_prompt_content,
    ]
    if old_translation:
        prompt_segments.extend(
            [
                "There's an existing previous translation for this content that is probably outdated with old content or old instructions.",
                "Update the translation given your current instructions and the original content.",
                "If you have instructions to translate specific terms or phrases in a specific way, please follow those instructions instead of keeping the old and outdated content.",
                "Previous translation:",
                f"%%%\n{old_translation}%%%",
            ]
        )
    prompt_segments.extend(
        [
            f"Translate to {language} ({lang}).",
            "Original content:",
            f"%%%\n{original_content_without_codeblocks}%%%",
        ]
    )
    prompt = "\n\n".join(prompt_segments)
    print(f"Running agent for {out_path}")
    result = agent.run_sync(prompt)
    try:
        out_content = add_back_codeblocks(f"{result.data.strip()}\n", codeblocks)
    except:
        safety_path = out_path.parent / (out_path.stem + '__NO_CODEBLOCKS__' + out_path.suffix)
        print(f"There was an error adding back the codeblocks. Saving the translation without codeblocks to {safety_path}")
        safety_path.write_text(f"{result.data.strip()}\n", encoding='utf-8')
        raise
    else:
        print(f"Saving translation to {out_path}")
        out_path.write_text(out_content, encoding='utf-8')


def iter_all_en_paths() -> Iterable[Path]:
    """
    Iterate on the markdown files to translate in order of priority.
    """
    first_dirs = [
        Path("docs/en/docs/learn"),
        Path("docs/en/docs/tutorial"),
        Path("docs/en/docs/advanced"),
        Path("docs/en/docs/about"),
        Path("docs/en/docs/how-to"),
    ]
    first_parent = Path("docs/en/docs")
    yield from first_parent.glob("*.md")
    for dir_path in first_dirs:
        yield from dir_path.rglob("*.md")
    first_dirs_str = tuple(str(d) for d in first_dirs)
    for path in Path("docs/en/docs").rglob("*.md"):
        if str(path).startswith(first_dirs_str):
            continue
        if path.parent == first_parent:
            continue
        yield path


def iter_en_paths_to_translate() -> Iterable[Path]:
    for path in iter_all_en_paths():
        if str(path).replace("docs/en/docs/", "").startswith(non_translated_sections):
            continue
        yield path


@app.command()
def translate_all(lang: str) -> None:
    paths_to_process = list(iter_en_paths_to_translate())
    print("Original paths:")
    for p in paths_to_process:
        print(f"  - {p}")
    print(f"Total original paths: {len(paths_to_process)}")
    missing_paths: list[Path] = []
    skipped_paths: list[Path] = []
    for p in paths_to_process:
        lang_path = generate_lang_path(lang=lang, path=p)
        if lang_path.exists():
            skipped_paths.append(p)
            continue
        missing_paths.append(p)
    print("Paths to skip:")
    for p in skipped_paths:
        print(f"  - {p}")
    print(f"Total paths to skip: {len(skipped_paths)}")
    print("Paths to process:")
    for p in missing_paths:
        print(f"  - {p}")
    print(f"Total paths to process: {len(missing_paths)}")
    for p in missing_paths:
        print(f"Translating: {p}")
        translate_page(lang="es", path=p)
        print(f"Done translating: {p}")


@app.command()
def list_removable(lang: str) -> list[Path]:
    removable_paths: list[Path] = []
    lang_paths = Path(f"docs/{lang}").rglob("*.md")
    for path in lang_paths:
        en_path = generate_en_path(lang=lang, path=path)
        if not en_path.exists():
            removable_paths.append(path)
    print(removable_paths)
    return removable_paths


@app.command()
def list_all_removable() -> list[Path]:
    all_removable_paths: list[Path] = []
    langs = get_langs()
    for lang in langs:
        if lang == "en":
            continue
        removable_paths = list_removable(lang)
        all_removable_paths.extend(removable_paths)
    print(all_removable_paths)
    return all_removable_paths


@app.command()
def remove_removable(lang: str) -> None:
    removable_paths = list_removable(lang)
    for path in removable_paths:
        path.unlink()
        print(f"Removed: {path}")
    print("Done removing all removable paths")


@app.command()
def remove_all_removable() -> None:
    all_removable = list_all_removable()
    for removable_path in all_removable:
        removable_path.unlink()
        print(f"Removed: {removable_path}")
    print("Done removing all removable paths")


@app.command()
def list_outdated(lang: str) -> list[Path]:
    dir_path = Path(__file__).absolute().parent.parent
    repo = git.Repo(dir_path)

    outdated_paths: list[Path] = []
    en_lang_paths = list(iter_en_paths_to_translate())
    for path in en_lang_paths:
        lang_path = generate_lang_path(lang=lang, path=path)
        if not lang_path.exists():
            outdated_paths.append(path)
            continue
        en_commit_datetime = list(repo.iter_commits(paths=path, max_count=1))[
            0
        ].committed_datetime
        lang_commit_datetime = list(repo.iter_commits(paths=lang_path, max_count=1))[
            0
        ].committed_datetime
        if lang_commit_datetime < en_commit_datetime:
            outdated_paths.append(path)
    print(outdated_paths)
    return outdated_paths


@app.command()
def update_outdated(lang: str) -> None:
    outdated_paths = list_outdated(lang)
    for path in outdated_paths:
        print(f"Updating lang: {lang} path: {path}")
        translate_page(lang=lang, path=path)
        print(f"Done updating: {path}")
    print("Done updating all outdated paths")


if __name__ == "__main__":
    app()
