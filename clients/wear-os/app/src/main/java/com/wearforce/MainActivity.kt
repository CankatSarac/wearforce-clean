package com.wearforce

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.navigation.compose.rememberNavController
import androidx.wear.compose.material.MaterialTheme
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberMultiplePermissionsState
import com.wearforce.ui.navigation.WearForceNavigation
import com.wearforce.ui.theme.WearForceTheme
import dagger.hilt.android.AndroidEntryPoint
import timber.log.Timber

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    
    private val viewModel: MainViewModel by viewModels()
    
    @OptIn(ExperimentalPermissionsApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        
        setContent {
            WearForceTheme {
                val navController = rememberNavController()
                
                // Request necessary permissions
                val permissionsState = rememberMultiplePermissionsState(
                    permissions = listOf(
                        Manifest.permission.RECORD_AUDIO,
                        Manifest.permission.INTERNET,
                        Manifest.permission.ACCESS_NETWORK_STATE
                    )
                )
                
                LaunchedEffect(key1 = permissionsState) {
                    if (!permissionsState.allPermissionsGranted) {
                        permissionsState.launchMultiplePermissionRequest()
                    }
                }
                
                WearForceApp(
                    navController = navController,
                    hasAudioPermission = permissionsState.permissions.find { 
                        it.permission == Manifest.permission.RECORD_AUDIO 
                    }?.hasPermission == true
                )
            }
        }
    }
}

@Composable
fun WearForceApp(
    navController: androidx.navigation.NavHostController,
    hasAudioPermission: Boolean
) {
    androidx.compose.foundation.layout.Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colors.background)
    ) {
        WearForceNavigation(
            navController = navController,
            hasAudioPermission = hasAudioPermission
        )
    }
}