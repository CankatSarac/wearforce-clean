package com.wearforce.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.*
import com.wearforce.models.ChatMessage
import com.wearforce.models.MessageType
import com.wearforce.models.formatTimestamp

@Composable
fun MessageBubble(
    message: ChatMessage,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = if (message.isFromUser) Alignment.End else Alignment.Start
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = if (message.isFromUser) Arrangement.End else Arrangement.Start
        ) {
            if (message.isFromUser) {
                Spacer(modifier = Modifier.width(32.dp))
            }
            
            Box(
                modifier = Modifier
                    .clip(
                        RoundedCornerShape(
                            topStart = if (message.isFromUser) 16.dp else 4.dp,
                            topEnd = if (message.isFromUser) 4.dp else 16.dp,
                            bottomStart = 16.dp,
                            bottomEnd = 16.dp
                        )
                    )
                    .background(
                        if (message.isFromUser) {
                            MaterialTheme.colors.primary
                        } else {
                            MaterialTheme.colors.surface.copy(alpha = 0.9f)
                        }
                    )
                    .padding(horizontal = 12.dp, vertical = 8.dp)
            ) {
                Column {
                    // Message content
                    when (message.type) {
                        MessageType.TEXT -> {
                            Text(
                                text = message.content,
                                style = MaterialTheme.typography.body2,
                                color = if (message.isFromUser) {
                                    Color.White
                                } else {
                                    MaterialTheme.colors.onSurface
                                }
                            )
                        }
                        
                        MessageType.VOICE -> {
                            VoiceMessageContent(
                                message = message,
                                isFromUser = message.isFromUser
                            )
                        }
                        
                        MessageType.SYSTEM -> {
                            SystemMessageContent(
                                message = message
                            )
                        }
                        
                        MessageType.ERROR -> {
                            ErrorMessageContent(
                                message = message
                            )
                        }
                    }
                    
                    // Timestamp
                    Text(
                        text = message.timestamp.formatTimestamp(),
                        style = MaterialTheme.typography.caption1,
                        color = if (message.isFromUser) {
                            Color.White.copy(alpha = 0.7f)
                        } else {
                            MaterialTheme.colors.onSurface.copy(alpha = 0.6f)
                        },
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
            
            if (!message.isFromUser) {
                Spacer(modifier = Modifier.width(32.dp))
            }
        }
    }
}

@Composable
private fun VoiceMessageContent(
    message: ChatMessage,
    isFromUser: Boolean
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(
            imageVector = Icons.Default.GraphicEq,
            contentDescription = "Voice message",
            tint = if (isFromUser) Color.White else MaterialTheme.colors.primary,
            modifier = Modifier.size(16.dp)
        )
        
        Column {
            if (message.transcription?.isNotEmpty() == true) {
                Text(
                    text = message.transcription,
                    style = MaterialTheme.typography.body2,
                    color = if (isFromUser) Color.White else MaterialTheme.colors.onSurface
                )
            } else {
                Text(
                    text = "Voice message",
                    style = MaterialTheme.typography.body2.copy(fontWeight = FontWeight.Medium),
                    color = if (isFromUser) Color.White else MaterialTheme.colors.onSurface
                )
            }
            
            if (message.content.isNotEmpty()) {
                Text(
                    text = message.content,
                    style = MaterialTheme.typography.caption1,
                    color = if (isFromUser) {
                        Color.White.copy(alpha = 0.8f)
                    } else {
                        MaterialTheme.colors.onSurface.copy(alpha = 0.7f)
                    },
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
            
            // Show confidence if available
            message.confidence?.let { confidence ->
                if (confidence < 0.8f) {
                    Text(
                        text = "Low confidence",
                        style = MaterialTheme.typography.caption2,
                        color = MaterialTheme.colors.error.copy(alpha = 0.7f),
                        modifier = Modifier.padding(top = 1.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun SystemMessageContent(
    message: ChatMessage
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Icon(
            imageVector = Icons.Default.Info,
            contentDescription = "System message",
            tint = MaterialTheme.colors.primary,
            modifier = Modifier.size(14.dp)
        )
        
        Text(
            text = message.content,
            style = MaterialTheme.typography.caption1,
            color = MaterialTheme.colors.onSurface.copy(alpha = 0.8f),
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun ErrorMessageContent(
    message: ChatMessage
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Icon(
            imageVector = Icons.Default.Error,
            contentDescription = "Error message",
            tint = MaterialTheme.colors.error,
            modifier = Modifier.size(14.dp)
        )
        
        Text(
            text = message.content,
            style = MaterialTheme.typography.caption1,
            color = MaterialTheme.colors.error
        )
    }
}

@Composable
fun MessageBubblePreview() {
    Column(
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.padding(16.dp)
    ) {
        // User text message
        MessageBubble(
            message = ChatMessage(
                content = "Show me today's sales",
                isFromUser = true,
                type = MessageType.TEXT
            )
        )
        
        // Assistant text response
        MessageBubble(
            message = ChatMessage(
                content = "Today's sales are $15,432 from 23 orders. This is 12% higher than yesterday.",
                isFromUser = false,
                type = MessageType.TEXT
            )
        )
        
        // Voice message from user
        MessageBubble(
            message = ChatMessage(
                content = "What about the top customers?",
                isFromUser = true,
                type = MessageType.VOICE,
                transcription = "What about the top customers?",
                confidence = 0.95f
            )
        )
        
        // System message
        MessageBubble(
            message = ChatMessage(
                content = "Connected to WearForce API",
                isFromUser = false,
                type = MessageType.SYSTEM
            )
        )
        
        // Error message
        MessageBubble(
            message = ChatMessage(
                content = "Failed to fetch customer data",
                isFromUser = false,
                type = MessageType.ERROR
            )
        )
    }
}