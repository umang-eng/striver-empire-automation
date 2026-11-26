package com.striverempire.automation.processor

import com.striverempire.automation.model.ParsedTask
import com.striverempire.automation.model.SubcategoryTarget
import java.io.File
import java.math.BigDecimal

class TaskParseException(message: String) : Exception(message)

object MessageParser {
    private val lowercaseConnectors = setOf("and", "or", "of", "for", "the", "in", "on", "to", "with", "&")

    private val discountPatterns = listOf(
        Regex("""(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*%\s*(?:off|discount)?""", RegexOption.IGNORE_CASE),
        Regex("""(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*(?:percent|pct)\b(?:\s*off)?""", RegexOption.IGNORE_CASE),
        Regex("""(?:^|[\s,\-|])(-?\d+(?:\.\d+)?)\s*$"""),
    )

    private val mainDisplayAliases = mapOf(
        "men" to "Men's",
        "mens" to "Men's",
        "men's" to "Men's",
        "women" to "Women's",
        "womens" to "Women's",
        "women's" to "Women's",
        "beauty and cosmetics" to "Beauty and Cosmetics",
        "beauty & cosmetics" to "Beauty and Cosmetics",
        "beauty" to "Beauty and Cosmetics",
        "accessories" to "Accessories",
        "accessory" to "Accessories",
        "winter" to "Winter",
        "home and living" to "Home & Living",
        "home & living" to "Home & Living",
        "home living" to "Home & Living",
    )

    fun parse(rawInput: String): ParsedTask {
        val cleaned = rawInput.trim().replace(Regex("\\s+"), " ")
        if (cleaned.isEmpty()) {
            throw TaskParseException("Enter a category and discount, e.g. women 25%.")
        }

        for (pattern in discountPatterns) {
            val matches = pattern.findAll(cleaned).toList()
            if (matches.isEmpty()) continue
            val match = matches.last()
            val rawNum = match.groupValues[1]
            val discount = rawNum.toBigDecimalOrNull()
                ?: throw TaskParseException("Invalid discount value \"$rawNum\".")

            if (discount < BigDecimal.ZERO || discount >= BigDecimal("100")) {
                throw TaskParseException("Discount must be at least 0% and less than 100%.")
            }

            val before = cleaned.substring(0, match.range.first)
            val after = cleaned.substring(match.range.last + 1)
            val remaining = "$before $after"
                .replace(Regex("""\b(discount|off)\b""", RegexOption.IGNORE_CASE), "")
                .trim(' ', ',', '-', '|', ';')
                .replace(Regex("\\s+"), " ")

            if (remaining.isEmpty()) {
                throw TaskParseException("Category name is required before the discount (e.g. women 25%).")
            }

            return ParsedTask(
                rawMessage = rawInput.trim(),
                category = formatCategoryLabel(remaining),
                discountPercent = discount,
            )
        }

        throw TaskParseException("Include a numeric discount percentage (e.g. women 25% or men formal pants 12.5%).")
    }

    fun formatCategoryLabel(category: String): String {
        val words = category.trim().trimEnd('.', ',').split(Regex("\\s+")).filter { it.isNotEmpty() }
        return words.mapIndexed { idx, word ->
            val low = word.lowercase()
            when {
                idx > 0 && low in lowercaseConnectors -> if (low == "&") "and" else low
                "-" in word -> word.split("-").joinToString("-") { part ->
                    if (part.isEmpty()) "" else part.take(1).uppercase() + part.drop(1).lowercase()
                }
                "'" in word || "’" in word -> {
                    val sep = if ("'" in word) "'" else "’"
                    val (head, tail) = word.split(sep, limit = 2)
                    "${head.take(1).uppercase()}${head.drop(1).lowercase()}$sep${tail.lowercase()}"
                }
                else -> word.take(1).uppercase() + word.drop(1).lowercase()
            }
        }.joinToString(" ")
    }

    fun formatDisplayCategoryForFilename(category: String): String {
        val raw = category.trim().trimEnd('.', ',').replace(Regex("\\s+"), " ")
        val low = raw.lowercase()
        mainDisplayAliases[low]?.let { return it }

        val words = raw.split(" ")
        for (prefixLen in listOf(3, 2, 1)) {
            if (words.size > prefixLen) {
                val head = words.take(prefixLen).joinToString(" ").lowercase()
                val mapped = mainDisplayAliases[head]
                if (mapped != null) {
                    val tail = formatCategoryLabel(words.drop(prefixLen).joinToString(" "))
                    return "$mapped $tail"
                }
            }
        }
        return formatCategoryLabel(raw)
    }

    fun resolveFilenameCategoryLabel(
        task: ParsedTask,
        targets: List<SubcategoryTarget>,
        isParentCategory: Boolean,
    ): String {
        if (targets.isNotEmpty()) {
            if (isParentCategory) {
                val parent = targets.first().parentName.ifBlank { task.category }
                return formatDisplayCategoryForFilename(parent)
            }
            if (targets.size == 1) {
                val sub = targets.first()
                val parentDisp = if (sub.parentName.isNotBlank()) formatDisplayCategoryForFilename(sub.parentName) else ""
                val subDisp = sub.name.trim()
                if (parentDisp.isNotBlank()) {
                    val parentRoot = parentDisp.lowercase().replace("'s", "").replace(Regex("[^a-z0-9]"), "")
                    val subRoot = subDisp.lowercase().replace(Regex("[^a-z0-9]"), "")
                    if (parentRoot.isNotEmpty() && parentRoot in subRoot) {
                        return subDisp
                    }
                    return "$parentDisp $subDisp"
                }
                return subDisp
            }
        }
        return formatDisplayCategoryForFilename(task.category)
    }

    fun buildOutputStem(task: ParsedTask, displayCategory: String? = null): String {
        val rawLabel = displayCategory ?: formatDisplayCategoryForFilename(task.category)
        val sanitized = rawLabel
            .replace(Regex("""[\\/:*?"<>|]+"""), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
            .ifEmpty { "Report" }
        return "$sanitized ${task.discountDisplay}"
    }

    fun resolveUniqueOutputFiles(
        excelDir: File,
        pdfDir: File,
        stem: String,
    ): Pair<File, File> {
        excelDir.mkdirs()
        pdfDir.mkdirs()
        var excelFile = File(excelDir, "$stem.xlsx")
        var pdfFile = File(pdfDir, "$stem.pdf")
        if (!excelFile.exists() && !pdfFile.exists()) {
            return excelFile to pdfFile
        }
        var idx = 2
        while (true) {
            excelFile = File(excelDir, "$stem ($idx).xlsx")
            pdfFile = File(pdfDir, "$stem ($idx).pdf")
            if (!excelFile.exists() && !pdfFile.exists()) {
                return excelFile to pdfFile
            }
            idx++
        }
    }
}
