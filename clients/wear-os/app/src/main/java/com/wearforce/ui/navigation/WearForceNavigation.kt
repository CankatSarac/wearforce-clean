package com.wearforce.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import com.wearforce.ui.screens.chat.ConversationScreen
import com.wearforce.ui.screens.crm.CRMScreen
import com.wearforce.ui.screens.dashboard.DashboardScreen
import com.wearforce.ui.screens.erp.ERPScreen
import com.wearforce.ui.screens.main.MainScreen

@Composable
fun WearForceNavigation(
    navController: NavHostController,
    hasAudioPermission: Boolean
) {
    SwipeDismissableNavHost(
        navController = navController,
        startDestination = Screen.Main.route
    ) {
        composable(Screen.Main.route) {
            MainScreen(
                onNavigateToChat = { navController.navigate(Screen.Chat.route) },
                onNavigateToCRM = { navController.navigate(Screen.CRM.route) },
                onNavigateToERP = { navController.navigate(Screen.ERP.route) },
                onNavigateToDashboard = { navController.navigate(Screen.Dashboard.route) }
            )
        }
        
        composable(Screen.Chat.route) {
            ConversationScreen(
                hasAudioPermission = hasAudioPermission,
                onNavigateBack = { navController.popBackStack() }
            )
        }
        
        composable(Screen.CRM.route) {
            CRMScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
        
        composable(Screen.ERP.route) {
            ERPScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
        
        composable(Screen.Dashboard.route) {
            DashboardScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}

sealed class Screen(val route: String) {
    object Main : Screen("main")
    object Chat : Screen("chat")
    object CRM : Screen("crm")
    object ERP : Screen("erp")
    object Dashboard : Screen("dashboard")
}