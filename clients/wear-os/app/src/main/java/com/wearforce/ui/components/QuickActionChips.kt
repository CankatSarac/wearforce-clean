package com.wearforce.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.*
import com.wearforce.models.QuickAction
import com.wearforce.models.QuickActionCategory

@Composable
fun QuickActionChips(
    onQuickAction: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val quickActions = getDefaultQuickActions()
    
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = "Quick Actions",
            style = MaterialTheme.typography.caption1,
            color = MaterialTheme.colors.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )
        
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = PaddingValues(horizontal = 8.dp)
        ) {
            items(quickActions) { action ->
                QuickActionChip(
                    action = action,
                    onClick = { onQuickAction(action.action) }
                )
            }
        }
    }
}

@Composable
fun QuickActionChip(
    action: QuickAction,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Chip(
        onClick = onClick,
        modifier = modifier.width(100.dp),
        colors = ChipDefaults.chipColors(
            backgroundColor = MaterialTheme.colors.surface.copy(alpha = 0.9f),
            contentColor = MaterialTheme.colors.onSurface
        ),
        border = ChipDefaults.chipBorder(
            borderColor = MaterialTheme.colors.primary.copy(alpha = 0.3f),
            borderWidth = 1.dp
        )
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(2.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(
                imageVector = getIconForAction(action.icon),
                contentDescription = action.title,
                tint = MaterialTheme.colors.primary,
                modifier = Modifier.size(16.dp)
            )
            
            Text(
                text = action.title,
                style = MaterialTheme.typography.caption2,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
fun CategoryQuickActions(
    category: QuickActionCategory,
    onQuickAction: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val categoryActions = when (category) {
        QuickActionCategory.CRM -> getCrmActions()
        QuickActionCategory.ERP -> getErpActions()
        QuickActionCategory.ANALYTICS -> getAnalyticsActions()
        QuickActionCategory.GENERAL -> getGeneralActions()
    }
    
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = category.displayName,
            style = MaterialTheme.typography.button,
            color = MaterialTheme.colors.primary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )
        
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = PaddingValues(horizontal = 8.dp)
        ) {
            items(categoryActions) { action ->
                QuickActionChip(
                    action = action,
                    onClick = { onQuickAction(action.action) }
                )
            }
        }
    }
}

private fun getDefaultQuickActions(): List<QuickAction> {
    return listOf(
        QuickAction(
            id = "customers",
            title = "Customers",
            description = "View customer list",
            action = "Show me the customer list",
            icon = "people",
            category = QuickActionCategory.CRM
        ),
        QuickAction(
            id = "orders",
            title = "Orders",
            description = "View recent orders",
            action = "Show me recent orders",
            icon = "shopping_cart",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "inventory",
            title = "Inventory",
            description = "Check inventory levels",
            action = "Check inventory levels",
            icon = "inventory",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "sales",
            title = "Sales",
            description = "View sales data",
            action = "Show me today's sales",
            icon = "trending_up",
            category = QuickActionCategory.ANALYTICS
        ),
        QuickAction(
            id = "leads",
            title = "Leads",
            description = "View active leads",
            action = "Show me active leads",
            icon = "person_add",
            category = QuickActionCategory.CRM
        )
    )
}

private fun getCrmActions(): List<QuickAction> {
    return listOf(
        QuickAction(
            id = "all_customers",
            title = "All Customers",
            description = "View all customers",
            action = "Show me all customers",
            icon = "people",
            category = QuickActionCategory.CRM
        ),
        QuickAction(
            id = "new_customers",
            title = "New Customers",
            description = "View new customers",
            action = "Show me new customers from this week",
            icon = "person_add",
            category = QuickActionCategory.CRM
        ),
        QuickAction(
            id = "top_customers",
            title = "Top Customers",
            description = "View top customers by revenue",
            action = "Show me top customers by revenue",
            icon = "star",
            category = QuickActionCategory.CRM
        ),
        QuickAction(
            id = "leads",
            title = "Active Leads",
            description = "View active leads",
            action = "Show me active leads",
            icon = "trending_up",
            category = QuickActionCategory.CRM
        ),
        QuickAction(
            id = "opportunities",
            title = "Opportunities",
            description = "View sales opportunities",
            action = "Show me sales opportunities",
            icon = "attach_money",
            category = QuickActionCategory.CRM
        )
    )
}

private fun getErpActions(): List<QuickAction> {
    return listOf(
        QuickAction(
            id = "recent_orders",
            title = "Recent Orders",
            description = "View recent orders",
            action = "Show me recent orders",
            icon = "shopping_cart",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "pending_orders",
            title = "Pending Orders",
            description = "View pending orders",
            action = "Show me pending orders",
            icon = "pending",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "inventory_status",
            title = "Inventory",
            description = "Check inventory status",
            action = "Check inventory status",
            icon = "inventory",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "low_stock",
            title = "Low Stock",
            description = "View low stock items",
            action = "Show me low stock items",
            icon = "warning",
            category = QuickActionCategory.ERP
        ),
        QuickAction(
            id = "suppliers",
            title = "Suppliers",
            description = "View supplier information",
            action = "Show me supplier information",
            icon = "business",
            category = QuickActionCategory.ERP
        )
    )
}

private fun getAnalyticsActions(): List<QuickAction> {
    return listOf(
        QuickAction(
            id = "daily_sales",
            title = "Daily Sales",
            description = "View today's sales",
            action = "Show me today's sales",
            icon = "today",
            category = QuickActionCategory.ANALYTICS
        ),
        QuickAction(
            id = "monthly_revenue",
            title = "Monthly Revenue",
            description = "View monthly revenue",
            action = "Show me this month's revenue",
            icon = "trending_up",
            category = QuickActionCategory.ANALYTICS
        ),
        QuickAction(
            id = "sales_trend",
            title = "Sales Trend",
            description = "View sales trend",
            action = "Show me sales trend for the last 7 days",
            icon = "show_chart",
            category = QuickActionCategory.ANALYTICS
        ),
        QuickAction(
            id = "top_products",
            title = "Top Products",
            description = "View top selling products",
            action = "Show me top selling products",
            icon = "emoji_events",
            category = QuickActionCategory.ANALYTICS
        ),
        QuickAction(
            id = "performance",
            title = "Performance",
            description = "View performance metrics",
            action = "Show me performance metrics",
            icon = "assessment",
            category = QuickActionCategory.ANALYTICS
        )
    )
}

private fun getGeneralActions(): List<QuickAction> {
    return listOf(
        QuickAction(
            id = "dashboard",
            title = "Dashboard",
            description = "View dashboard",
            action = "Show me the dashboard",
            icon = "dashboard",
            category = QuickActionCategory.GENERAL
        ),
        QuickAction(
            id = "notifications",
            title = "Notifications",
            description = "Check notifications",
            action = "Check my notifications",
            icon = "notifications",
            category = QuickActionCategory.GENERAL
        ),
        QuickAction(
            id = "search",
            title = "Search",
            description = "Search data",
            action = "Help me search for something",
            icon = "search",
            category = QuickActionCategory.GENERAL
        ),
        QuickAction(
            id = "help",
            title = "Help",
            description = "Get help",
            action = "I need help with WearForce",
            icon = "help",
            category = QuickActionCategory.GENERAL
        )
    )
}

private fun getIconForAction(iconName: String): ImageVector {
    return when (iconName) {
        "people" -> Icons.Default.People
        "person_add" -> Icons.Default.PersonAdd
        "shopping_cart" -> Icons.Default.ShoppingCart
        "inventory" -> Icons.Default.Inventory
        "trending_up" -> Icons.Default.TrendingUp
        "star" -> Icons.Default.Star
        "attach_money" -> Icons.Default.AttachMoney
        "pending" -> Icons.Default.Pending
        "warning" -> Icons.Default.Warning
        "business" -> Icons.Default.Business
        "today" -> Icons.Default.Today
        "show_chart" -> Icons.Default.ShowChart
        "emoji_events" -> Icons.Default.EmojiEvents
        "assessment" -> Icons.Default.Assessment
        "dashboard" -> Icons.Default.Dashboard
        "notifications" -> Icons.Default.Notifications
        "search" -> Icons.Default.Search
        "help" -> Icons.Default.Help
        else -> Icons.Default.Help
    }
}