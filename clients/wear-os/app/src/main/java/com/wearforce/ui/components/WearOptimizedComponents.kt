package com.wearforce.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.*
import kotlinx.coroutines.delay

/**
 * Wear OS optimized scrollable list with proper scaling and focus management
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun WearOptimizedList(
    modifier: Modifier = Modifier,
    contentPadding: PaddingValues = PaddingValues(vertical = 16.dp),
    verticalArrangement: Arrangement.Vertical = Arrangement.spacedBy(4.dp),
    state: ScalingLazyListState = rememberScalingLazyListState(),
    content: LazyListScope.() -> Unit
) {
    ScalingLazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = contentPadding,
        verticalArrangement = verticalArrangement,
        state = state,
        scalingParams = ScalingLazyColumnDefaults.scalingParams(
            edgeScale = 0.7f,
            edgeAlpha = 0.7f,
            minElementHeight = 32.dp,
            maxElementHeight = 60.dp,
            minTransitionArea = 0.3f,
            maxTransitionArea = 0.7f,
            scaleInterpolator = CubicBezierEasing(0.25f, 0.1f, 0.25f, 1f),
            reverseLayout = false
        ),
        anchorType = ScalingLazyListAnchorType.ItemCenter,
        content = content
    )
}

/**
 * Haptic feedback enhanced button with wear-optimized sizing
 */
@Composable
fun HapticButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = ButtonDefaults.primaryButtonColors(),
    border: ButtonBorder? = null,
    hapticFeedback: HapticFeedbackType = HapticFeedbackType.LongPress,
    content: @Composable RowScope.() -> Unit
) {
    val haptic = LocalHapticFeedback.current
    
    Button(
        onClick = {
            if (enabled) {
                haptic.performHapticFeedback(hapticFeedback)
                onClick()
            }
        },
        modifier = modifier,
        enabled = enabled,
        colors = colors,
        border = border,
        content = content
    )
}

/**
 * Battery and performance optimized pulsing indicator
 */
@Composable
fun PulsingIndicator(
    isActive: Boolean,
    modifier: Modifier = Modifier,
    color: Color = MaterialTheme.colors.primary,
    size: androidx.compose.ui.unit.Dp = 16.dp,
    pulseScale: Float = 1.3f
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (isActive) pulseScale else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = EaseInOutCubic),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse_scale"
    )

    Box(
        modifier = modifier
            .size(size)
            .scale(scale)
            .background(color, CircleShape)
    )
}

/**
 * Voice activity indicator with audio level visualization
 */
@Composable
fun VoiceActivityIndicator(
    isActive: Boolean,
    audioLevel: Float = 0f,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "voice_activity")
    
    val wave1 by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = if (isActive) 1f else 0.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "wave1"
    )
    
    val wave2 by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue = if (isActive) 0.8f else 0.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "wave2"
    )
    
    val wave3 by infiniteTransition.animateFloat(
        initialValue = 0.7f,
        targetValue = if (isActive) 1f else 0.7f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "wave3"
    )

    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        repeat(3) { index ->
            val height = when (index) {
                0 -> (wave1 * (0.5f + audioLevel * 0.5f)).coerceIn(0.2f, 1f)
                1 -> (wave2 * (0.7f + audioLevel * 0.3f)).coerceIn(0.3f, 1f)
                else -> (wave3 * (0.6f + audioLevel * 0.4f)).coerceIn(0.2f, 1f)
            }
            
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height((16.dp * height))
                    .background(
                        if (isActive) MaterialTheme.colors.primary else MaterialTheme.colors.onSurface.copy(alpha = 0.3f),
                        RoundedCornerShape(2.dp)
                    )
            )
        }
    }
}

/**
 * Connection status indicator optimized for small screens
 */
@Composable
fun ConnectionStatusIndicator(
    isConnected: Boolean,
    modifier: Modifier = Modifier,
    showText: Boolean = false
) {
    val color = if (isConnected) MaterialTheme.colors.primary else MaterialTheme.colors.error
    val icon = if (isConnected) Icons.Default.Wifi else Icons.Default.WifiOff
    
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Icon(
            imageVector = icon,
            contentDescription = if (isConnected) "Connected" else "Disconnected",
            tint = color,
            modifier = Modifier.size(12.dp)
        )
        
        if (showText) {
            Text(
                text = if (isConnected) "Online" else "Offline",
                style = MaterialTheme.typography.caption2,
                color = color,
                fontSize = 10.sp
            )
        }
    }
}

/**
 * Optimized chip with proper touch targets for Wear OS
 */
@Composable
fun WearChip(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    enabled: Boolean = true,
    colors: ChipColors = ChipDefaults.secondaryChipColors()
) {
    val haptic = LocalHapticFeedback.current
    
    Chip(
        onClick = {
            if (enabled) {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                onClick()
            }
        },
        modifier = modifier.height(32.dp),
        enabled = enabled,
        colors = colors,
        border = ChipDefaults.chipBorder()
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            icon?.let {
                Icon(
                    imageVector = it,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp)
                )
            }
            
            Text(
                text = label,
                style = MaterialTheme.typography.caption1,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                textAlign = TextAlign.Center,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

/**
 * Optimized loading state for Wear OS
 */
@Composable
fun WearLoadingIndicator(
    modifier: Modifier = Modifier,
    message: String? = null,
    size: androidx.compose.ui.unit.Dp = 24.dp
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(size),
            strokeWidth = 2.dp,
            colors = ProgressIndicatorDefaults.circularProgressIndicatorColors(
                color = MaterialTheme.colors.primary
            )
        )
        
        message?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.caption2,
                color = MaterialTheme.colors.onSurface.copy(alpha = 0.7f),
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

/**
 * Error state component optimized for Wear OS
 */
@Composable
fun WearErrorState(
    message: String,
    onRetry: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(
            imageVector = Icons.Default.Error,
            contentDescription = "Error",
            tint = MaterialTheme.colors.error,
            modifier = Modifier.size(32.dp)
        )
        
        Text(
            text = message,
            style = MaterialTheme.typography.body2,
            color = MaterialTheme.colors.error,
            textAlign = TextAlign.Center,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis
        )
        
        onRetry?.let { retryAction ->
            HapticButton(
                onClick = retryAction,
                colors = ButtonDefaults.secondaryButtonColors()
            ) {
                Text("Retry", style = MaterialTheme.typography.button)
            }
        }
    }
}

/**
 * Swipe to dismiss wrapper for Wear OS
 */
@OptIn(ExperimentalWearMaterialApi::class)
@Composable
fun SwipeToDismissBox(
    onDismissed: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit
) {
    val state = rememberSwipeToDismissBoxState()
    
    LaunchedEffect(state.currentValue) {
        if (state.currentValue == SwipeToDismissValue.Dismissed) {
            onDismissed()
        }
    }
    
    SwipeToDismissBox(
        state = state,
        modifier = modifier,
        backgroundKey = "background",
        contentKey = "content"
    ) { isBackground ->
        if (isBackground) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colors.error),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Delete,
                    contentDescription = "Delete",
                    tint = Color.White
                )
            }
        } else {
            Box(content = content)
        }
    }
}

/**
 * Optimized timer component for showing recording duration
 */
@Composable
fun RecordingTimer(
    isRecording: Boolean,
    modifier: Modifier = Modifier
) {
    var elapsedTime by remember { mutableStateOf(0L) }
    
    LaunchedEffect(isRecording) {
        if (isRecording) {
            val startTime = System.currentTimeMillis()
            while (isRecording) {
                elapsedTime = System.currentTimeMillis() - startTime
                delay(100) // Update every 100ms for smooth animation
            }
        } else {
            elapsedTime = 0L
        }
    }
    
    val seconds = (elapsedTime / 1000) % 60
    val minutes = (elapsedTime / 60000)
    
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        PulsingIndicator(
            isActive = isRecording,
            color = MaterialTheme.colors.error,
            size = 8.dp
        )
        
        Text(
            text = "%02d:%02d".format(minutes, seconds),
            style = MaterialTheme.typography.caption1,
            color = if (isRecording) MaterialTheme.colors.error else MaterialTheme.colors.onSurface
        )
    }
}