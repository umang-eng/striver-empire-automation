package com.striverempire.automation.viewmodel

import android.app.Application
import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.striverempire.automation.generator.ExcelGenerator
import com.striverempire.automation.generator.HeaderColorPicker
import com.striverempire.automation.generator.PdfGenerator
import com.striverempire.automation.model.TaskRunStatus
import com.striverempire.automation.model.TaskUiState
import com.striverempire.automation.processor.MessageParser
import com.striverempire.automation.scraper.StriverScraper
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val _inputValue = MutableStateFlow("")
    val inputValue: StateFlow<String> = _inputValue.asStateFlow()

    private val _uiState = MutableStateFlow(TaskUiState())
    val uiState: StateFlow<TaskUiState> = _uiState.asStateFlow()

    private val scraper = StriverScraper()
    private var activeJob: Job? = null
    private var timerJob: Job? = null
    private val cancelFlag = AtomicBoolean(false)

    fun updateInput(next: String) {
        _inputValue.value = next
    }

    fun selectTemplate(template: String) {
        _inputValue.value = template
        val status = _uiState.value.status
        if (status == TaskRunStatus.COMPLETED || status == TaskRunStatus.FAILED) {
            _uiState.value = TaskUiState()
        }
    }

    fun cancelTask() {
        cancelFlag.set(true)
        activeJob?.cancel()
        timerJob?.cancel()
        _uiState.value = TaskUiState()
    }

    fun resetToInput() {
        timerJob?.cancel()
        _uiState.value = TaskUiState()
    }

    fun submitTask() {
        if (_uiState.value.status == TaskRunStatus.RUNNING) return
        val raw = _inputValue.value
        val parsed = try {
            MessageParser.parse(raw)
        } catch (e: Exception) {
            _uiState.value = TaskUiState(
                status = TaskRunStatus.FAILED,
                rawMessage = raw,
                errorMessage = e.message ?: "Invalid task message.",
            )
            return
        }

        cancelFlag.set(false)
        val startedMs = System.currentTimeMillis()
        _uiState.value = TaskUiState(
            status = TaskRunStatus.RUNNING,
            rawMessage = parsed.rawMessage,
            category = parsed.category,
            discountDisplay = parsed.discountDisplay,
            stage = "Validating task",
            stageIndex = 1,
            progressPercent = 5,
        )

        timerJob?.cancel()
        timerJob = viewModelScope.launch {
            while (isActive) {
                delay(1000)
                val sec = ((System.currentTimeMillis() - startedMs) / 1000L).coerceAtLeast(0L)
                _uiState.update { it.copy(elapsedSeconds = sec) }
            }
        }

        activeJob = viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    _uiState.update {
                        it.copy(stage = "Opening website", stageIndex = 2, progressPercent = 12)
                    }
                    _uiState.update {
                        it.copy(stage = "Discovering subcategories", stageIndex = 3, progressPercent = 20)
                    }
                    val (_, targets, isParent) = scraper.resolveTargets(parsed.category)
                    val displayCategory = MessageParser.resolveFilenameCategoryLabel(
                        parsed, targets, isParent
                    )
                    val stem = MessageParser.buildOutputStem(parsed, displayCategory)

                    _uiState.update {
                        it.copy(
                            stage = "Collecting product URLs",
                            stageIndex = 4,
                            progressPercent = 28,
                            currentSubcategory = targets.firstOrNull()?.name ?: parsed.category,
                        )
                    }

                    val (candidates, catWarnings) = scraper.collectProductsForTargets(targets) { sub, subIdx, subTotal, disc ->
                        if (cancelFlag.get()) throw CancellationException("Cancelled")
                        val pct = 28 + ((subIdx.toFloat() / maxOf(subTotal, 1)) * 14f).toInt()
                        _uiState.update {
                            it.copy(
                                stage = "Collecting product URLs",
                                stageIndex = 4,
                                progressPercent = pct.coerceAtMost(42),
                                productsDiscovered = disc,
                                currentSubcategory = sub,
                            )
                        }
                    }

                    _uiState.update {
                        it.copy(
                            stage = "Extracting product details",
                            stageIndex = 5,
                            progressPercent = 44,
                            productsDiscovered = candidates.size,
                            warnings = catWarnings,
                        )
                    }

                    val (records, failures) = scraper.scrapeAllProducts(
                        candidates = candidates,
                        task = parsed,
                        isCancelled = { cancelFlag.get() },
                    ) { index, total, extracted, failed, sub, phase ->
                        val pct = 44 + ((index.toFloat() / maxOf(total, 1)) * 40f).toInt()
                        val (stageName, stageIdx) = when (phase) {
                            "calculated" -> when (index % 3) {
                                1 -> "Detecting sizes" to 6
                                2 -> "Categorizing products" to 7
                                else -> "Calculating discounted prices" to 8
                            }
                            else -> "Extracting product details" to 5
                        }
                        _uiState.update {
                            it.copy(
                                stage = stageName,
                                stageIndex = stageIdx,
                                progressPercent = pct.coerceAtMost(84),
                                productsExtracted = extracted,
                                failedProducts = failed,
                                currentSubcategory = sub,
                            )
                        }
                    }

                    if (cancelFlag.get()) throw CancellationException("Cancelled")

                    val app = getApplication<Application>()
                    val baseOut = File(app.filesDir, "output")
                    val (excelFile, pdfFile) = MessageParser.resolveUniqueOutputFiles(
                        excelDir = File(baseOut, "Excel"),
                        pdfDir = File(baseOut, "PDF"),
                        stem = stem,
                    )
                    val headerHex = HeaderColorPicker.pickReadableHex()

                    _uiState.update {
                        it.copy(
                            stage = "Generating Excel",
                            stageIndex = 9,
                            progressPercent = 88,
                            productsExtracted = records.size,
                            failedProducts = failures.size,
                        )
                    }
                    ExcelGenerator.generate(records, excelFile, headerHex)

                    _uiState.update {
                        it.copy(
                            stage = "Generating PDF",
                            stageIndex = 10,
                            progressPercent = 94,
                        )
                    }
                    val (_, pdfWarn) = PdfGenerator.generate(records, pdfFile, headerHex)

                    _uiState.update {
                        it.copy(
                            stage = "Saving generated files",
                            stageIndex = 11,
                            progressPercent = 98,
                        )
                    }

                    val allWarnings = catWarnings + listOfNotNull(pdfWarn)
                    timerJob?.cancel()
                    _uiState.update {
                        it.copy(
                            status = TaskRunStatus.COMPLETED,
                            stage = "Completed",
                            stageIndex = 11,
                            progressPercent = 100,
                            productsDiscovered = candidates.size,
                            productsExtracted = records.size,
                            failedProducts = failures.size,
                            excelFile = excelFile,
                            pdfFile = pdfFile,
                            excelFilename = excelFile.name,
                            pdfFilename = pdfFile.name,
                            warnings = allWarnings,
                            failures = failures,
                        )
                    }
                }
            } catch (_: CancellationException) {
                timerJob?.cancel()
            } catch (e: Exception) {
                timerJob?.cancel()
                _uiState.update {
                    it.copy(
                        status = TaskRunStatus.FAILED,
                        stage = "Failed",
                        errorMessage = e.message ?: "Extraction failed. Please check internet connection.",
                    )
                }
            }
        }
    }

    suspend fun exportToDownloads(sourceFile: File, mimeType: String): Boolean = withContext(Dispatchers.IO) {
        val app = getApplication<Application>()
        return@withContext try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, sourceFile.name)
                    put(MediaStore.Downloads.MIME_TYPE, mimeType)
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val resolver = app.contentResolver
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: return@withContext false
                resolver.openOutputStream(uri)?.use { out ->
                    sourceFile.inputStream().use { inp -> inp.copyTo(out) }
                }
                values.clear()
                values.put(MediaStore.Downloads.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
                true
            } else {
                val dlDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                dlDir.mkdirs()
                sourceFile.copyTo(File(dlDir, sourceFile.name), overwrite = true)
                true
            }
        } catch (_: Exception) {
            false
        }
    }
}
