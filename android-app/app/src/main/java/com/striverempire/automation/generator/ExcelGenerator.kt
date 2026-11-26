package com.striverempire.automation.generator

import com.striverempire.automation.model.ProductRecord
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

object ExcelGenerator {
    val COLUMNS = listOf(
        "Sr. no.",
        "Product Name",
        "Total Price",
        "Less Price",
        "Real Price",
        "Size",
        "Type",
    )

    private fun xmlEscape(text: String): String {
        return buildString(text.length) {
            for (ch in text) {
                when (ch) {
                    '&' -> append("&amp;")
                    '<' -> append("&lt;")
                    '>' -> append("&gt;")
                    '"' -> append("&quot;")
                    '\'' -> append("&apos;")
                    else -> append(ch)
                }
            }
        }
    }

    private fun colLetter(col1Based: Int): String {
        return ('A' + (col1Based - 1)).toString()
    }

    fun generate(
        records: List<ProductRecord>,
        outputFile: File,
        headerHexRgb: String = HeaderColorPicker.pickReadableHex(),
    ): File {
        outputFile.parentFile?.mkdirs()
        val cleanHex = headerHexRgb.removePrefix("#").uppercase()
        val maxRow = maxOf(1, records.size + 1)

        ZipOutputStream(FileOutputStream(outputFile)).use { zip ->
            fun putEntry(name: String, content: String) {
                zip.putNextEntry(ZipEntry(name))
                zip.write(content.toByteArray(Charsets.UTF_8))
                zip.closeEntry()
            }

            putEntry(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
            )

            putEntry(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
            )

            putEntry(
                "xl/workbook.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Products" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""
            )

            putEntry(
                "xl/_rels/workbook.xml.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
            )

            putEntry("xl/styles.xml", buildStylesXml(cleanHex))
            putEntry("xl/worksheets/sheet1.xml", buildSheetXml(records, maxRow))
        }
        return outputFile
    }

    /**
     * Style indices (cellXfs):
     * 0: default
     * 1: header (bold black Arial 11, random header fill, center)
     * 2: body white left
     * 3: body white center
     * 4: body white right 0.00
     * 5: body zebra (#F5F5F5) left
     * 6: body zebra (#F5F5F5) center
     * 7: body zebra (#F5F5F5) right 0.00
     */
    private fun buildStylesXml(headerHex: String): String {
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1">
    <numFmt numFmtId="164" formatCode="0.00"/>
  </numFmts>
  <fonts count="2">
    <font><sz val="10"/><color rgb="FF000000"/><name val="Arial"/></font>
    <font><b/><sz val="11"/><color rgb="FF000000"/><name val="Arial"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF$headerHex"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF5F5F5"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FF333333"/></left>
      <right style="thin"><color rgb="FF333333"/></right>
      <top style="thin"><color rgb="FF333333"/></top>
      <bottom style="thin"><color rgb="FF333333"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
  </cellXfs>
</styleSheet>"""
    }

    private fun buildSheetXml(records: List<ProductRecord>, maxRow: Int): String {
        val sb = StringBuilder()
        sb.append("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>""")
        sb.append("""<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">""")
        sb.append("""<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>""")

        val colWidths = computeColWidths(records)
        sb.append("<cols>")
        colWidths.forEachIndexed { i, w ->
            val idx = i + 1
            sb.append("""<col min="$idx" max="$idx" width="$w" customWidth="1"/>""")
        }
        sb.append("</cols>")

        sb.append("<sheetData>")
        // Header Row (Row 1)
        sb.append("""<row r="1" ht="26" customHeight="1">""")
        COLUMNS.forEachIndexed { colIdx, title ->
            val ref = "${colLetter(colIdx + 1)}1"
            sb.append("""<c r="$ref" t="inlineStr" s="1"><is><t>${xmlEscape(title)}</t></is></c>""")
        }
        sb.append("</row>")

        // Data Rows
        records.forEachIndexed { idx, rec ->
            val rowNum = idx + 2
            val zebra = (rowNum % 2) == 1
            val sLeft = if (zebra) 5 else 2
            val sCenter = if (zebra) 6 else 3
            val sNum = if (zebra) 7 else 4

            sb.append("""<row r="$rowNum" ht="20" customHeight="1">""")
            sb.append("""<c r="A$rowNum" s="$sCenter"><v>${rec.srNo}</v></c>""")
            sb.append("""<c r="B$rowNum" t="inlineStr" s="$sLeft"><is><t>${xmlEscape(rec.name)}</t></is></c>""")
            sb.append("""<c r="C$rowNum" s="$sNum"><v>${rec.totalPrice.toPlainString()}</v></c>""")
            sb.append("""<c r="D$rowNum" t="inlineStr" s="$sCenter"><is><t>${xmlEscape(rec.lessPriceDisplay)}</t></is></c>""")
            sb.append("""<c r="E$rowNum" s="$sNum"><v>${rec.realPrice.toPlainString()}</v></c>""")
            sb.append("""<c r="F$rowNum" t="inlineStr" s="$sCenter"><is><t>${xmlEscape(rec.size)}</t></is></c>""")
            sb.append("""<c r="G$rowNum" t="inlineStr" s="$sLeft"><is><t>${xmlEscape(rec.categoryType)}</t></is></c>""")
            sb.append("</row>")
        }
        sb.append("</sheetData>")
        sb.append("""<autoFilter ref="A1:G$maxRow"/>""")
        sb.append("</worksheet>")
        return sb.toString()
    }

    private fun computeColWidths(records: List<ProductRecord>): List<Int> {
        val maxName = maxOf(12, records.maxOfOrNull { it.name.length } ?: 12)
        val maxSize = maxOf(6, records.maxOfOrNull { it.size.length } ?: 6)
        val maxType = maxOf(10, records.maxOfOrNull { it.categoryType.length } ?: 10)
        return listOf(
            10,
            (maxName + 4).coerceIn(28, 48),
            14,
            12,
            14,
            (maxSize + 4).coerceIn(12, 26),
            (maxType + 4).coerceIn(18, 28),
        )
    }
}
