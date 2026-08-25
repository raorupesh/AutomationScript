"""Parser for the BHF-style vendor purchase order text format.

The item table can't be sliced by fixed column position: numbers are
right-aligned and vary in width (e.g. CTNS can be 1 to 4 digits), so a wide
value shifts into its neighboring column. Instead each item line is matched
with one regex per row, anchored on each column's decimal precision, which
*is* constant (RETAIL always X.XX, COST/EXT COST always X.XXX, CUBE always
X.XXXX, KILOGRAMS always X.XX). DESCRIPTION is free text, so it's captured
non-greedily between VENDOR PART# and RETAIL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOLERANCE = 0.01  # acceptable rounding drift when comparing recomputed vs printed dollar amounts

ITEM_LINE_RE = re.compile(
    r"^(?P<dept>\d+)\s+(?P<sku>\S+)\s+(?P<vendor_part>\S+)\s+(?P<description>.+?)\s+"
    r"(?P<retail>\d+\.\d{2})\s+(?P<cost>\d+\.\d{3})\s+(?P<ext_cost>\d+\.\d{3})\s+"
    r"(?P<ctns>\d+)\s+(?P<cspk>\d+)\s+(?P<ext_qty>\d+)\s+"
    r"(?P<cube>\d+\.\d{4})\s+(?P<kilograms>\d+\.\d{2})\s*$"
)
# The UPC sits alone on the line directly under its item row.
UPC_LINE_RE = re.compile(r"^\s*(\d{6,})\s*$")


@dataclass
class LineItem:
    dept: str
    sku: str
    vendor_part: str
    description: str
    retail: float
    cost: float
    ext_cost: float
    ctns: int
    cspk: int
    ext_qty: int
    cube: float
    kilograms: float
    upc: str = ""
    computed_ext_qty: int = field(init=False, default=0)
    computed_ext_cost: float = field(init=False, default=0.0)
    ext_qty_ok: bool = field(init=False, default=True)
    ext_cost_ok: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        self.computed_ext_qty = self.ctns * self.cspk
        self.computed_ext_cost = self.cost * self.computed_ext_qty
        self.ext_qty_ok = self.computed_ext_qty == self.ext_qty
        self.ext_cost_ok = abs(self.computed_ext_cost - self.ext_cost) <= TOLERANCE


@dataclass
class PurchaseOrder:
    buyer: str = ""
    ship_terms: str = ""
    po_number: str = ""
    ref_master_po: str = ""
    ship_date: str = ""
    vendor: str = ""
    ship_to: str = ""
    bill_to: str = ""
    items: list[LineItem] = field(default_factory=list)


def _first_match(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else default


def _parse_header(lines: list[str]) -> dict:
    top = "\n".join(lines[:4])
    return {
        "buyer": _first_match(r"BUYER:\s*(.*?)\s{2,}", lines[0]),
        "ship_terms": _first_match(r"SHIP TERMS:\s*(.*?)\s{2,}", lines[1]),
        "po_number": _first_match(r"PO#:\s*(\S+)", lines[1]),
        "ref_master_po": _first_match(r"REF MASTER PO#:\s*(\S+)", top),
        "ship_date": _first_match(r"SHIP DATE:\s*(\S+)", top),
    }


def _parse_labeled_block(lines: list[str], heading: str) -> list[str]:
    """Collect the non-blank lines under a `heading` / `------` underline."""
    for i, line in enumerate(lines):
        if line.strip() == heading:
            block = []
            for l in lines[i + 2:]:
                if not l.strip():
                    break
                block.append(l.strip())
            return block
    return []


def _parse_ship_bill_to(lines: list[str]) -> tuple[str, str]:
    """SHIP TO and BILL TO are printed as two side-by-side address blocks."""
    for i, line in enumerate(lines):
        if line.strip().startswith("SHIP TO") and "BILL TO" in line:
            split_col = line.index("BILL TO")
            ship_parts, bill_parts = [], []
            for l in lines[i + 2:]:
                if not l.strip():
                    break
                left, right = l[:split_col].strip(), l[split_col:].strip()
                if left:
                    ship_parts.append(left)
                if right:
                    bill_parts.append(right)
            return ", ".join(ship_parts), ", ".join(bill_parts)
    return "", ""


def _parse_items(lines: list[str]) -> list[LineItem]:
    items: list[LineItem] = []
    for line in lines:
        m = ITEM_LINE_RE.match(line)
        if m:
            d = m.groupdict()
            items.append(LineItem(
                dept=d["dept"],
                sku=d["sku"],
                vendor_part=d["vendor_part"],
                description=d["description"],
                retail=float(d["retail"]),
                cost=float(d["cost"]),
                ext_cost=float(d["ext_cost"]),
                ctns=int(d["ctns"]),
                cspk=int(d["cspk"]),
                ext_qty=int(d["ext_qty"]),
                cube=float(d["cube"]),
                kilograms=float(d["kilograms"]),
            ))
            continue
        u = UPC_LINE_RE.match(line)
        if u and items:
            items[-1].upc = u.group(1)
    return items


def parse_purchase_order(text: str) -> PurchaseOrder:
    lines = text.splitlines()
    header = _parse_header(lines)
    vendor = ", ".join(_parse_labeled_block(lines, "VENDOR"))
    ship_to, bill_to = _parse_ship_bill_to(lines)
    items = _parse_items(lines)
    return PurchaseOrder(
        buyer=header["buyer"],
        ship_terms=header["ship_terms"],
        po_number=header["po_number"],
        ref_master_po=header["ref_master_po"],
        ship_date=header["ship_date"],
        vendor=vendor,
        ship_to=ship_to,
        bill_to=bill_to,
        items=items,
    )
