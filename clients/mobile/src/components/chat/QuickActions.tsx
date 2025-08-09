import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { colors, spacing, typography } from '@utils/theme';

interface QuickAction {
  id: string;
  title: string;
  description: string;
  action: string;
  icon: string;
  category: 'crm' | 'erp' | 'analytics' | 'general';
}

interface QuickActionsProps {
  onAction: (action: string) => void;
}

const quickActions: QuickAction[] = [
  {
    id: 'customers',
    title: 'Customers',
    description: 'View customer list',
    action: 'Show me the customer list',
    icon: 'people',
    category: 'crm',
  },
  {
    id: 'orders',
    title: 'Recent Orders',
    description: 'View recent orders',
    action: 'Show me recent orders',
    icon: 'shopping-cart',
    category: 'erp',
  },
  {
    id: 'inventory',
    title: 'Inventory',
    description: 'Check inventory levels',
    action: 'Check inventory levels',
    icon: 'inventory',
    category: 'erp',
  },
  {
    id: 'sales',
    title: 'Sales Today',
    description: 'View today\'s sales',
    action: 'Show me today\'s sales',
    icon: 'trending-up',
    category: 'analytics',
  },
  {
    id: 'leads',
    title: 'Active Leads',
    description: 'View active leads',
    action: 'Show me active leads',
    icon: 'person-add',
    category: 'crm',
  },
  {
    id: 'lowstock',
    title: 'Low Stock',
    description: 'Items running low',
    action: 'Show me items with low stock',
    icon: 'warning',
    category: 'erp',
  },
  {
    id: 'revenue',
    title: 'Monthly Revenue',
    description: 'View revenue data',
    action: 'Show me this month\'s revenue',
    icon: 'attach-money',
    category: 'analytics',
  },
  {
    id: 'help',
    title: 'Help',
    description: 'Get assistance',
    action: 'I need help with WearForce',
    icon: 'help',
    category: 'general',
  },
];

export const QuickActions: React.FC<QuickActionsProps> = ({ onAction }) => {
  const categories = [
    { id: 'crm', title: 'CRM', icon: 'people' },
    { id: 'erp', title: 'ERP', icon: 'business' },
    { id: 'analytics', title: 'Analytics', icon: 'analytics' },
    { id: 'general', title: 'General', icon: 'apps' },
  ];

  const getIconName = (iconName: string): string => {
    const iconMap: Record<string, string> = {
      'people': 'people',
      'shopping-cart': 'shopping-cart',
      'inventory': 'inventory',
      'trending-up': 'trending-up',
      'person-add': 'person-add',
      'warning': 'warning',
      'attach-money': 'attach-money',
      'help': 'help',
      'business': 'business',
      'analytics': 'analytics',
      'apps': 'apps',
    };
    return iconMap[iconName] || 'help';
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Quick Actions</Text>
      <Text style={styles.subtitle}>Tap to ask about these topics</Text>

      {categories.map((category) => {
        const categoryActions = quickActions.filter(
          (action) => action.category === category.id
        );

        if (categoryActions.length === 0) return null;

        return (
          <View key={category.id} style={styles.categoryContainer}>
            <View style={styles.categoryHeader}>
              <Icon
                name={getIconName(category.icon)}
                size={18}
                color={colors.primary}
              />
              <Text style={styles.categoryTitle}>{category.title}</Text>
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.actionsContainer}
            >
              {categoryActions.map((action) => (
                <QuickActionCard
                  key={action.id}
                  action={action}
                  onPress={() => onAction(action.action)}
                />
              ))}
            </ScrollView>
          </View>
        );
      })}
    </View>
  );
};

interface QuickActionCardProps {
  action: QuickAction;
  onPress: () => void;
}

const QuickActionCard: React.FC<QuickActionCardProps> = ({ action, onPress }) => {
  const getIconName = (iconName: string): string => {
    const iconMap: Record<string, string> = {
      'people': 'people',
      'shopping-cart': 'shopping-cart',
      'inventory': 'inventory',
      'trending-up': 'trending-up',
      'person-add': 'person-add',
      'warning': 'warning',
      'attach-money': 'attach-money',
      'help': 'help',
    };
    return iconMap[iconName] || 'help';
  };

  const getCategoryColor = (category: string): string => {
    const colorMap: Record<string, string> = {
      crm: colors.primary,
      erp: colors.success,
      analytics: colors.warning,
      general: colors.gray,
    };
    return colorMap[category] || colors.primary;
  };

  return (
    <TouchableOpacity style={styles.actionCard} onPress={onPress}>
      <View style={[
        styles.iconContainer,
        { backgroundColor: getCategoryColor(action.category) + '20' }
      ]}>
        <Icon
          name={getIconName(action.icon)}
          size={24}
          color={getCategoryColor(action.category)}
        />
      </View>
      <Text style={styles.actionTitle} numberOfLines={1}>
        {action.title}
      </Text>
      <Text style={styles.actionDescription} numberOfLines={2}>
        {action.description}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.lg,
  },
  title: {
    ...typography.h3,
    color: colors.dark,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.caption,
    color: colors.gray,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  categoryContainer: {
    marginBottom: spacing.lg,
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  categoryTitle: {
    ...typography.subtitle,
    color: colors.dark,
    fontWeight: '600',
  },
  actionsContainer: {
    paddingHorizontal: spacing.sm,
    gap: spacing.sm,
  },
  actionCard: {
    backgroundColor: colors.white,
    borderRadius: 12,
    padding: spacing.md,
    marginHorizontal: spacing.xs,
    width: 120,
    alignItems: 'center',
    elevation: 2,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  actionTitle: {
    ...typography.subtitle,
    color: colors.dark,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  actionDescription: {
    ...typography.caption,
    color: colors.gray,
    textAlign: 'center',
    lineHeight: 16,
  },
});