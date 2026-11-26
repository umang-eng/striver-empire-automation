package com.striverempire.automation.processor

import com.striverempire.automation.model.ProductRecord
import java.math.BigDecimal
import java.math.RoundingMode

class PriceParseException(message: String) : Exception(message)

object PriceCalculator {
    private val currencyNoiseRegex = Regex(
        """(?:₹|र|rs\.?|inr|\$|€|£|\(inclusive of all taxes\))""",
        RegexOption.IGNORE_CASE,
    )
    private val numberRegex = Regex("""[-+]?\d[\d,]*(?:\.\d+)?""")

    fun parsePrice(rawValue: String): BigDecimal {
        val cleaned = currencyNoiseRegex.replace(rawValue, " ").trim()
        val matches = numberRegex.findAll(cleaned).map { it.value }.toList()
        if (matches.isEmpty()) {
            throw PriceParseException("No numeric price found in '$rawValue'")
        }
        if (matches.size > 1) {
            throw PriceParseException("Ambiguous numeric values in price '$rawValue'")
        }
        val numStr = matches.first().replace(",", "")
        val value = numStr.toBigDecimalOrNull()
            ?: throw PriceParseException("Invalid numeric price '$rawValue'")
        if (value <= BigDecimal.ZERO) {
            throw PriceParseException("Price must be greater than zero, got $value")
        }
        return value.setScale(2, RoundingMode.HALF_UP)
    }

    fun calculateRealPrice(totalPrice: BigDecimal, discountPercent: BigDecimal): BigDecimal {
        val multiplier = BigDecimal.ONE.subtract(
            discountPercent.divide(BigDecimal("100"), 10, RoundingMode.HALF_UP)
        )
        return totalPrice.multiply(multiplier).setScale(2, RoundingMode.HALF_UP)
    }

    fun buildRecord(
        srNo: Int,
        name: String,
        totalPrice: BigDecimal,
        discountPercent: BigDecimal,
        size: String,
        categoryType: String,
        url: String,
    ): ProductRecord {
        val scaledTotal = totalPrice.setScale(2, RoundingMode.HALF_UP)
        val realPrice = calculateRealPrice(scaledTotal, discountPercent)
        val cleanSize = size.trim().ifEmpty { "NA" }
        return ProductRecord(
            srNo = srNo,
            name = name.trim(),
            totalPrice = scaledTotal,
            discountPercent = discountPercent,
            realPrice = realPrice,
            size = cleanSize,
            categoryType = categoryType,
            url = url,
        )
    }
}
