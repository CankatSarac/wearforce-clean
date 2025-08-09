package com.wearforce.ui.screens.main

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Inventory
import androidx.compose.material.icons.filled.People
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.Button
import androidx.wear.compose.material.ButtonDefaults
import androidx.wear.compose.material.Icon
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.ScalingLazyColumn
import androidx.wear.compose.material.ScalingLazyListState
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TitleCard
import androidx.wear.compose.material.rememberScalingLazyListState

@Composable
fun MainScreen(
    onNavigateToChat: () -> Unit,
    onNavigateToCRM: () -> Unit,
    onNavigateToERP: () -> Unit,
    onNavigateToDashboard: () -> Unit
) {
    val listState = rememberScalingLazyListState()
    
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        ScalingLazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                top = 16.dp,
                start = 8.dp,
                end = 8.dp,
                bottom = 16.dp
            ),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            state = listState
        ) {
            item {
                Text(
                    text = "WearForce",
                    style = MaterialTheme.typography.title2,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
            
            item {
                Spacer(modifier = Modifier.height(8.dp))
            }
            
            item {
                MainMenuCard(
                    title = "Chat",
                    subtitle = "AI Assistant",
                    icon = Icons.Default.Chat,
                    onClick = onNavigateToChat
                )
            }
            
            item {
                MainMenuCard(
                    title = "CRM",
                    subtitle = "Customers & Leads",
                    icon = Icons.Default.People,
                    onClick = onNavigateToCRM
                )
            }
            
            item {
                MainMenuCard(
                    title = "ERP",
                    subtitle = "Orders & Inventory",
                    icon = Icons.Default.Inventory,
                    onClick = onNavigateToERP
                )
            }
            
            item {
                MainMenuCard(
                    title = "Dashboard",
                    subtitle = "Analytics & Stats",
                    icon = Icons.Default.BarChart,
                    onClick = onNavigateToDashboard
                )
            }
        }
    }
}

@Composable
fun MainMenuCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    TitleCard(
        onClick = onClick,
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = title,
                    modifier = Modifier.size(24.dp),
                    tint = MaterialTheme.colors.primary
                )
                
                Spacer(modifier = Modifier.width(12.dp))
                
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.button,
                        color = MaterialTheme.colors.onSurface
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.caption2,
                        color = MaterialTheme.colors.onSurfaceVariant
                    )
                }
            }
        },
        modifier = modifier.fillMaxWidth()
    )
}