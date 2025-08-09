import React, { useEffect } from 'react';
import { StatusBar, LogBox } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Toast from 'react-native-toast-message';
import SplashScreen from 'react-native-splash-screen';

import { store, persistor } from '@store/index';
import { AppNavigator } from '@navigation/AppNavigator';
import { LoadingScreen } from '@components/common/LoadingScreen';
import { toastConfig } from '@utils/toastConfig';
import { initializeApp } from '@services/appService';

// Ignore specific warnings in development
if (__DEV__) {
  LogBox.ignoreLogs([
    'Require cycle:',
    'Remote debugger',
    'Setting a timer',
  ]);
}

const App: React.FC = () => {
  useEffect(() => {
    const setupApp = async () => {
      try {
        await initializeApp();
      } catch (error) {
        console.error('App initialization failed:', error);
      } finally {
        // Hide splash screen after app initialization
        SplashScreen.hide();
      }
    };

    setupApp();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <Provider store={store}>
          <PersistGate loading={<LoadingScreen />} persistor={persistor}>
            <NavigationContainer>
              <StatusBar
                backgroundColor="transparent"
                barStyle="dark-content"
                translucent
              />
              <AppNavigator />
              <Toast config={toastConfig} />
            </NavigationContainer>
          </PersistGate>
        </Provider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
};

export default App;