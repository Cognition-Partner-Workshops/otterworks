# Citation and evidence conventions

- Source baseline: `demo-insrules` at `3d1c5662441923c6361912e088f2f9c60ae6d6e9`. The extraction workers reported HTTP 429 from DeepWiki or no branch source from Ask Devin; no wiki citation is used. Citation line ranges were checked directly against the checked-out branch.
- COBOL citations use `RATEPREM.cbl:PARAGRAPH` and physical line numbers; Pharo uses `Class>>selector` linked to the method's file and lines. Section sources apply to each rule in the section. Specific citations also include `tables/<file>.dat:<line>` for table-driven behavior, including searched rows when no row matched.
- Fixtures are policy IDs in [`fixtures/policies.dat`](../fixtures/policies.dat). `make insrules-reset` runs the original 200 policies; catalog evidence uses `build/cobol.dat` and `build/pharo.txt`. The headless Pharo batch invokes the same `InsQuoteEngine>>quote:` entry point as the screen.
- Unless explicitly given in dollars, amounts are cents. `T` denotes the requested territory, `D` the default, and `O` an override. `Y`/`N` following a modified amount is the minimum-applied flag. COBOL prints the class rate and factor; Pharo prints the factor source and premium but not those intermediate values. The table keys and source establish the selected row when the premium is sufficient to distinguish it.
- Decode COBOL with [`RATEOUT.cpy`](../cobol/copybooks/RATEOUT.cpy#L5-L16). The total occupies columns 58–68 (zero-based slice `[57:68]`); the catalog reads this field directly.

## Status

- **proven:** an executed fixture shows the condition on both legacy stacks.
- **from-table:** an executed fixture demonstrates the condition derived from a specific table row.
- **amber:** the legacy outputs disagree or the source is ambiguous; both source paths and the reason are retained.
- **unproven:** no fixture reaches the condition, the output cannot distinguish it from another path, or the condition is single-stack without an evidenced disagreement. A row may be inferred to be reached without the output independently proving its behavior.

## Input artifacts

The final catalog supersedes the input counts and status labels. The original documents are retained on their working branches:

- [COBOL extraction](https://github.com/Cognition-Partner-Workshops/otterworks/blob/da2a78db52595a075994f78aee00e3755e946eb3/legacy-rating/catalog/extract/cobol-rules.md) and [COBOL cross-check](https://github.com/Cognition-Partner-Workshops/otterworks/blob/6e0501ddea4507c45ee866b616e9c2857771e792/legacy-rating/catalog/extract/cobol-crosscheck.md).
- [Pharo extraction](https://github.com/Cognition-Partner-Workshops/otterworks/blob/9c147020e4244162c008698dbfa60f56d2484fef/legacy-rating/catalog/pharo-extract.md) and [Pharo cross-check](https://github.com/Cognition-Partner-Workshops/otterworks/blob/0f4e16cb3ae8fbf37ea72115934388324950bdcc/legacy-rating/catalog/crosscheck-pharo.md).
