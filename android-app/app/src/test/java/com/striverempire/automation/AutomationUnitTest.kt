package com.striverempire.automation

import com.striverempire.automation.generator.ExcelGenerator
import com.striverempire.automation.model.ProductRecord
import com.striverempire.automation.model.SubcategoryTarget
import com.striverempire.automation.processor.MessageParser
import com.striverempire.automation.processor.PriceCalculator
import com.striverempire.automation.processor.TaskParseException
import com.striverempire.automation.scraper.StriverScraper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.math.BigDecimal
import java.util.zip.ZipFile

class AutomationUnitTest {
    @Test
    fun parseTaskMessagesAndFilenames() {
        val t1 = MessageParser.parse("women 25%")
        assertEquals("Women", t1.category)
        assertEquals(BigDecimal("25"), t1.discountPercent)
        assertEquals("Women's 25%", MessageParser.buildOutputStem(t1))

        val t2 = MessageParser.parse("men formal pants 12.5%")
        assertEquals("Men Formal Pants", t2.category)
        assertEquals(BigDecimal("12.5"), t2.discountPercent)
        assertEquals("Men's Formal Pants 12.5%", MessageParser.buildOutputStem(t2))

        val t3 = MessageParser.parse("home and living 5%")
        assertEquals("Home & Living 5%", MessageParser.buildOutputStem(t3))

        val sub = SubcategoryTarget("Formal Pant", "https://striverempire.com/product/list/formal-pant", "Women's")
        val label = MessageParser.resolveFilenameCategoryLabel(t1, listOf(sub), isParentCategory = false)
        assertEquals("Women's Formal Pant 25%", MessageParser.buildOutputStem(t1, label))
    }

    @Test(expected = TaskParseException::class)
    fun rejectHundredPercentDiscount() {
        MessageParser.parse("women 100%")
    }

    @Test(expected = TaskParseException::class)
    fun rejectMissingCategory() {
        MessageParser.parse("25%")
    }

    @Test
    fun parsePricesAndCalculateRealPrice() {
        assertEquals(BigDecimal("1699.00"), PriceCalculator.parsePrice("र 1,699"))
        assertEquals(BigDecimal("299.00"), PriceCalculator.parsePrice("Rs. 299.00 (Inclusive of all taxes)"))
        assertEquals(BigDecimal("749.25"), PriceCalculator.calculateRealPrice(BigDecimal("999.00"), BigDecimal("25")))
        assertEquals(BigDecimal("141.55"), PriceCalculator.calculateRealPrice(BigDecimal("149.00"), BigDecimal("5")))
    }

    @Test
    fun parseProductHtmlWithNaSize() {
        val html = """
            <html><body>
              <h1 class="h4">Neem Tulsi Aloevera Soap.</h1>
              <div class="h4 d-flex align-items-center"><del>र 199</del> र <span id="category_dp_1170">149</span></div>
              <input type="radio" class="CategoryPricesSelect" id="3180" data-dp="149">
              <label for="3180">NA</label>
            </body></html>
        """.trimIndent()
        val scraper = StriverScraper()
        val (name, price, size) = scraper.parseProductDetailHtml(html, "https://striverempire.com/product/detail/soap")
        assertEquals("Neem Tulsi Aloevera Soap.", name)
        assertEquals(BigDecimal("149.00"), price)
        assertEquals("NA", size)
    }

    @Test
    fun generateValidXlsxZipWithSevenColumns() {
        val tempFile = File.createTempFile("test_report", ".xlsx")
        tempFile.deleteOnExit()
        val records = listOf(
            ProductRecord(
                srNo = 1,
                name = "Women Black Shirt",
                totalPrice = BigDecimal("999.00"),
                discountPercent = BigDecimal("25"),
                realPrice = BigDecimal("749.25"),
                size = "L",
                categoryType = "Shirt's",
                url = "https://striverempire.com/product/detail/women-black-shirt",
            )
        )
        ExcelGenerator.generate(records, tempFile, "18B500")
        assertTrue(tempFile.length() > 500)
        ZipFile(tempFile).use { zip ->
            val sheetXml = zip.getInputStream(zip.getEntry("xl/worksheets/sheet1.xml")).bufferedReader().readText()
            assertTrue(sheetXml.contains("Sr. no."))
            assertTrue(sheetXml.contains("Women Black Shirt"))
            assertTrue(sheetXml.contains("749.25"))
            assertTrue(sheetXml.contains("Shirt&apos;s"))
        }
    }
}
