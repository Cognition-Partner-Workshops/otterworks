# xslt-golden

Runs XSLT maps (BizTalk, Mule, hand-written) over a corpus of input messages with Saxon
(SaxonC-HE through `saxonche`) and writes or checks golden outputs byte for byte. One
manifest per estate; one row per message in the output so a parity report can quote it.

```bash
pip install -r tools/xslt-golden/requirements.txt
python tools/xslt-golden/xslt_golden.py write --manifest <estate>/corpus/manifest.yaml   # regenerate goldens
python tools/xslt-golden/xslt_golden.py check --manifest <estate>/corpus/manifest.yaml   # gate, exit 1 on any diff
```

Maps whose XSLT embeds `msxsl:script` (inline C# functoids) do not run under Saxon. The
estate supplies a `*.golden.xslt` twin with the script body hand-translated to XSLT 3.0
functions and names it in the manifest; the estate's `ESTATE.md` says what the twin reproduces.

Tests: `python -m pytest tools/xslt-golden/tests -q`.
