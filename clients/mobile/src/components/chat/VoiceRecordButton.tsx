import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Alert,
  Vibration,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { colors, spacing, typography } from '@utils/theme';

interface VoiceRecordButtonProps {
  isRecording: boolean;
  audioLevel: number;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onTranscription: (transcription: string) => void;
  hasPermission: boolean;
}

export const VoiceRecordButton: React.FC<VoiceRecordButtonProps> = ({
  isRecording,
  audioLevel,
  onStartRecording,
  onStopRecording,
  onTranscription,
  hasPermission,
}) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const waveAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isRecording) {
      // Start pulsing animation
      const pulseAnimation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 500,
            useNativeDriver: true,
          }),
        ])
      );

      // Audio level animation
      const scaleValue = 1 + (audioLevel * 0.3);
      Animated.timing(scaleAnim, {
        toValue: scaleValue,
        duration: 100,
        useNativeDriver: true,
      }).start();

      // Wave animation
      const waveAnimation = Animated.loop(
        Animated.timing(waveAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        })
      );

      pulseAnimation.start();
      waveAnimation.start();

      return () => {
        pulseAnimation.stop();
        waveAnimation.stop();
      };
    } else {
      // Reset animations
      Animated.parallel([
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(scaleAnim, {
          toValue: 1,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(waveAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [isRecording, audioLevel, pulseAnim, scaleAnim, waveAnim]);

  const handlePress = () => {
    if (!hasPermission) {
      Alert.alert(
        'Permission Required',
        'Microphone permission is required to record voice messages.',
        [{ text: 'OK' }]
      );
      return;
    }

    if (isRecording) {
      Vibration.vibrate(50);
      onStopRecording();
    } else {
      Vibration.vibrate(50);
      onStartRecording();
    }
  };

  const waveOpacity = waveAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.6],
  });

  const waveScale = waveAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 2.5],
  });

  return (
    <View style={styles.container}>
      {isRecording && (
        <>
          {/* Outer wave */}
          <Animated.View
            style={[
              styles.wave,
              {
                opacity: waveOpacity,
                transform: [{ scale: waveScale }],
              },
            ]}
          />
          {/* Inner wave */}
          <Animated.View
            style={[
              styles.wave,
              styles.innerWave,
              {
                opacity: waveOpacity,
                transform: [{ scale: waveAnim }],
              },
            ]}
          />
        </>
      )}

      <Animated.View
        style={[
          styles.buttonContainer,
          {
            transform: [
              { scale: pulseAnim },
              { scale: scaleAnim },
            ],
          },
        ]}
      >
        <TouchableOpacity
          style={[
            styles.button,
            isRecording ? styles.recordingButton : styles.defaultButton,
            !hasPermission && styles.disabledButton,
          ]}
          onPress={handlePress}
          activeOpacity={0.8}
          disabled={!hasPermission}
        >
          <Icon
            name={isRecording ? 'stop' : 'mic'}
            size={28}
            color={colors.white}
          />
        </TouchableOpacity>
      </Animated.View>

      {isRecording && (
        <View style={styles.recordingIndicator}>
          <View style={styles.recordingDot} />
          <Text style={styles.recordingText}>Recording...</Text>
        </View>
      )}

      {!hasPermission && (
        <View style={styles.permissionWarning}>
          <Icon name="warning" size={16} color={colors.error} />
          <Text style={styles.permissionText}>Mic permission required</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  wave: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.primary,
  },
  innerWave: {
    width: 80,
    height: 80,
    borderRadius: 40,
  },
  buttonContainer: {
    position: 'relative',
    zIndex: 1,
  },
  button: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  defaultButton: {
    backgroundColor: colors.primary,
  },
  recordingButton: {
    backgroundColor: colors.error,
  },
  disabledButton: {
    backgroundColor: colors.gray,
    elevation: 0,
    shadowOpacity: 0,
  },
  recordingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
    gap: spacing.xs,
  },
  recordingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.error,
  },
  recordingText: {
    ...typography.caption,
    color: colors.error,
    fontWeight: '600',
  },
  permissionWarning: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
    gap: spacing.xs,
  },
  permissionText: {
    ...typography.caption,
    color: colors.error,
    fontSize: 11,
  },
});