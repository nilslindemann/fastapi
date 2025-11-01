# Description
This script should be helpful in checking translations made by LLM.
It's rare, but sometimes LLM modifies parts, that shouldn't be modified (code blocks, URLs, permalinks).
When you need to check a lot of documents, it's hard to compare all of them manually. This script automates some of this work!

# Algorithm:
* Take one document (original En version and its translation to target language)
* Extract blocks that shouldn't be changed (sometimes they can be changed, e.g. translated comments in code block)
  * multiline code blocks
  * headers and permalinks
  * links
* Compare those extracted blocks:
  * multiline code blocks - compare total number
  * headers - compare total number and levels (e.g. `#`, `##`)
  * links - compare total number
* If any mismatch detected on previous step:
  * script will show the error message and open VSCode editor to see the diff between translated page and original page
  * user should fix the error and continue (type `F`) or skip and mark this document as invalid (type `E`)
  * script will check this document again to ensure there is no mismatch anymore
* Script will create a temporary document and write the content of translated document, but with all special blocks (multiline code blocks, permalinks, links) replaced by corresponding blocks from original En document.
* If the diff between that temporary document and translated document is not empty, the VSCode editor will be opened with the diff between them
  * This way it's easy to see what was changed in those blocks (diff is usually quite small).
  * User should check the diff, fix mistakes if needed, and then continue (type `F`) or skip and mark this document as invalid.

# Run:
* It's supposed that the script is placed in the root of the project dirrectory.
* You can run script for all documents of specified language with `python cmpr.py process-all --lang de` command
* You can run script for specific pages of specified language with `python cmpr.py process-pages path/to/page1.md path/to/page2.md --lang de`

By-default script uses `non-git/translations` path to store temporary documents. You can configure it to use different path using `TMP_DOCS_PATH` environment variable.
