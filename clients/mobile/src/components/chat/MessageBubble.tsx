import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { ChatMessage } from '@types/chat';
import { colors, spacing, typography } from '@utils/theme';

interface MessageBubbleProps {
  message: ChatMessage;
  onPlayAudio?: (audioData: string) => void;
  animated?: boolean;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ 
  message, 
  onPlayAudio,
  animated = true 
}) => {
  const fadeAnim = React.useRef(new Animated.Value(0)).current;
  const slideAnim = React.useRef(new Animated.Value(20)).current;

  React.useEffect(() => {
    if (animated) {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [animated, fadeAnim, slideAnim]);

  const formatTimestamp = (timestamp: Date) => {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    
    return timestamp.toLocaleDateString();
  };

  const renderMessageContent = () => {
    switch (message.type) {
      case 'voice':
        return (
          <View style={styles.voiceContainer}>
            <TouchableOpacity
              style={styles.voiceButton}
              onPress={() => message.audioData && onPlayAudio?.(message.audioData)}
            >
              <Icon name="play-arrow" size={20} color={colors.white} />
            </TouchableOpacity>
            <View style={styles.voiceTextContainer}>
              <Text style={[
                styles.messageText,
                { color: message.isFromUser ? colors.white : colors.dark }
              ]}>
                {message.content || 'Voice message'}
              </Text>
              {message.transcription && (
                <Text style={[
                  styles.transcriptionText,
                  { color: message.isFromUser ? colors.white : colors.gray }
                ]}>
                  "{message.transcription}"
                </Text>
              )}
            </View>
            <Icon 
              name="mic" 
              size={16} 
              color={message.isFromUser ? colors.white : colors.primary} 
            />
          </View>
        );
      
      case 'system':
        return (
          <View style={styles.systemContainer}>
            <Icon name="info" size={16} color={colors.gray} />
            <Text style={styles.systemText}>{message.content}</Text>
          </View>
        );
      
      case 'error':
        return (
          <View style={styles.errorContainer}>
            <Icon name="error" size={16} color={colors.error} />
            <Text style={styles.errorText}>{message.content}</Text>
          </View>
        );
      
      default:
        return (
          <Text style={[
            styles.messageText,
            { color: message.isFromUser ? colors.white : colors.dark }
          ]}>
            {message.content}
          </Text>
        );
    }
  };

  const containerStyle = [
    styles.container,
    message.isFromUser ? styles.userContainer : styles.assistantContainer
  ];

  const bubbleStyle = [
    styles.bubble,
    message.isFromUser ? styles.userBubble : styles.assistantBubble,
    message.type === 'system' && styles.systemBubble,
    message.type === 'error' && styles.errorBubble,
  ];

  if (animated) {
    return (
      <Animated.View 
        style={[
          containerStyle,
          {
            opacity: fadeAnim,
            transform: [{ translateY: slideAnim }]
          }
        ]}
      >
        <View style={bubbleStyle}>
          {renderMessageContent()}
          <Text style={[
            styles.timestamp,
            { 
              color: message.isFromUser 
                ? colors.white + '90' 
                : colors.gray 
            }
          ]}>
            {formatTimestamp(message.timestamp)}
          </Text>
        </View>
      </Animated.View>
    );
  }

  return (
    <View style={containerStyle}>
      <View style={bubbleStyle}>
        {renderMessageContent()}
        <Text style={[
          styles.timestamp,
          { 
            color: message.isFromUser 
              ? colors.white + '90' 
              : colors.gray 
          }
        ]}>
          {formatTimestamp(message.timestamp)}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: spacing.xs,
    marginHorizontal: spacing.md,
  },
  userContainer: {
    alignItems: 'flex-end',
  },
  assistantContainer: {
    alignItems: 'flex-start',
  },
  bubble: {
    maxWidth: '80%',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 18,
  },
  userBubble: {
    backgroundColor: colors.primary,
    borderBottomRightRadius: 6,
  },
  assistantBubble: {
    backgroundColor: colors.lightGray,
    borderBottomLeftRadius: 6,
  },
  systemBubble: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    alignSelf: 'center',
    maxWidth: '90%',
  },
  errorBubble: {
    backgroundColor: colors.error + '20',
    borderWidth: 1,
    borderColor: colors.error,
  },
  messageText: {
    ...typography.body,
    lineHeight: 20,
  },
  timestamp: {
    ...typography.caption,
    marginTop: spacing.xs,
    fontSize: 11,
  },
  voiceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  voiceButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  voiceTextContainer: {
    flex: 1,
  },
  transcriptionText: {
    ...typography.caption,
    fontStyle: 'italic',
    marginTop: 2,
  },
  systemContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    justifyContent: 'center',
  },
  systemText: {
    ...typography.caption,
    color: colors.gray,
    textAlign: 'center',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  errorText: {
    ...typography.caption,
    color: colors.error,
  },
});