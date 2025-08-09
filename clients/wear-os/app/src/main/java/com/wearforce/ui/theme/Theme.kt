package com.wearforce.ui.theme

import androidx.compose.runtime.Composable
import androidx.wear.compose.material.Colors
import androidx.wear.compose.material.MaterialTheme
import androidx.compose.ui.graphics.Color

private val WearForceColorPalette = Colors(
    primary = Color(0xFF1976D2),
    primaryVariant = Color(0xFF004BA0),
    secondary = Color(0xFF03DAC6),
    secondaryVariant = Color(0xFF018786),
    surface = Color(0xFF121212),
    error = Color(0xFFCF6679),
    onPrimary = Color.White,
    onSecondary = Color.Black,
    onSurface = Color.White,
    onSurfaceVariant = Color(0xFFBBBBBB),
    onError = Color.Black
)

@Composable
fun WearForceTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colors = WearForceColorPalette,
        typography = WearForceTypography,
        content = content
    )
}