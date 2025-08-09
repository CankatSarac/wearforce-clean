import { configureStore } from '@reduxjs/toolkit';
import { persistStore, persistReducer } from 'redux-persist';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { combineReducers } from '@reduxjs/toolkit';

import authSlice from './slices/authSlice';
import chatSlice from './slices/chatSlice';
import crmSlice from './slices/crmSlice';
import erpSlice from './slices/erpSlice';
import settingsSlice from './slices/settingsSlice';
import networkSlice from './slices/networkSlice';

const persistConfig = {
  key: 'root',
  storage: AsyncStorage,
  whitelist: ['auth', 'settings'], // Only persist auth and settings
  blacklist: ['chat', 'crm', 'erp', 'network'], // Don't persist these
};

const rootReducer = combineReducers({
  auth: authSlice,
  chat: chatSlice,
  crm: crmSlice,
  erp: erpSlice,
  settings: settingsSlice,
  network: networkSlice,
});

const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE'],
        ignoredPaths: ['register'],
      },
    }),
  devTools: __DEV__,
});

export const persistor = persistStore(store);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;