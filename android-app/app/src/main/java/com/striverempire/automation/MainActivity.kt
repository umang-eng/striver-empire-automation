package com.striverempire.automation

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.striverempire.automation.data.CategoryCatalog
import com.striverempire.automation.model.TaskRunStatus
import com.striverempire.automation.ui.components.BackgroundVideoLayer
import com.striverempire.automation.ui.components.CategorySuggestionsPanel
import com.striverempire.automation.ui.components.CompletionCard
import com.striverempire.automation.ui.components.LiquidGlassHeader
import com.striverempire.automation.ui.components.TaskInputCard
import com.striverempire.automation.ui.components.TaskProgressCard
import com.striverempire.automation.viewmodel.MainViewModel
import kotlinx.coroutines.launch
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            StriverEmpireApp()
        }
    }
}

@Composable
fun StriverEmpireApp(vm: MainViewModel = viewModel()) {
    val inputValue by vm.inputValue.collectAsState()
    val uiState by vm.uiState.collectAsState()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    fun openFile(file: File, mimeType: String) {
        runCatching {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, mimeType)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(intent, "Open ${file.name}"))
        }.onFailure {
            Toast.makeText(context, "No app installed to open ${file.name}", Toast.LENGTH_SHORT).show()
        }
    }

    fun shareFile(file: File, mimeType: String) {
        runCatching {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = mimeType
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(intent, "Share ${file.name}"))
        }.onFailure {
            Toast.makeText(context, "Unable to share ${file.name}", Toast.LENGTH_SHORT).show()
        }
    }

    fun saveToDownloads(file: File, mimeType: String) {
        scope.launch {
            val ok = vm.exportToDownloads(file, mimeType)
            Toast.makeText(
                context,
                if (ok) "Saved to Downloads: ${file.name}" else "Failed saving ${file.name}",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        BackgroundVideoLayer()

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            LiquidGlassHeader()

            // Hero Headline matching Web App
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = "PRODUCT AUTOMATION ASSISTANT",
                    color = Color.White.copy(alpha = 0.72f),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 2.0.sp,
                )
                Text(
                    text = "Product reports, simplified.",
                    color = Color.White,
                    fontSize = 28.sp,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                )
                Text(
                    text = "Enter a category and discount to extract live products and generate matching Excel & PDF reports.",
                    color = Color.White.copy(alpha = 0.72f),
                    fontSize = 13.sp,
                    textAlign = TextAlign.Center,
                )
            }

            BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
                val isWide = maxWidth >= 800.dp

                val mainPanel: @Composable (Modifier) -> Unit = { mod ->
                    when (uiState.status) {
                        TaskRunStatus.RUNNING -> TaskProgressCard(
                            state = uiState,
                            onCancel = vm::cancelTask,
                            modifier = mod,
                        )
                        TaskRunStatus.COMPLETED -> CompletionCard(
                            state = uiState,
                            onOpenFile = ::openFile,
                            onSaveToDownloads = ::saveToDownloads,
                            onShareFile = ::shareFile,
                            onReset = vm::resetToInput,
                            modifier = mod,
                        )
                        TaskRunStatus.FAILED -> FailedPanel(
                            errorMessage = uiState.errorMessage ?: "Extraction failed.",
                            onRetry = vm::resetToInput,
                            modifier = mod,
                        )
                        TaskRunStatus.IDLE -> TaskInputCard(
                            value = inputValue,
                            onValueChange = vm::updateInput,
                            onSubmit = vm::submitTask,
                            modifier = mod,
                        )
                    }
                }

                if (isWide) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        mainPanel(Modifier.weight(7f))
                        CategorySuggestionsPanel(
                            groups = CategoryCatalog.defaultGroups,
                            onUseTemplate = vm::selectTemplate,
                            modifier = Modifier.weight(5f),
                        )
                    }
                } else {
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        mainPanel(Modifier.fillMaxWidth())
                        CategorySuggestionsPanel(
                            groups = CategoryCatalog.defaultGroups,
                            onUseTemplate = vm::selectTemplate,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }

            Spacer(Modifier.height(4.dp))
            Text(
                text = "Striver Empire Automation · Native On-Device Catalog Extraction & Excel/PDF Engine",
                color = Color.White.copy(alpha = 0.50f),
                fontSize = 11.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun FailedPanel(
    errorMessage: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color(0xFF7F1D1D).copy(alpha = 0.45f))
            .border(1.dp, Color(0xFFFDA4AF).copy(alpha = 0.4f), RoundedCornerShape(24.dp))
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {
            Icon(Icons.Rounded.WarningAmber, null, tint = Color(0xFFFDA4AF), modifier = Modifier.size(20.dp))
            Column {
                Text("Extraction Failed", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                Text(errorMessage, color = Color(0xFFFECDD3), fontSize = 12.sp)
            }
        }
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(12.dp))
                .background(Color.White.copy(alpha = 0.14f))
                .border(1.dp, Color.White.copy(alpha = 0.25f), RoundedCornerShape(12.dp))
                .clickable(onClick = onRetry)
                .padding(horizontal = 14.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Rounded.Refresh, null, tint = Color.White, modifier = Modifier.size(15.dp))
            Spacer(Modifier.width(6.dp))
            Text("Try Another Task", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}
