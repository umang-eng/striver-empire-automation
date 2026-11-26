package com.striverempire.automation.ui.components

import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.media.MediaPlayer
import android.net.Uri
import android.view.Surface
import android.view.TextureView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.striverempire.automation.R

@Composable
fun BackgroundVideoLayer(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var mediaPlayerRef by remember { mutableStateOf<MediaPlayer?>(null) }

    fun applyCenterCrop(textureView: TextureView, videoW: Int, videoH: Int) {
        if (videoW <= 0 || videoH <= 0 || textureView.width <= 0 || textureView.height <= 0) return
        val viewW = textureView.width.toFloat()
        val viewH = textureView.height.toFloat()
        val scaleX: Float
        val scaleY: Float
        if (videoW / videoH.toFloat() > viewW / viewH) {
            scaleX = (videoW / videoH.toFloat()) / (viewW / viewH)
            scaleY = 1f
        } else {
            scaleX = 1f
            scaleY = (viewW / viewH) / (videoW / videoH.toFloat())
        }
        val matrix = Matrix().apply {
            setScale(scaleX, scaleY, viewW / 2f, viewH / 2f)
        }
        textureView.setTransform(matrix)
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                mediaPlayerRef?.let { mp ->
                    if (!mp.isPlaying) {
                        runCatching { mp.start() }
                    }
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mediaPlayerRef?.release()
            mediaPlayerRef = null
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF05070D)),
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                TextureView(ctx).apply {
                    val textureView = this
                    isClickable = false
                    isFocusable = false
                    isLongClickable = false
                    surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                        private var videoW = 1920
                        private var videoH = 1080

                        override fun onSurfaceTextureAvailable(surface: SurfaceTexture, width: Int, height: Int) {
                            val mp = MediaPlayer().apply {
                                val uri = Uri.parse("android.resource://${context.packageName}/${R.raw.background}")
                                setDataSource(context, uri)
                                setSurface(Surface(surface))
                                isLooping = true
                                setVolume(0f, 0f)
                                setOnVideoSizeChangedListener { _, vw, vh ->
                                    videoW = vw
                                    videoH = vh
                                    applyCenterCrop(textureView, vw, vh)
                                }
                                setOnPreparedListener { player ->
                                    applyCenterCrop(textureView, player.videoWidth, player.videoHeight)
                                    player.start()
                                }
                                setOnCompletionListener { player ->
                                    player.start()
                                }
                                prepareAsync()
                            }
                            mediaPlayerRef = mp
                        }

                        override fun onSurfaceTextureSizeChanged(surface: SurfaceTexture, width: Int, height: Int) {
                            applyCenterCrop(textureView, videoW, videoH)
                        }

                        override fun onSurfaceTextureDestroyed(surface: SurfaceTexture): Boolean {
                            mediaPlayerRef?.release()
                            mediaPlayerRef = null
                            return true
                        }

                        override fun onSurfaceTextureUpdated(surface: SurfaceTexture) = Unit
                    }
                }
            },
        )

        // Subtle dark scrim for Liquid Glass readability
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color.Black.copy(alpha = 0.35f),
                            Color.Black.copy(alpha = 0.25f),
                            Color.Black.copy(alpha = 0.55f),
                        )
                    )
                )
        )
    }
}
