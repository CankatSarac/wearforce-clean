import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Animated,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAppDispatch, useAppSelector } from '@hooks/redux';
import { useWebSocket } from '@hooks/useWebSocket';
import { useVoiceRecording } from '@hooks/useVoiceRecording';
import { ChatMessage } from '@types/chat';
import { MessageBubble } from '@components/chat/MessageBubble';
import { VoiceRecordButton } from '@components/chat/VoiceRecordButton';
import { QuickActions } from '@components/chat/QuickActions';
import { LoadingIndicator } from '@components/common/LoadingIndicator';
import { chatActions } from '@store/slices/chatSlice';
import { colors, spacing, typography } from '@utils/theme';
import { chatService } from '@services/chatService';

export const ChatScreen: React.FC = () => {
  const dispatch = useAppDispatch();
  const { messages, isLoading, error } = useAppSelector((state) => state.chat);
  const [inputText, setInputText] = useState('');
  const [showQuickActions, setShowQuickActions] = useState(true);
  
  const flatListRef = useRef<FlatList>(null);
  const fadeAnim = useRef(new Animated.Value(1)).current;
  
  const { isConnected, sendMessage } = useWebSocket();
  const {
    isRecording,
    startRecording,
    stopRecording,
    audioLevel,
    hasPermission: hasAudioPermission,
  } = useVoiceRecording();

  useEffect(() => {
    loadConversationHistory();
  }, []);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  useEffect(() => {
    // Hide quick actions when there are messages
    setShowQuickActions(messages.length === 0);
  }, [messages.length]);

  const loadConversationHistory = async () => {
    try {
      dispatch(chatActions.setLoading(true));
      const history = await chatService.getConversationHistory();
      dispatch(chatActions.setMessages(history));
    } catch (err) {
      console.error('Failed to load conversation history:', err);
      dispatch(chatActions.setError('Failed to load conversation history'));
    } finally {
      dispatch(chatActions.setLoading(false));
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const message: ChatMessage = {
      id: Date.now().toString(),
      content: content.trim(),
      isFromUser: true,
      timestamp: new Date(),
      type: 'text',
    };

    // Add message immediately to UI
    dispatch(chatActions.addMessage(message));
    setInputText('');

    try {
      // Send via WebSocket if connected, otherwise use HTTP
      if (isConnected) {
        sendMessage({
          type: 'chat',
          content: content.trim(),
          timestamp: new Date(),
        });
      } else {
        dispatch(chatActions.setLoading(true));
        const response = await chatService.sendMessage(content.trim());
        dispatch(chatActions.addMessage({
          id: response.messageId,
          content: response.content,
          isFromUser: false,
          timestamp: new Date(response.timestamp),
          type: 'text',
        }));
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      Alert.alert('Error', 'Failed to send message. Please try again.');
    } finally {
      dispatch(chatActions.setLoading(false));
    }
  };

  const handleVoiceMessage = async (transcription: string) => {
    if (transcription.trim()) {
      await handleSendMessage(transcription);
    }
  };

  const handleQuickAction = (action: string) => {
    handleSendMessage(action);
  };

  const renderMessage = ({ item }: { item: ChatMessage }) => (
    <MessageBubble message={item} />
  );

  const renderEmptyState = () => (
    <View style={styles.emptyContainer}>
      <Icon name="chat-bubble-outline" size={64} color={colors.lightGray} />
      <Text style={styles.emptyText}>Start a conversation</Text>
      <Text style={styles.emptySubtext}>
        Ask me about customers, orders, inventory, or anything else!
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView 
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>WearForce Assistant</Text>
          <View style={styles.connectionStatus}>
            <View 
              style={[
                styles.connectionDot, 
                { backgroundColor: isConnected ? colors.success : colors.warning }
              ]} 
            />
            <Text style={styles.connectionText}>
              {isConnected ? 'Connected' : 'Offline'}
            </Text>
          </View>
        </View>

        {/* Messages */}
        <View style={styles.messagesContainer}>
          {messages.length === 0 && !isLoading ? (
            renderEmptyState()
          ) : (
            <FlatList
              ref={flatListRef}
              data={messages}
              renderItem={renderMessage}
              keyExtractor={(item) => item.id}
              style={styles.messagesList}
              contentContainerStyle={styles.messagesContent}
              showsVerticalScrollIndicator={false}
            />
          )}
          
          {isLoading && <LoadingIndicator />}
        </View>

        {/* Quick Actions */}
        {showQuickActions && (
          <Animated.View style={[styles.quickActionsContainer, { opacity: fadeAnim }]}>
            <QuickActions onAction={handleQuickAction} />
          </Animated.View>
        )}

        {/* Input Area */}
        <View style={styles.inputContainer}>
          <View style={styles.inputRow}>
            <TextInput
              style={styles.textInput}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Type your message..."
              placeholderTextColor={colors.gray}
              multiline
              maxLength={500}
              onSubmitEditing={() => handleSendMessage(inputText)}
              blurOnSubmit={false}
            />
            
            {inputText.trim() ? (
              <TouchableOpacity
                style={styles.sendButton}
                onPress={() => handleSendMessage(inputText)}
                activeOpacity={0.7}
              >
                <Icon name="send" size={24} color={colors.white} />
              </TouchableOpacity>
            ) : (
              <VoiceRecordButton
                isRecording={isRecording}
                audioLevel={audioLevel}
                onStartRecording={startRecording}
                onStopRecording={stopRecording}
                onTranscription={handleVoiceMessage}
                hasPermission={hasAudioPermission}
              />
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.lightGray,
    elevation: 2,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  headerTitle: {
    ...typography.h3,
    color: colors.dark,
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: spacing.xs,
  },
  connectionText: {
    ...typography.caption,
    color: colors.gray,
  },
  messagesContainer: {
    flex: 1,
  },
  messagesList: {
    flex: 1,
  },
  messagesContent: {
    paddingVertical: spacing.md,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
  },
  emptyText: {
    ...typography.h3,
    color: colors.gray,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
  emptySubtext: {
    ...typography.body,
    color: colors.lightGray,
    marginTop: spacing.sm,
    textAlign: 'center',
    lineHeight: 20,
  },
  quickActionsContainer: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  inputContainer: {
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.lightGray,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
  },
  textInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.lightGray,
    borderRadius: 20,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    maxHeight: 100,
    ...typography.body,
    color: colors.dark,
  },
  sendButton: {
    backgroundColor: colors.primary,
    borderRadius: 24,
    padding: spacing.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
});