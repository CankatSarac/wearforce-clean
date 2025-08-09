import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createDrawerNavigator } from '@react-navigation/drawer';
import Icon from 'react-native-vector-icons/MaterialIcons';

import { useAppSelector } from '@hooks/redux';
import { AuthNavigator } from './AuthNavigator';
import { ChatScreen } from '@screens/chat/ChatScreen';
import { DashboardScreen } from '@screens/dashboard/DashboardScreen';
import { CRMScreen } from '@screens/crm/CRMScreen';
import { ERPScreen } from '@screens/erp/ERPScreen';
import { ProfileScreen } from '@screens/profile/ProfileScreen';
import { SettingsScreen } from '@screens/settings/SettingsScreen';
import { colors } from '@utils/theme';

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
  Chat: undefined;
  Dashboard: undefined;
  CRM: undefined;
  ERP: undefined;
  Profile: undefined;
  Settings: undefined;
};

export type TabParamList = {
  Dashboard: undefined;
  Chat: undefined;
  CRM: undefined;
  ERP: undefined;
};

export type DrawerParamList = {
  TabNavigator: undefined;
  Profile: undefined;
  Settings: undefined;
};

const RootStack = createStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();
const Drawer = createDrawerNavigator<DrawerParamList>();

const TabNavigator: React.FC = () => {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName: string;

          switch (route.name) {
            case 'Dashboard':
              iconName = 'dashboard';
              break;
            case 'Chat':
              iconName = 'chat';
              break;
            case 'CRM':
              iconName = 'people';
              break;
            case 'ERP':
              iconName = 'inventory';
              break;
            default:
              iconName = 'circle';
          }

          return <Icon name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.gray,
        tabBarStyle: {
          backgroundColor: colors.white,
          borderTopColor: colors.lightGray,
          elevation: 10,
          shadowOpacity: 0.1,
        },
        headerShown: false,
      })}
    >
      <Tab.Screen 
        name="Dashboard" 
        component={DashboardScreen} 
        options={{ tabBarLabel: 'Dashboard' }}
      />
      <Tab.Screen 
        name="Chat" 
        component={ChatScreen} 
        options={{ tabBarLabel: 'Chat' }}
      />
      <Tab.Screen 
        name="CRM" 
        component={CRMScreen} 
        options={{ tabBarLabel: 'CRM' }}
      />
      <Tab.Screen 
        name="ERP" 
        component={ERPScreen} 
        options={{ tabBarLabel: 'ERP' }}
      />
    </Tab.Navigator>
  );
};

const DrawerNavigator: React.FC = () => {
  return (
    <Drawer.Navigator
      screenOptions={{
        headerShown: false,
        drawerStyle: {
          backgroundColor: colors.white,
        },
        drawerActiveTintColor: colors.primary,
        drawerInactiveTintColor: colors.gray,
      }}
    >
      <Drawer.Screen 
        name="TabNavigator" 
        component={TabNavigator}
        options={{
          drawerLabel: 'Home',
          drawerIcon: ({ color, size }) => (
            <Icon name="home" size={size} color={color} />
          ),
        }}
      />
      <Drawer.Screen 
        name="Profile" 
        component={ProfileScreen}
        options={{
          drawerLabel: 'Profile',
          drawerIcon: ({ color, size }) => (
            <Icon name="person" size={size} color={color} />
          ),
        }}
      />
      <Drawer.Screen 
        name="Settings" 
        component={SettingsScreen}
        options={{
          drawerLabel: 'Settings',
          drawerIcon: ({ color, size }) => (
            <Icon name="settings" size={size} color={color} />
          ),
        }}
      />
    </Drawer.Navigator>
  );
};

export const AppNavigator: React.FC = () => {
  const { isAuthenticated, isLoading } = useAppSelector((state) => state.auth);

  return (
    <RootStack.Navigator screenOptions={{ headerShown: false }}>
      {!isAuthenticated ? (
        <RootStack.Screen name="Auth" component={AuthNavigator} />
      ) : (
        <RootStack.Screen name="Main" component={DrawerNavigator} />
      )}
    </RootStack.Navigator>
  );
};