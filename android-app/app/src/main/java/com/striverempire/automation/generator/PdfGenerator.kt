package com.striverempire.automation.generator

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import com.striverempire.automation.model.ProductRecord
import java.io.File
import java.io.FileOutputStream

object PdfGenerator {
    private const val PAGE_WIDTH = 842
    private const val PAGE_HEIGHT = 595
    private const val MARGIN_X = 22f
    private const val MARGIN_Y = 22f

    private fun fmtPrice(value: java.math.BigDecimal): String {
        return value.setScale(2, java.math.RoundingMode.HALF_UP).toPlainString()
    }

    fun generate(
        records: List<ProductRecord>,
        outputFile: File,
        headerHexRgb: String = HeaderColorPicker.pickReadableHex(),
    ): Pair<File, String?> {
        outputFile.parentFile?.mkdirs()
        val headerColor = Color.parseColor("#${headerHexRgb.removePrefix("#")}")
        val availW = PAGE_WIDTH - 2f * MARGIN_X
        val availH = PAGE_HEIGHT - 2f * MARGIN_Y

        val colWidths = computeColWidths(records, availW)
        val tableWidth = colWidths.sum()

        var chosenFont = 9.5f
        var chosenLayouts: List<RowMeasurement> = emptyList()
        var chosenTotalHeight = 0f

        var f = 9.5f
        while (f >= 5.5f - 0.01f) {
            val vPad = maxOf(1.2f, f * 0.45f)
            val hPad = maxOf(2.0f, f * 0.50f)
            val measured = measureTable(records, colWidths, f, hPad, vPad)
            val totalH = measured.sumOf { it.height.toDouble() }.toFloat()
            chosenFont = f
            chosenLayouts = measured
            chosenTotalHeight = totalH
            if (totalH <= availH) break
            f -= 0.5f
        }

        var scale = 1f
        var warning: String? = null
        if (chosenTotalHeight > availH) {
            val fullWidths = colWidths.map { it * (availW / tableWidth) }
            val measured = measureTable(records, fullWidths, 5.5f, 2.0f, 1.0f)
            val totalH = measured.sumOf { it.height.toDouble() }.toFloat()
            chosenLayouts = measured
            chosenTotalHeight = totalH
            scale = minOf(availW / fullWidths.sum(), availH / totalH, 1f)
            warning = "Dataset of ${records.size} product(s) scaled (${String.format("%.2f", scale)}x) to fit strictly onto 1 PDF page."
        }

        val finalColWidths = if (scale < 1f) {
            colWidths.map { it * (availW / tableWidth) }
        } else {
            colWidths
        }
        val finalTableW = finalColWidths.sum()

        val doc = PdfDocument()
        val pageInfo = PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, 1).create()
        val page = doc.startPage(pageInfo)
        val canvas = page.canvas

        val drawW = finalTableW * scale
        val originX = (PAGE_WIDTH - drawW) / 2f
        val originY = MARGIN_Y

        canvas.save()
        canvas.translate(originX, originY)
        if (scale < 1f) {
            canvas.scale(scale, scale)
        }

        drawTable(canvas, chosenLayouts, finalColWidths, headerColor)
        canvas.restore()

        doc.finishPage(page)
        FileOutputStream(outputFile).use { out ->
            doc.writeTo(out)
        }
        doc.close()
        return outputFile to warning
    }

    private data class RowMeasurement(
        val isHeader: Boolean,
        val cells: List<StaticLayout>,
        val height: Float,
        val hPad: Float,
        val vPad: Float,
    )

    private fun computeColWidths(records: List<ProductRecord>, availW: Float): List<Float> {
        val maxSr = maxOf(7, records.maxOfOrNull { it.srNo.toString().length } ?: 3)
        val maxName = maxOf(12, records.maxOfOrNull { it.name.length } ?: 12)
        val maxTp = maxOf(11, records.maxOfOrNull { fmtPrice(it.totalPrice).length } ?: 6)
        val maxLp = maxOf(10, records.maxOfOrNull { it.lessPriceDisplay.length } ?: 4)
        val maxRp = maxOf(10, records.maxOfOrNull { fmtPrice(it.realPrice).length } ?: 6)
        val maxSize = maxOf(4, records.maxOfOrNull { it.size.length } ?: 4)
        val maxType = maxOf(6, records.maxOfOrNull { it.categoryType.length } ?: 10)

        val weights = listOf(
            maxOf(maxSr + 2, 7),
            (maxName + 4).coerceIn(22, 52),
            maxOf(maxTp + 3, 12),
            maxOf(maxLp + 3, 10),
            maxOf(maxRp + 3, 12),
            (maxSize + 3).coerceIn(9, 22),
            (maxType + 4).coerceIn(15, 26),
        ).map { it.toFloat() }

        val sumW = weights.sum()
        val targetW = minOf(availW, maxOf(availW * 0.78f, sumW * 6.2f))
        return weights.map { targetW * (it / sumW) }
    }

    private fun measureTable(
        records: List<ProductRecord>,
        colWidths: List<Float>,
        fontSize: Float,
        hPad: Float,
        vPad: Float,
    ): List<RowMeasurement> {
        val bodyPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.BLACK
            textSize = fontSize
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL)
        }
        val headerSize = fontSize + if (fontSize >= 6.5f) 1.0f else 0.5f
        val headerPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.BLACK
            textSize = headerSize
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
        }

        val rows = mutableListOf<RowMeasurement>()

        fun makeCell(text: String, width: Float, paint: TextPaint, align: Layout.Alignment): StaticLayout {
            val innerW = maxOf(8, (width - 2f * hPad).toInt())
            return StaticLayout.Builder.obtain(text, 0, text.length, paint, innerW)
                .setAlignment(align)
                .setLineSpacing(0f, 1.12f)
                .setIncludePad(false)
                .build()
        }

        // Header row
        val hdrCells = ExcelGenerator.COLUMNS.mapIndexed { idx, title ->
            makeCell(title, colWidths[idx], headerPaint, Layout.Alignment.ALIGN_CENTER)
        }
        val hdrH = (hdrCells.maxOfOrNull { it.height.toFloat() } ?: headerSize) + 2f * vPad
        rows.add(RowMeasurement(isHeader = true, cells = hdrCells, height = hdrH, hPad = hPad, vPad = vPad))

        // Body rows
        for (rec in records) {
            val cells = listOf(
                makeCell(rec.srNo.toString(), colWidths[0], bodyPaint, Layout.Alignment.ALIGN_CENTER),
                makeCell(rec.name, colWidths[1], bodyPaint, Layout.Alignment.ALIGN_NORMAL),
                makeCell(fmtPrice(rec.totalPrice), colWidths[2], bodyPaint, Layout.Alignment.ALIGN_OPPOSITE),
                makeCell(rec.lessPriceDisplay, colWidths[3], bodyPaint, Layout.Alignment.ALIGN_CENTER),
                makeCell(fmtPrice(rec.realPrice), colWidths[4], bodyPaint, Layout.Alignment.ALIGN_OPPOSITE),
                makeCell(rec.size, colWidths[5], bodyPaint, Layout.Alignment.ALIGN_CENTER),
                makeCell(rec.categoryType, colWidths[6], bodyPaint, Layout.Alignment.ALIGN_NORMAL),
            )
            val rowH = (cells.maxOfOrNull { it.height.toFloat() } ?: fontSize) + 2f * vPad
            rows.add(RowMeasurement(isHeader = false, cells = cells, height = rowH, hPad = hPad, vPad = vPad))
        }
        return rows
    }

    private fun drawTable(
        canvas: Canvas,
        rows: List<RowMeasurement>,
        colWidths: List<Float>,
        headerColor: Int,
    ) {
        val totalW = colWidths.sum()
        val totalH = rows.sumOf { it.height.toDouble() }.toFloat()

        val headerBgPaint = Paint().apply {
            color = headerColor
            style = Paint.Style.FILL
        }
        val whiteBgPaint = Paint().apply {
            color = Color.WHITE
            style = Paint.Style.FILL
        }
        val zebraBgPaint = Paint().apply {
            color = Color.rgb(245, 245, 245)
            style = Paint.Style.FILL
        }
        val gridPaint = Paint().apply {
            color = Color.rgb(51, 51, 51)
            strokeWidth = 0.5f
            style = Paint.Style.STROKE
        }
        val borderPaint = Paint().apply {
            color = Color.BLACK
            strokeWidth = 1.0f
            style = Paint.Style.STROKE
        }

        var y = 0f
        rows.forEachIndexed { rowIdx, row ->
            val bgPaint = when {
                row.isHeader -> headerBgPaint
                rowIdx % 2 == 0 -> zebraBgPaint
                else -> whiteBgPaint
            }
            canvas.drawRect(0f, y, totalW, y + row.height, bgPaint)

            var x = 0f
            row.cells.forEachIndexed { colIdx, layout ->
                val cw = colWidths[colIdx]
                val cellTop = y + (row.height - layout.height) / 2f
                canvas.save()
                canvas.translate(x + row.hPad, cellTop)
                layout.draw(canvas)
                canvas.restore()
                x += cw
            }
            canvas.drawLine(0f, y + row.height, totalW, y + row.height, if (row.isHeader) borderPaint else gridPaint)
            y += row.height
        }

        // Vertical column grid lines
        var x = 0f
        for (i in 0 until colWidths.size - 1) {
            x += colWidths[i]
            canvas.drawLine(x, 0f, x, totalH, gridPaint)
        }

        // Outer black box
        canvas.drawRect(0f, 0f, totalW, totalH, borderPaint)
    }
}
