# Purchase Order Text-to-Spreadsheet Converter

Turns `purchase_order_sample.txt` (a semi-structured vendor PO) into a row-per-SKU
spreadsheet matching `output_template_blank.xlsx`, with a validation pass on the
extended quantity / cost math.

## Usage

```bash
pip install -r requirements.txt
python generate_output.py
```

Optional positional args override the defaults: `python generate_output.py <input.txt> <template.xlsx> <output.xlsx>`.

This writes `output.xlsx` and prints a one-line parse/validation summary to the console.

## Files

- `po_parser.py`: Parsing Logic: reads the raw text and returns a `PurchaseOrder`
  (header fields) with a list of `LineItem`s (one per SKU, validated).
- `generate_output.py` Orchestration: runs the parser, writes rows into a copy  of the template workbook, flags validation mismatches, saves `output.xlsx`.
- `output.xlsx`: Generated output, committed as a deliverable.

## Approach

The header block (BUYER / SHIP TERMS / PO# / REF MASTER PO# / SHIP DATE) is pulled
with small targeted regexes off the first four lines each label has a stable
`LABEL: value` shape, so this was more robust than fixed columns.

VENDOR, SHIP TO, and BILL TO are multi-line address blocks. VENDOR is parsed by
grabbing every non-blank line under the `VENDOR` / `------` heading. SHIP TO and
BILL TO print as two side-by-side columns under one `SHIP TO ... BILL TO` heading;
the column split point is taken from the character offset of the literal text
"BILL TO" in that heading line, then each subsequent line is sliced left/right at
that offset until the blank line that ends the block. Each address block is
flattened into a single comma-separated string so it fits one cell.

The line item table was the interesting part. I initially tried slicing columns
by position, using the dashed `---- ----` separator row to find each column's
start offset. That works for the label-width portion of a column but breaks the
moment a right-aligned number is wider than its header (e.g. `CTNS` is only 4
dashes wide, but a value like `1013` pushes into the neighboring column). So the
line items are parsed with one regex per row instead, anchored on the fact that
each numeric column has a *constant* number of decimal places for the whole
sample (RETAIL always `X.XX`, COST/EXT COST always `X.XXX`, CUBE always `X.XXXX`,
KILOGRAMS always `X.XX`), with CTNS/CSPK/EXT QTY as plain integers and DESCRIPTION
captured non-greedily in between DPT/SKU/VENDOR PART# and RETAIL. The UPC prints
on its own indented line directly beneath each item row, so it's picked up as
"next line is a bare run of 6+ digits" and attached to the item above it.

## Validation

For every line item: `computed EXT QTY = CTNS x CSPK` and
`computed EXT COST = COST x computed EXT QTY`, compared against the values
printed on the PO (dollar comparisons use a $0.01 tolerance for rounding).
On the provided sample, all 12 rows validate cleanly no mismatches.

`output_template_blank.xlsx` has no dedicated "flag" column, and the brief says
the output has to match that schema exactly, so mismatches are surfaced two ways
without changing the schema:
1. The `EXT Cost` / `EXT QTY` cell is filled red on any row that fails validation.
2. A second `Validation` sheet is added to the workbook listing every mismatch
   (SKU, field, printed value, recomputed value), or a one-line "no discrepancies"
   note if the PO is clean.

## Assumptions

- **`Total Cost` column**: this header exists in the template but isn't one of
  the fields listed in the instructions. I used it to hold the *recomputed*
  EXT COST (`cost x computed ext qty`), so it sits next to the parsed `EXT Cost`
  column as a built-in visual cross-check. Worth confirming with BHF what this
  column is actually meant to hold.
- **VENDOR / SHIP TO / BILL TO as flat strings**: the schema gives each of these
  one column, so multi-line addresses are joined with `", "` rather than kept as
  embedded newlines.
- **Recompute chain**: "recompute EXT COST (cost x ext qty)" is read as using the
  *recomputed* EXT QTY, not the printed one EXT COST is checked against
  `cost x (ctns x cspk)`, so a bad EXT QTY doesn't silently mask a bad EXT COST
  (or vice versa).
- Only one PO / one page is handled the sample has no page breaks or multiple
  purchase orders in one file.
- `DPT`, `SKU`, `Vendor Part #`, and `UPC` are kept as text, not numbers, so
  leading zeros (the UPC starts with `0`) aren't dropped.

## What I'd change with more time

- Handle multiple POs per file / multi-page documents, and surface a clear error
  instead of silently parsing zero items if the format doesn't match at all.
- Add unit tests around the regexes and block parsers using a couple of
  hand-crafted edge-case fixtures (missing UPC, wrapped description, missing
  BILL TO block, etc.), rather than relying on the one sample file.
- Pull the mismatch tolerance and file paths into CLI flags/argparse instead of
  positional args.
- Ask organisation what `Total Cost` is actually supposed to represent instead of
  guessing from context.

## AI coding assistant

I used Claude Code for this exercise. There's no `CLAUDE.md` / `AGENTS.md`  in this repo no persistent instruction file was set up for the
project. Direction was given conversationally: I supplied the two attachments, Claude Code read both input files, inferred the
column layout and header positions by inspecting the raw text and the template's
column headers directly (rather than being told them), and I reviewed each
parsing decision (column-split logic, regex column boundaries, the `Total Cost`
ambiguity) before generating the final output.
Lastly, used to formaulate key bullet points and explanation in README.md file.