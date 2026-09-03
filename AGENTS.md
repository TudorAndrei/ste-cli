# ste for an agent

`ste` finds ASD-STE100 (Simplified Technical English) violations in Markdown
and plain text. This page gives the rules that an agent must obey. A person
can read [the start page](https://tudorandrei.github.io/ste-cli/) instead.

## Read the schema first

```bash
ste schema
```

The result is JSON of about 6 kB. It gives each command and each flag, with
its type and its permitted values. It also gives each config key, each rule
with its number in the standard, the fields of a finding, and the exit
codes. **Read a rule identifier from that document, and not from the text
of a message.** A
message is for a person and it can change. An identifier does not change.

## Control the size before you run

The output of a large repository is large. One repository of 180 files gave
**3.7 MB of JSON**. That is more than a context window, and most of it is
not necessary for a decision.

| Invocation | Bytes |
|---|---|
| `ste lint --format json .` | 3 675 857 |
| `ste lint --format json --limit 20 .` | 7 539 |
| `ste lint --format json --limit 20 --fields rule_id,file,line,text .` | 2 711 |
| `ste lint --format json --summary .` | 226 |

Thus:

1. Start with `--summary` to see the size of the problem.
2. Then read the findings with `--limit` and `--fields`.
3. Use `--format ndjson` to read one finding for each line and to stop when
   you have enough.

`summary.findings` always gives the real total, and `summary.shown` gives
the number in this output. `summary.truncated` is true when `--limit`
removed a finding. Do not report `shown` as the total.

## The exit code is not a count of findings

| Code | Condition |
|---|---|
| 0 | The tool ran. **Findings alone do not change this code.** |
| 1 | A gate failed: `--fail-on-new`, `--warnings-as-errors`, or `--fail-over`. |
| 2 | A flag, a file, or the config has an error. The message names the problem. |

Do not use exit code 0 as proof that a document has no violation. Read
`summary.findings`.

## Change a file only with a plan

`ste baseline` and `ste dict import` write a file, and `ste dict remove`
deletes one. Each takes `--dry-run`, which gives the plan as JSON and
changes nothing:

```bash
ste baseline --dry-run --format json .
# {"action":"baseline","dry_run":true,"path":".ste-baseline.json",
#  "findings":974,"files":156,"exists":false}
```

Run the plan first when you did not write the command yourself.

## The output shape

`--format json` gives one object:

```json
{
  "version": 1, "tool": "ste", "mode": "flavored",
  "summary": {"files":2,"words":18,"findings":4,"score":22.2,
              "shown":4,"truncated":false,"errors":0},
  "files":    [{"path":"a.md","words":9,"count":2}],
  "findings": [{"rule_id":"STE-4.2","severity":"warning","confidence":0.98,
                "file":"a.md","line":1,"column":11,"start":10,"end":15,
                "text":"isn't","message":"...","suggestion":"..."}]
}
```

The findings are **one flat list**, and each finding names its file. There
is no second list for each file. `files` names only the files of the
findings in the output.

`--format ndjson` gives one object for each line. Each line has a `type` of
`finding` or `summary`, and the summary line is last.

## Do not correct a finding without care

A finding is not always a defect. The tool has no part-of-speech tagger, and
`confidence` states how sure it is:

- `1.00` and `0.98`: a semicolon, a contraction. Correct it.
- `0.90` to `0.95`: usually a defect.
- `0.60` to `0.70`: the tool cannot separate a noun from a verb, or an
  adjective from a passive verb. **Read the sentence before you change it.**

`STE-GR-6` is a general recommendation of the standard, and not a rule. It
always has the `info` severity, and no flag makes it an error.

## Do not make the text worse

- Never change a quotation to satisfy a rule. Use
  `<!-- ste-disable-next-line STE-3.6 -->` above it.
- Never change a name. "VS Code" and "Defence Industries" are names.
- A technical noun of the project belongs in `allow.nouns` of the config,
  and not in a rewrite. Rule 1.6 of the standard permits it.

## The dictionary is off, and this is deliberate

`ste dict import` needs a copy of ASD-STE100 that **the user** supplies. The
tool does not ship the dictionary, and an agent must not try to find one on
the internet or write one from memory. The terms of ASD do not permit
redistribution.

With the dictionary, rule `STE-1.1` reports about 1 word in 10 of general
software documentation. ASD-STE100 approves about 900 words, for the
maintenance of an aircraft. Do not give `--use-dict` unless the user asks.

## A first run on a repository that has documentation

```bash
ste lint --format json --summary .   # the size of the problem
ste baseline .                       # accept it
ste lint --fail-on-new --format json --limit 20 .
```

The baseline holds the findings of today. After it, only a new finding comes
to the report, and the work of the user does not stop.
