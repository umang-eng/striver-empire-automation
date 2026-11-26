package com.striverempire.automation.generator

import android.graphics.Color
import kotlin.random.Random

object HeaderColorPicker {
    /**
     * Pick a random vibrant #RRGGBB color whose relative luminance >= 0.36
     * so bold black header text remains crisp and readable on every run.
     */
    fun pickReadableHex(rng: Random = Random.Default): String {
        repeat(25) {
            val hue = rng.nextFloat() * 360f
            val sat = 0.55f + rng.nextFloat() * 0.35f
            val lightness = 0.58f + rng.nextFloat() * 0.20f
            val rgb = hslToRgb(hue, sat, lightness)
            val r = Color.red(rgb) / 255.0
            val g = Color.green(rgb) / 255.0
            val b = Color.blue(rgb) / 255.0
            val luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if (luminance >= 0.36) {
                return String.format("%02X%02X%02X", Color.red(rgb), Color.green(rgb), Color.blue(rgb))
            }
        }
        return "4ADE80"
    }

    private fun hslToRgb(h: Float, s: Float, l: Float): Int {
        val c = (1f - kotlin.math.abs(2f * l - 1f)) * s
        val x = c * (1f - kotlin.math.abs((h / 60f) % 2f - 1f))
        val m = l - c / 2f
        val (rf, gf, bf) = when {
            h < 60f -> Triple(c, x, 0f)
            h < 120f -> Triple(x, c, 0f)
            h < 180f -> Triple(0f, c, x)
            h < 240f -> Triple(0f, x, c)
            h < 300f -> Triple(x, 0f, c)
            else -> Triple(c, 0f, x)
        }
        return Color.rgb(
            ((rf + m) * 255f).toInt().coerceIn(0, 255),
            ((gf + m) * 255f).toInt().coerceIn(0, 255),
            ((bf + m) * 255f).toInt().coerceIn(0, 255),
        )
    }
}
