package com.striverempire.automation.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.striverempire.automation.model.PROGRESS_STAGES
import com.striverempire.automation.model.TaskUiState

@Composable
fun TaskProgressCard(
    state: TaskUiState,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val elapsedText = if (state.elapsedSeconds >= 60) {
        "${state.elapsedSeconds / 60}m ${state.elapsedSeconds % 60}s"
    } else {
        "${state.elapsedSeconds}s"
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.White.copy(alpha = 0.11f))
            .border(1.dp, Color.White.copy(alpha = 0.24f), RoundedCornerShape(24.dp))
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(Color(0xFF10B981).copy(alpha = 0.16f))
                        .border(1.dp, Color(0xFF34D399).copy(alpha = 0.35f), CircleShape)
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    CircularProgressIndicator(
                        color = Color(0xFF6EE7B7),
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(12.dp),
                    )
                    Text(
                        text = "Stage ${state.stageIndex} of ${state.totalStages}",
                        color = Color(0xFF6EE7B7),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                    )
                }

                Spacer(Modifier.height(8.dp))
                Text(
                    text = state.stage,
                    color = Color.White,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = buildString {
                        append("Task: ${state.rawMessage}")
                        if (state.currentSubcategory.isNotBlank()) {
                            append(" · ${state.currentSubcategory}")
                        }
                    },
                    color = Color.White.copy(alpha = 0.68f),
                    fontSize = 12.sp,
                )
            }

            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.White.copy(alpha = 0.08f))
                    .border(1.dp, Color.White.copy(alpha = 0.16f), RoundedCornerShape(12.dp))
                    .clickable(onClick = onCancel)
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = Icons.Rounded.Cancel,
                    contentDescription = "Cancel",
                    tint = Color.White.copy(alpha = 0.8f),
                    modifier = Modifier.size(15.dp),
                )
                Spacer(Modifier.width(4.dp))
                Text("Cancel", color = Color.White.copy(alpha = 0.85f), fontSize = 12.sp)
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text("Extraction Progress", color = Color.White.copy(alpha = 0.72f), fontSize = 12.sp)
                Text("${state.progressPercent}%", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
            LinearProgressIndicator(
                progress = { (state.progressPercent / 100f).coerceIn(0.04f, 1f) },
                color = Color(0xFF34D399),
                trackColor = Color.White.copy(alpha = 0.14f),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(CircleShape),
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            MetricBox("Discovered", state.productsDiscovered.toString(), Color.White, Modifier.weight(1f))
            MetricBox("Extracted", state.productsExtracted.toString(), Color(0xFF6EE7B7), Modifier.weight(1f))
            MetricBox("Failed", state.failedProducts.toString(), Color(0xFFFDA4AF), Modifier.weight(1f))
            MetricBox("Elapsed", elapsedText, Color.White, Modifier.weight(1f))
        }

        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
            PROGRESS_STAGES.chunked(2).forEachIndexed { rowIdx, pair ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    pair.forEachIndexed { colIdx, label ->
                        val stageNum = rowIdx * 2 + colIdx + 1
                        val done = stageNum < state.stageIndex
                        val current = stageNum == state.stageIndex
                        Row(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(10.dp))
                                .background(
                                    when {
                                        current -> Color(0xFF34D399).copy(alpha = 0.16f)
                                        done -> Color.White.copy(alpha = 0.05f)
                                        else -> Color.Transparent
                                    }
                                )
                                .border(
                                    1.dp,
                                    when {
                                        current -> Color(0xFF34D399).copy(alpha = 0.45f)
                                        done -> Color.White.copy(alpha = 0.10f)
                                        else -> Color.Transparent
                                    },
                                    RoundedCornerShape(10.dp),
                                )
                                .padding(horizontal = 8.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            when {
                                done -> Icon(Icons.Rounded.Check, null, tint = Color(0xFF6EE7B7), modifier = Modifier.size(13.dp))
                                current -> CircularProgressIndicator(color = Color(0xFF6EE7B7), strokeWidth = 1.8.dp, modifier = Modifier.size(12.dp))
                                else -> Box(Modifier.size(6.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.25f)))
                            }
                            Text(
                                text = "$stageNum. $label",
                                color = when {
                                    current -> Color.White
                                    done -> Color.White.copy(alpha = 0.78f)
                                    else -> Color.White.copy(alpha = 0.38f)
                                },
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                    if (pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun MetricBox(title: String, value: String, valueColor: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(Color.Black.copy(alpha = 0.28f))
            .border(1.dp, Color.White.copy(alpha = 0.12f), RoundedCornerShape(14.dp))
            .padding(10.dp),
    ) {
        Text(title, color = Color.White.copy(alpha = 0.55f), fontSize = 10.sp)
        Text(value, color = valueColor, fontSize = 16.sp, fontWeight = FontWeight.Bold)
    }
}
