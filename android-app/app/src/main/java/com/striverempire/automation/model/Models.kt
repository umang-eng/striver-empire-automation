package com.striverempire.automation.model

import java.io.File
import java.math.BigDecimal

data class ParsedTask(
    val rawMessage: String,
    val category: String,
    val discountPercent: BigDecimal,
) {
    val discountDisplay: String
        get() {
            val stripped = discountPercent.stripTrailingZeros().toPlainString()
            return "$stripped%"
        }
}

data class SubcategoryTarget(
    val name: String,
    val url: String,
    val parentName: String = "",
)

data class ProductCandidate(
    val url: String,
    val nameHint: String = "",
    val subcategory: String = "",
    val parentCategory: String = "",
)

data class ProductRecord(
    val srNo: Int,
    val name: String,
    val totalPrice: BigDecimal,
    val discountPercent: BigDecimal,
    val realPrice: BigDecimal,
    val size: String,
    val categoryType: String,
    val url: String,
) {
    val lessPriceDisplay: String
        get() = "${discountPercent.stripTrailingZeros().toPlainString()}%"
}

data class FailedProduct(
    val url: String,
    val nameHint: String,
    val reason: String,
    val subcategory: String = "",
)

data class CategorySubItem(
    val name: String,
    val template: String,
)

data class CategoryGroup(
    val id: String,
    val label: String,
    val mainTemplates: List<String>,
    val subcategories: List<CategorySubItem>,
)

enum class TaskRunStatus {
    IDLE,
    RUNNING,
    COMPLETED,
    FAILED,
}

data class TaskUiState(
    val status: TaskRunStatus = TaskRunStatus.IDLE,
    val rawMessage: String = "",
    val category: String = "",
    val discountDisplay: String = "",
    val stage: String = "Validating task",
    val stageIndex: Int = 1,
    val totalStages: Int = 11,
    val progressPercent: Int = 0,
    val productsDiscovered: Int = 0,
    val productsExtracted: Int = 0,
    val failedProducts: Int = 0,
    val currentSubcategory: String = "",
    val elapsedSeconds: Long = 0L,
    val excelFile: File? = null,
    val pdfFile: File? = null,
    val excelFilename: String = "",
    val pdfFilename: String = "",
    val warnings: List<String> = emptyList(),
    val failures: List<FailedProduct> = emptyList(),
    val errorMessage: String? = null,
)

val PROGRESS_STAGES = listOf(
    "Validating task",
    "Opening website",
    "Discovering subcategories",
    "Collecting product URLs",
    "Extracting product details",
    "Detecting sizes",
    "Categorizing products",
    "Calculating discounted prices",
    "Generating Excel",
    "Generating PDF",
    "Saving generated files",
)
