import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { BaseToast, ErrorToast, InfoToast, ToastConfig } from 'react-native-toast-message';
import { colors, spacing, typography } from './theme';

const CustomSuccessToast = (props: any) => (
  <BaseToast
    {...props}
    style={[styles.baseToast, styles.successToast]}
    contentContainerStyle={styles.contentContainer}
    text1Style={styles.text1}
    text2Style={styles.text2}
    renderLeadingIcon={() => (
      <View style={styles.iconContainer}>
        <Icon name="check-circle" size={24} color={colors.success} />
      </View>
    )}
  />
);

const CustomErrorToast = (props: any) => (
  <ErrorToast
    {...props}
    style={[styles.baseToast, styles.errorToast]}
    contentContainerStyle={styles.contentContainer}
    text1Style={styles.text1}
    text2Style={styles.text2}
    renderLeadingIcon={() => (
      <View style={styles.iconContainer}>
        <Icon name="error" size={24} color={colors.error} />
      </View>
    )}
  />
);

const CustomInfoToast = (props: any) => (
  <InfoToast
    {...props}
    style={[styles.baseToast, styles.infoToast]}
    contentContainerStyle={styles.contentContainer}
    text1Style={styles.text1}
    text2Style={styles.text2}
    renderLeadingIcon={() => (
      <View style={styles.iconContainer}>
        <Icon name="info" size={24} color={colors.primary} />
      </View>
    )}
  />
);

const CustomWarningToast = (props: any) => (
  <BaseToast
    {...props}
    style={[styles.baseToast, styles.warningToast]}
    contentContainerStyle={styles.contentContainer}
    text1Style={styles.text1}
    text2Style={styles.text2}
    renderLeadingIcon={() => (
      <View style={styles.iconContainer}>
        <Icon name="warning" size={24} color={colors.warning} />
      </View>
    )}
  />
);

const VoiceToast = (props: any) => (
  <View style={[styles.baseToast, styles.voiceToast]}>
    <View style={styles.iconContainer}>
      <Icon name="mic" size={24} color={colors.white} />
    </View>
    <View style={styles.voiceContent}>
      <Text style={styles.voiceTitle}>{props.text1}</Text>
      {props.text2 && <Text style={styles.voiceSubtitle}>{props.text2}</Text>}
    </View>
    <View style={styles.voiceIndicator}>
      <View style={[styles.voiceDot, { opacity: 0.3 }]} />
      <View style={[styles.voiceDot, { opacity: 0.6 }]} />
      <View style={[styles.voiceDot, { opacity: 1.0 }]} />
    </View>
  </View>
);

const ConnectionToast = (props: any) => {
  const isConnected = props.props?.isConnected;
  const iconName = isConnected ? 'wifi' : 'wifi-off';
  const iconColor = isConnected ? colors.success : colors.error;
  const borderColor = isConnected ? colors.success : colors.error;

  return (
    <View style={[styles.baseToast, styles.connectionToast, { borderLeftColor: borderColor }]}>
      <View style={styles.iconContainer}>
        <Icon name={iconName} size={24} color={iconColor} />
      </View>
      <View style={styles.contentContainer}>
        <Text style={styles.text1}>{props.text1}</Text>
        {props.text2 && <Text style={styles.text2}>{props.text2}</Text>}
      </View>
    </View>
  );
};

export const toastConfig: ToastConfig = {
  success: CustomSuccessToast,
  error: CustomErrorToast,
  info: CustomInfoToast,
  warning: CustomWarningToast,
  voice: VoiceToast,
  connection: ConnectionToast,
};

const styles = StyleSheet.create({
  baseToast: {
    height: 70,
    width: '90%',
    borderRadius: 12,
    borderLeftWidth: 4,
    backgroundColor: colors.white,
    shadowColor: colors.dark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
    paddingHorizontal: spacing.sm,
  },
  successToast: {
    borderLeftColor: colors.success,
  },
  errorToast: {
    borderLeftColor: colors.error,
  },
  infoToast: {
    borderLeftColor: colors.primary,
  },
  warningToast: {
    borderLeftColor: colors.warning,
  },
  voiceToast: {
    backgroundColor: colors.primary,
    borderLeftWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  connectionToast: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  contentContainer: {
    flex: 1,
    paddingHorizontal: spacing.sm,
  },
  iconContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.background,
    marginRight: spacing.sm,
  },
  text1: {
    ...typography.subtitle,
    color: colors.dark,
    fontWeight: '600',
  },
  text2: {
    ...typography.caption,
    color: colors.gray,
    marginTop: 2,
  },
  voiceContent: {
    flex: 1,
    marginHorizontal: spacing.sm,
  },
  voiceTitle: {
    ...typography.subtitle,
    color: colors.white,
    fontWeight: '600',
  },
  voiceSubtitle: {
    ...typography.caption,
    color: colors.white + 'CC',
    marginTop: 2,
  },
  voiceIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  voiceDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.white,
  },
});

// Toast helper functions
export const showToast = {
  success: (title: string, message?: string) => {
    Toast.show({
      type: 'success',
      text1: title,
      text2: message,
      position: 'top',
      visibilityTime: 3000,
    });
  },

  error: (title: string, message?: string) => {
    Toast.show({
      type: 'error',
      text1: title,
      text2: message,
      position: 'top',
      visibilityTime: 4000,
    });
  },

  info: (title: string, message?: string) => {
    Toast.show({
      type: 'info',
      text1: title,
      text2: message,
      position: 'top',
      visibilityTime: 3000,
    });
  },

  warning: (title: string, message?: string) => {
    Toast.show({
      type: 'warning',
      text1: title,
      text2: message,
      position: 'top',
      visibilityTime: 3500,
    });
  },

  voice: (title: string, message?: string) => {
    Toast.show({
      type: 'voice',
      text1: title,
      text2: message,
      position: 'bottom',
      visibilityTime: 2000,
    });
  },

  connection: (isConnected: boolean) => {
    Toast.show({
      type: 'connection',
      text1: isConnected ? 'Connected' : 'Connection Lost',
      text2: isConnected ? 'You\'re back online' : 'Working in offline mode',
      props: { isConnected },
      position: 'top',
      visibilityTime: 2500,
    });
  },
};