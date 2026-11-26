package com.striverempire.automation.scraper

import com.striverempire.automation.model.FailedProduct
import com.striverempire.automation.model.ParsedTask
import com.striverempire.automation.model.ProductCandidate
import com.striverempire.automation.model.ProductRecord
import com.striverempire.automation.model.SubcategoryTarget
import com.striverempire.automation.processor.PriceCalculator
import com.striverempire.automation.processor.PriceParseException
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import org.jsoup.Jsoup
import java.io.IOException
import java.math.BigDecimal
import java.net.URLDecoder
import java.util.concurrent.TimeUnit

class BlockedAccessException(message: String) : Exception(message)
class CategoryNotFoundException(message: String) : Exception(message)
class CategoryAmbiguityException(message: String) : Exception(message)

class StriverScraper {
    companion object {
        const val BASE_URL = "https://striverempire.com"
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"

        private val blockKeywords = listOf(
            "cf-browser-verification",
            "verify you are human",
            "attention required! | cloudflare",
            "just a moment...",
            "g-recaptcha",
            "hcaptcha",
            "access denied",
        )

        private val emptySizeTokens = setOf("", "na", "n/a", "none", "null", "-", "--")
        private val connectorWords = setOf("and", "or", "of", "for", "the", "in", "on", "to", "with", "&")

        private val specSizeRegex = Regex(
            """(?:^|\n|\b)(?:size|volume|quantity|qty|net\s*wt\.?|net\s*weight|weight|pack\s*size)\s*[:\-]\s*([^\n\r;|]{1,40})""",
            RegexOption.IGNORE_CASE,
        )
        private val unitRegex = Regex(
            """\b(\d+(?:\.\d+)?\s*(?:ml|mL|l|L|ltr|g|gm|gms|kg|mg|oz|pcs|pieces|capsules|tablets))\b"""
        )

        private val mainCategoryAliases = mapOf(
            "men" to ("Men's" to "$BASE_URL/product/list/mens"),
            "mens" to ("Men's" to "$BASE_URL/product/list/mens"),
            "men's" to ("Men's" to "$BASE_URL/product/list/mens"),
            "women" to ("Women's" to "$BASE_URL/product/list/womens"),
            "womens" to ("Women's" to "$BASE_URL/product/list/womens"),
            "women's" to ("Women's" to "$BASE_URL/product/list/womens"),
            "beauty and cosmetics" to ("Beauty and cosmetics" to "$BASE_URL/product/list/beauty-and-cosmetics"),
            "beauty & cosmetics" to ("Beauty and cosmetics" to "$BASE_URL/product/list/beauty-and-cosmetics"),
            "beauty" to ("Beauty and cosmetics" to "$BASE_URL/product/list/beauty-and-cosmetics"),
            "accessories" to ("Accessories" to "$BASE_URL/product/list/accessories"),
            "accessory" to ("Accessories" to "$BASE_URL/product/list/accessories"),
            "winter" to ("Winter" to "$BASE_URL/product/list/winter"),
            "home and living" to ("Home & living" to "$BASE_URL/product/list/home-living"),
            "home & living" to ("Home & living" to "$BASE_URL/product/list/home-living"),
            "home living" to ("Home & living" to "$BASE_URL/product/list/home-living"),
        )
    }

    private val cookieStore = mutableMapOf<String, MutableList<Cookie>>()

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(25, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(25, TimeUnit.SECONDS)
        .cookieJar(object : CookieJar {
            override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
                val hostList = cookieStore.getOrPut(url.host) { mutableListOf() }
                for (c in cookies) {
                    hostList.removeAll { it.name == c.name }
                    hostList.add(c)
                }
            }

            override fun loadForRequest(url: HttpUrl): List<Cookie> {
                val now = System.currentTimeMillis()
                val hostList = cookieStore[url.host] ?: return emptyList()
                hostList.removeAll { it.expiresAt < now }
                return hostList.toList()
            }
        })
        .build()

    fun canonicalizeUrl(rawUrl: String): String {
        val trimmed = rawUrl.trim()
        val abs = when {
            trimmed.startsWith("http://") || trimmed.startsWith("https://") -> trimmed
            trimmed.startsWith("/") -> "$BASE_URL$trimmed"
            else -> "$BASE_URL/$trimmed"
        }
        val withoutFrag = abs.substringBefore("#").substringBefore("?").trimEnd('/')
        return withoutFrag.replace("https://STRIVEREMPIRE.com", BASE_URL, ignoreCase = true)
    }

    fun normalizeKey(text: String): String {
        return text.lowercase()
            .replace("&", " and ")
            .replace("-", " ")
            .replace("'", "")
            .replace("’", "")
            .replace(".", "")
            .replace(",", "")
            .replace(Regex("[^a-z0-9\\s]+"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }

    fun formatSubcategoryLabel(rawName: String): String {
        val cleaned = rawName.trim().trimEnd('.', ',').replace(Regex("\\s+"), " ")
        if (cleaned.isEmpty()) return "NA"
        return cleaned.split(" ").mapIndexed { idx, w ->
            val low = w.lowercase()
            when {
                idx > 0 && low in connectorWords -> if (low == "&") "and" else low
                w.all { it.isLowerCase() } -> w.take(1).uppercase() + w.drop(1)
                else -> w
            }
        }.joinToString(" ")
    }

    private fun checkForBlock(statusCode: Int, html: String, url: String) {
        if (statusCode in listOf(401, 403, 429)) {
            throw BlockedAccessException("Access blocked with HTTP $statusCode at $url.")
        }
        val lower = html.lowercase()
        for (kw in blockKeywords) {
            if (kw in lower) {
                throw BlockedAccessException("Detected anti-bot or CAPTCHA gate ('$kw') at $url.")
            }
        }
    }

    private fun getWithRetry(url: String, maxRetries: Int = 3): String {
        var lastErr: Exception? = null
        for (attempt in 1..maxRetries) {
            try {
                val req = Request.Builder()
                    .url(url)
                    .header("User-Agent", USER_AGENT)
                    .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                    .get()
                    .build()
                client.newCall(req).execute().use { resp ->
                    val body = resp.body?.string() ?: ""
                    checkForBlock(resp.code, body, url)
                    if (!resp.isSuccessful) {
                        throw IOException("HTTP ${resp.code} while loading $url")
                    }
                    return body
                }
            } catch (e: BlockedAccessException) {
                throw e
            } catch (e: Exception) {
                lastErr = e
                if (attempt < maxRetries) {
                    Thread.sleep(900L * attempt)
                }
            }
        }
        throw IOException("Failed to load $url after $maxRetries attempts: ${lastErr?.message}", lastErr)
    }

    private fun currentXsrfHeader(): String? {
        val cookies = cookieStore["striverempire.com"] ?: return null
        val xsrf = cookies.firstOrNull { it.name == "XSRF-TOKEN" }?.value ?: return null
        return try {
            URLDecoder.decode(xsrf, "UTF-8")
        } catch (_: Exception) {
            xsrf
        }
    }

    private fun postFilterProducts(apiUrl: String, categoryId: Int): JSONObject {
        var lastErr: Exception? = null
        for (attempt in 1..3) {
            try {
                val payload = JSONObject().put("categoryId", categoryId).toString()
                val reqBuilder = Request.Builder()
                    .url(apiUrl)
                    .header("User-Agent", USER_AGENT)
                    .header("Accept", "application/json, text/plain, */*")
                    .header("Content-Type", "application/json")
                    .header("X-Requested-With", "XMLHttpRequest")
                    .post(payload.toRequestBody("application/json; charset=utf-8".toMediaType()))
                currentXsrfHeader()?.let { reqBuilder.header("X-XSRF-TOKEN", it) }

                client.newCall(reqBuilder.build()).execute().use { resp ->
                    val body = resp.body?.string() ?: ""
                    checkForBlock(resp.code, body, apiUrl)
                    if (!resp.isSuccessful) {
                        throw IOException("HTTP ${resp.code} from $apiUrl")
                    }
                    return JSONObject(body)
                }
            } catch (e: BlockedAccessException) {
                throw e
            } catch (e: Exception) {
                lastErr = e
                if (attempt < 3) Thread.sleep(900L * attempt)
            }
        }
        throw IOException("Failed calling $apiUrl: ${lastErr?.message}", lastErr)
    }

    fun extractCategoryTreeFromHomepage(html: String): Map<String, List<SubcategoryTarget>> {
        val doc = Jsoup.parse(html, BASE_URL)
        val tree = linkedMapOf<String, List<SubcategoryTarget>>()
        for (li in doc.select("header li.dropdown")) {
            val topA = li.selectFirst("> a") ?: continue
            val parentLabel = topA.text().trim().replace(Regex("\\s+"), " ")
            if (parentLabel.isEmpty()) continue
            val subs = mutableListOf<SubcategoryTarget>()
            val seen = mutableSetOf<String>()
            for (subA in li.select("ul.dropdown-menu a.dropdown-item[href*=/product/list/]")) {
                val href = subA.attr("href").trim()
                if (href.isEmpty()) continue
                val canon = canonicalizeUrl(href)
                if (!seen.add(canon)) continue
                val subName = subA.text().trim().replace(Regex("\\s+"), " ")
                    .ifEmpty { canon.substringAfterLast("/") }
                subs.add(
                    SubcategoryTarget(
                        name = formatSubcategoryLabel(subName),
                        url = canon,
                        parentName = parentLabel,
                    )
                )
            }
            if (subs.isNotEmpty()) {
                tree[parentLabel] = subs
            }
        }
        return tree
    }

    private fun extractSidebarSubcategories(html: String, parentName: String): List<SubcategoryTarget> {
        val doc = Jsoup.parse(html, BASE_URL)
        // Striver Empire embeds sideCategories JSON inside script tags and renders via Vue
        val sideCatsRegex = Regex("""sideCategories\s*:\s*(\[[^\n\r]*\])""")
        val match = sideCatsRegex.find(html)
        if (match != null) {
            try {
                val arr = org.json.JSONArray(match.groupValues[1])
                val out = mutableListOf<SubcategoryTarget>()
                val seen = mutableSetOf<String>()
                for (i in 0 until arr.length()) {
                    val obj = arr.getJSONObject(i)
                    val url = canonicalizeUrl(obj.optString("url", ""))
                    val name = obj.optString("name", "")
                    if (url.isNotEmpty() && seen.add(url)) {
                        out.add(
                            SubcategoryTarget(
                                name = formatSubcategoryLabel(name.ifEmpty { url.substringAfterLast("/") }),
                                url = url,
                                parentName = parentName,
                            )
                        )
                    }
                }
                if (out.isNotEmpty()) return out
            } catch (_: Exception) {
                // Fallback to anchor tags
            }
        }

        val fallback = mutableListOf<SubcategoryTarget>()
        val seen = mutableSetOf<String>()
        for (a in doc.select("#filterSidebar a.nav-link[href*=/product/list/]")) {
            val href = a.attr("href").trim()
            if (href.isEmpty()) continue
            val canon = canonicalizeUrl(href)
            if (seen.add(canon)) {
                fallback.add(
                    SubcategoryTarget(
                        name = formatSubcategoryLabel(a.text()),
                        url = canon,
                        parentName = parentName,
                    )
                )
            }
        }
        return fallback
    }

    private fun extractCategoryId(html: String): Int? {
        val m = Regex("""category\s*:\s*\{[^}]*"id"\s*:\s*(\d+)""").find(html)
        return m?.groupValues?.get(1)?.toIntOrNull()
    }

    private fun matchSubcategoriesInScope(
        subQuery: String,
        subs: List<SubcategoryTarget>,
    ): List<SubcategoryTarget> {
        val normQ = normalizeKey(subQuery)
        val exact = subs.filter {
            val slug = it.url.substringAfterLast("/")
            normalizeKey(it.name) == normQ || normalizeKey(slug) == normQ
        }
        if (exact.isNotEmpty()) return exact

        val alt = if (normQ.endsWith("s")) normQ.dropLast(1) else "${normQ}s"
        val plural = subs.filter {
            val slug = it.url.substringAfterLast("/")
            normalizeKey(it.name) == alt || normalizeKey(slug) == alt
        }
        if (plural.isNotEmpty()) return plural

        val partial = subs.filter {
            val nk = normalizeKey(it.name)
            normQ in nk || nk in normQ
        }.sortedBy { kotlin.math.abs(normalizeKey(it.name).length - normQ.length) }
        return if (partial.isNotEmpty()) listOf(partial.first()) else emptyList()
    }

    fun resolveTargets(requestedCategory: String): Triple<String, List<SubcategoryTarget>, Boolean> {
        val homeHtml = getWithRetry(BASE_URL)
        val tree = extractCategoryTreeFromHomepage(homeHtml)

        val normReq = normalizeKey(requestedCategory)
        val normalizedMainMap = mainCategoryAliases.mapKeys { normalizeKey(it.key) }

        // 1. Direct match to a main category
        normalizedMainMap[normReq]?.let { (parentLabel, parentUrl) ->
            val mainHtml = getWithRetry(parentUrl)
            val sidebarSubs = extractSidebarSubcategories(mainHtml, parentLabel)
            val subs = sidebarSubs.ifEmpty {
                tree.entries.firstOrNull { normalizeKey(it.key) == normalizeKey(parentLabel) }?.value
                    ?: listOf(SubcategoryTarget(formatSubcategoryLabel(parentLabel), parentUrl, parentLabel))
            }
            return Triple(parentUrl, subs, true)
        }

        // 2. Parent-qualified subcategory (e.g. "women formal pant", "men shirt")
        val reqWords = normReq.split(" ")
        val sortedAliases = normalizedMainMap.keys.sortedByDescending { it.split(" ").size }
        for (alias in sortedAliases) {
            val aliasWords = alias.split(" ")
            if (reqWords.size > aliasWords.size && reqWords.take(aliasWords.size) == aliasWords) {
                val (parentLabel, parentUrl) = normalizedMainMap.getValue(alias)
                val subQuery = reqWords.drop(aliasWords.size).joinToString(" ")
                val mainHtml = getWithRetry(parentUrl)
                val subs = extractSidebarSubcategories(mainHtml, parentLabel).ifEmpty {
                    tree.entries.firstOrNull { normalizeKey(it.key) == normalizeKey(parentLabel) }?.value.orEmpty()
                }
                val matched = matchSubcategoriesInScope(subQuery, subs)
                if (matched.size == 1) {
                    return Triple(matched.first().url, matched, false)
                }
                if (matched.size > 1) {
                    val opts = matched.joinToString(", ") { "${it.parentName} -> ${it.name}" }
                    throw CategoryAmbiguityException("Category '$requestedCategory' matched multiple subcategories: $opts.")
                }
            }
        }

        // 3. Unqualified subcategory across all parents
        val allSubs = tree.values.flatten()
        val distinct = matchSubcategoriesInScope(normReq, allSubs).distinctBy { it.url }
        if (distinct.size == 1) {
            return Triple(distinct.first().url, distinct, false)
        }
        if (distinct.size > 1) {
            val opts = distinct.joinToString(", ") { "${it.parentName} -> ${it.name}" }
            throw CategoryAmbiguityException("Subcategory '$requestedCategory' is ambiguous: $opts. Please prefix with Men or Women.")
        }

        throw CategoryNotFoundException("Category '$requestedCategory' could not be matched on $BASE_URL.")
    }

    fun collectProductsForTargets(
        targets: List<SubcategoryTarget>,
        onProgress: (subcategory: String, subIndex: Int, subTotal: Int, discovered: Int) -> Unit,
    ): Pair<List<ProductCandidate>, List<String>> {
        val ordered = mutableListOf<ProductCandidate>()
        val seenByUrl = mutableMapOf<String, String>()
        val warnings = mutableListOf<String>()

        targets.forEachIndexed { idx, target ->
            onProgress(target.name, idx + 1, targets.size, ordered.size)
            val html = getWithRetry(target.url)
            val catId = extractCategoryId(html)
                ?: throw IOException("Could not find categoryId on ${target.url}")

            var nextUrl: String? = "$BASE_URL/product/filter-products"
            var pageCount = 0
            while (nextUrl != null && pageCount < 100) {
                pageCount++
                val json = postFilterProducts(nextUrl, catId)
                val productsObj = json.optJSONObject("products") ?: break
                val dataArr = productsObj.optJSONArray("data") ?: break

                var newOnPage = 0
                for (i in 0 until dataArr.length()) {
                    val item = dataArr.getJSONObject(i)
                    val detailUrl = canonicalizeUrl(item.optString("detailUrl", ""))
                    if (detailUrl.isEmpty() || "/product/detail/" !in detailUrl) continue
                    if (detailUrl in seenByUrl) {
                        val existingType = seenByUrl.getValue(detailUrl)
                        if (existingType != target.name) {
                            warnings.add("Duplicate product URL $detailUrl kept under '$existingType' (also in '${target.name}').")
                        }
                        continue
                    }
                    seenByUrl[detailUrl] = target.name
                    ordered.add(
                        ProductCandidate(
                            url = detailUrl,
                            nameHint = item.optString("name", ""),
                            subcategory = target.name,
                            parentCategory = target.parentName,
                        )
                    )
                    newOnPage++
                }

                val meta = productsObj.optJSONObject("meta")
                val rawNext = meta?.optString("next_page_url", "")?.takeIf { it.isNotBlank() && it != "null" }
                nextUrl = if (newOnPage > 0) rawNext else null
            }
            onProgress(target.name, idx + 1, targets.size, ordered.size)
        }

        return ordered to warnings
    }

    fun parseProductDetailHtml(html: String, url: String): Triple<String, BigDecimal, String> {
        val doc = Jsoup.parse(html, url)
        val name = doc.selectFirst("h1, .product-title, [itemprop=name]")
            ?.text()?.trim()?.replace(Regex("\\s+"), " ")
            ?.takeIf { it.isNotEmpty() }
            ?: throw IOException("Missing product name at $url")

        val price = extractSellingPrice(doc, url)
        val size = extractSize(doc, name)
        return Triple(name, price, size)
    }

    private fun extractSellingPrice(doc: org.jsoup.nodes.Document, url: String): BigDecimal {
        doc.selectFirst("span[id^=category_dp_]")?.text()?.trim()?.takeIf { it.isNotEmpty() }?.let {
            return PriceCalculator.parsePrice(it)
        }

        for (sel in listOf("div.h4.d-flex.align-items-center", ".product-price", "[itemprop=price]")) {
            val container = doc.selectFirst(sel) ?: continue
            val clone = container.clone()
            clone.select("del, small, s").remove()
            val txt = clone.text().trim().replace(Regex("\\s+"), " ")
            if (txt.isNotEmpty()) {
                try {
                    return PriceCalculator.parsePrice(txt)
                } catch (_: PriceParseException) {
                }
            }
        }

        val radioDp = doc.selectFirst("input.CategoryPricesSelect:checked[data-dp]")?.attr("data-dp")
            ?: doc.selectFirst("input.CategoryPricesSelect[data-dp]")?.attr("data-dp")
        if (!radioDp.isNullOrBlank()) {
            return PriceCalculator.parsePrice(radioDp)
        }

        val selectDp = doc.selectFirst("select[id^=PricesSelect_] option[selected][data-dp]")?.attr("data-dp")
            ?: doc.selectFirst("select[id^=PricesSelect_] option[data-dp]")?.attr("data-dp")
        if (!selectDp.isNullOrBlank()) {
            return PriceCalculator.parsePrice(selectDp)
        }

        throw PriceParseException("Displayed selling price missing at $url")
    }

    private fun extractSize(doc: org.jsoup.nodes.Document, productName: String): String {
        val sizes = mutableListOf<String>()
        val seen = mutableSetOf<String>()

        fun addSize(raw: String) {
            val cleaned = raw.trim().replace(Regex("\\s+"), " ")
            val low = cleaned.lowercase()
            if (low in emptySizeTokens) return
            if (seen.add(low)) sizes.add(cleaned)
        }

        for (radio in doc.select("input.CategoryPricesSelect")) {
            val id = radio.attr("id")
            if (id.isNotEmpty()) {
                doc.selectFirst("label[for=$id]")?.text()?.let(::addSize)
            } else if (radio.hasAttr("data-size")) {
                addSize(radio.attr("data-size"))
            }
        }

        if (sizes.isEmpty()) {
            for (opt in doc.select("select[id^=PricesSelect_] option")) {
                if (opt.hasAttr("disabled")) continue
                val txt = opt.text().trim()
                if ("select" in txt.lowercase()) continue
                addSize(txt)
            }
        }

        if (sizes.isNotEmpty()) {
            return sizes.joinToString(", ")
        }

        val desc = listOf("#description-tab", "#specification-tab", ".product-details", "ul.list-unstyled")
            .mapNotNull { doc.selectFirst(it)?.text() }
            .joinToString("\n")

        specSizeRegex.find(desc)?.groupValues?.get(1)?.trim(' ', '.', ',', ':', ';', '-')?.let { cand ->
            if (cand.lowercase() !in emptySizeTokens) return cand
        }

        for (src in listOf(productName, desc)) {
            unitRegex.find(src)?.groupValues?.get(1)?.let {
                return it.replace(Regex("\\s+"), " ").trim()
            }
        }
        return "NA"
    }

    fun scrapeAllProducts(
        candidates: List<ProductCandidate>,
        task: ParsedTask,
        isCancelled: () -> Boolean,
        onProgress: (index: Int, total: Int, extracted: Int, failed: Int, subcategory: String, phase: String) -> Unit,
    ): Pair<List<ProductRecord>, List<FailedProduct>> {
        val records = mutableListOf<ProductRecord>()
        val failures = mutableListOf<FailedProduct>()
        val total = candidates.size

        candidates.forEachIndexed { idx, candidate ->
            if (isCancelled()) throw InterruptedException("Cancelled")
            val subLabel = candidate.subcategory.ifBlank { task.category }
            onProgress(idx + 1, total, records.size, failures.size, subLabel, "extracting")
            if (idx > 0) Thread.sleep(150)

            try {
                val html = getWithRetry(candidate.url)
                val (name, totalPrice, size) = parseProductDetailHtml(html, candidate.url)
                val record = PriceCalculator.buildRecord(
                    srNo = records.size + 1,
                    name = name,
                    totalPrice = totalPrice,
                    discountPercent = task.discountPercent,
                    size = size,
                    categoryType = subLabel,
                    url = candidate.url,
                )
                records.add(record)
                onProgress(idx + 1, total, records.size, failures.size, subLabel, "calculated")
            } catch (e: BlockedAccessException) {
                throw e
            } catch (e: Exception) {
                failures.add(
                    FailedProduct(
                        url = candidate.url,
                        nameHint = candidate.nameHint.ifBlank { "Unknown" },
                        reason = e.message ?: "Extraction failed",
                        subcategory = subLabel,
                    )
                )
                onProgress(idx + 1, total, records.size, failures.size, subLabel, "failed_item")
            }
        }
        return records to failures
    }
}
