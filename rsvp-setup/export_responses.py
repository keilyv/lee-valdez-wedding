#!/usr/bin/env python3
"""Export live D1 RSVPs to a private, formatted Excel workbook.

Run from anywhere: python3 export_responses.py
Only Python's standard library and the already-installed Wrangler are needed.
"""

import argparse
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


QUERY = ("SELECT household_name, max_guests, attendance, guest_count, guest_names, "
         "dietary_notes, message, responded_at FROM invitations "
         "WHERE active = 1 ORDER BY household_name")
HEADERS = ["Household", "Status", "Invited", "Attending", "Guest names",
           "Dietary notes", "Message", "Responded (UTC)"]
WIDTHS = [29, 19, 12, 13, 34, 34, 44, 23]


def get_rows(input_json=None):
    if input_json:
        payload = json.loads(input_json.read_text(encoding="utf-8"))
    else:
        cmd = ["npx", "wrangler", "d1", "execute", "wedding-rsvps", "--remote",
               "--json", "--command", QUERY]
        result = subprocess.run(cmd, cwd=Path(__file__).resolve().parent,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Wrangler failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Wrangler did not return JSON. Run npx wrangler login and try again.") from exc
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ValueError("Unexpected D1 response")
    if any(part.get("success") is False for part in payload):
        raise RuntimeError("D1 could not read the RSVP database")
    rows = payload[0].get("results")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("D1 response did not contain invitation rows")
    return rows


def tag(value):
    return escape(str(value), {'"': '&quot;'})


def col_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def cell(row, column, value, style=0):
    address = f"{col_name(column)}{row}"
    if isinstance(value, int):
        return f'<c r="{address}" s="{style}"><v>{value}</v></c>'
    value = "" if value is None else str(value)
    # Inline text is never parsed as an Excel formula, even for guest-supplied text.
    return (f'<c r="{address}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{tag(value)}</t></is></c>')


def sheet_xml(rows, generated_at):
    counts = {
        "Attending": sum(row.get("attendance") == "attending" for row in rows),
        "Declined": sum(row.get("attendance") == "declined" for row in rows),
        "No reply yet": sum(not row.get("attendance") for row in rows),
    }
    guest_total = sum(int(row.get("guest_count") or 0) for row in rows
                      if row.get("attendance") == "attending")
    lines = [
        '<row r="1" ht="36"><c r="A1" s="1" t="inlineStr"><is><t>Keily &amp; Nathan</t></is></c></row>',
        '<row r="2" ht="28">' + cell(2, 1, "Wedding RSVP responses", 2) + '</row>',
        '<row r="3" ht="23">' + cell(3, 1, "Exported " + generated_at + " (UTC)", 3) + '</row>',
    ]
    summary = [("Households", len(rows)), ("Attending", counts["Attending"]),
               ("Declined", counts["Declined"]), ("No reply yet", counts["No reply yet"]),
               ("Confirmed guests", guest_total)]
    lines.append('<row r="5" ht="28">' + ''.join(
        cell(5, i + 1, label, 4) for i, (label, _) in enumerate(summary)) + '</row>')
    lines.append('<row r="6" ht="33">' + ''.join(
        cell(6, i + 1, value, 5) for i, (_, value) in enumerate(summary)) + '</row>')
    lines.append('<row r="8" ht="28">' + ''.join(
        cell(8, i + 1, heading, 6) for i, heading in enumerate(HEADERS)) + '</row>')
    for excel_row, record in enumerate(rows, start=9):
        status = {"attending": "Attending", "declined": "Declined"}.get(
            record.get("attendance"), "No reply yet")
        style = {"Attending": 8, "Declined": 9, "No reply yet": 10}[status]
        alternate = 7 if excel_row % 2 == 0 else 0
        values = [record.get("household_name", ""), status, int(record.get("max_guests") or 0),
                  int(record.get("guest_count") or 0) if record.get("attendance") == "attending" else "",
                  record.get("guest_names", ""), record.get("dietary_notes", ""),
                  record.get("message", ""), record.get("responded_at", "")]
        name_lines = str(record.get("guest_names") or "").count("\n") + 1
        row_height = min(180, max(30, name_lines * 18 + 12))
        lines.append(f'<row r="{excel_row}" ht="{row_height}">' + ''.join(
            cell(excel_row, i + 1, value, style if i == 1 else (11 if i == 4 and alternate == 0 else alternate))
            for i, value in enumerate(values)) + '</row>')
    end_row = max(8, 8 + len(rows))
    widths = ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
                     for i, width in enumerate(WIDTHS, start=1))
    return ('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="8" topLeftCell="A9" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="22"/><cols>''' + widths + '</cols><sheetData>' +
            ''.join(lines) + f'</sheetData><autoFilter ref="A8:H{end_row}"/>' +
            '<mergeCells count="3"><mergeCell ref="A1:H1"/><mergeCell ref="A2:H2"/>'
            '<mergeCell ref="A3:H3"/></mergeCells>'
            '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
            '</worksheet>')


STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="5"><font><sz val="11"/><name val="Aptos"/><color rgb="FF38342F"/></font>
<font><sz val="20"/><name val="Georgia"/><color rgb="FFFFFFFF"/></font>
<font><sz val="16"/><name val="Georgia"/><color rgb="FFAD614B"/></font>
<font><sz val="11"/><name val="Aptos"/><color rgb="FF80665D"/></font>
<font><b/><sz val="11"/><name val="Aptos"/><color rgb="FFFFFFFF"/></font></fonts>
<fills count="7"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFAD614B"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEDF4F8"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFAF6EF"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE4F2E5"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF5E5D9"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="12">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="4" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="4" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" indent="1" wrapText="1"/></xf>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def write_xlsx(destination, rows, generated_at):
    parts = {
        '[Content_Types].xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>''',
        '_rels/.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''',
        'xl/workbook.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Responses" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        'xl/_rels/workbook.xml.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        'xl/styles.xml': STYLES,
        'xl/worksheets/sheet1.xml': sheet_xml(rows, generated_at),
    }
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)


def main():
    parser = argparse.ArgumentParser(description="Save current private RSVPs to an Excel workbook")
    parser.add_argument("--input-json", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        rows = get_rows(args.input_json)
        folder = args.output_dir or Path(__file__).resolve().parent.parent.parent / 'wedding-rsvp-private'
        folder.mkdir(mode=0o700, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')
        output = folder / f'wedding-responses-{stamp}.xlsx'
        write_xlsx(output, rows, datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M'))
        output.chmod(0o600)
        print(f"Saved {len(rows)} household responses to {output}")
        print("Keep this workbook private. Run the same command later for an updated copy.")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Could not export responses: {exc}\n")


if __name__ == "__main__":
    main()
