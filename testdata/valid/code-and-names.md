---
title: The tool and its flags
description: A file with front matter, code, links, and names.
tags: [reference, cli]
---

# The tool and its flags

The command is `scripts/release.sh`, exposed through the API. The parser
replaces each span of code with spaces, and the two words that the code
divides are not one verb construction.

VS Code and the other editors read this file. The name "VS Code" has a
capital letter, thus it is a name and not a Latin abbreviation.

| Flag | What it does |
|---|---|
| `--format` | Selects the shape of the report |
| `--limit` | Gives the maximum number of findings |

The result is [the report](https://example.com/report), signed by the team.

```bash
# A code fence holds no prose, thus no rule reads it.
ste lint --mode strict docs/; echo "it isn't a finding"
```

Read the [start page](index.md) for more data. The link target holds a
semicolon, and no rule reads it.
