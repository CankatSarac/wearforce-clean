import AsyncStorage from '@react-native-async-storage/async-storage';
import { ChatMessage } from '@types/chat';

const BASE_URL = 'https://api.wearforce.com/api/v1';
const STORAGE_KEY = 'wearforce_chat_history';

export interface ChatResponse {
  messageId: string;
  content: string;
  timestamp: string;
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface SendMessageRequest {
  content: string;
  type?: 'text' | 'voice';
  audioData?: string;
  context?: Record<string, any>;
}

class ChatService {
  private async getAuthHeader(): Promise<{ Authorization: string } | null> {
    try {
      const token = await AsyncStorage.getItem('accessToken');
      return token ? { Authorization: `Bearer ${token}` } : null;
    } catch (error) {
      console.error('Failed to get auth token:', error);
      return null;
    }
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const authHeader = await this.getAuthHeader();
    if (!authHeader) {
      throw new Error('Authentication required');
    }

    const url = `${BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  async sendMessage(content: string, type: 'text' | 'voice' = 'text'): Promise<ChatResponse> {
    const request: SendMessageRequest = {
      content,
      type,
      context: {
        platform: 'mobile',
        timestamp: new Date().toISOString(),
      },
    };

    return this.makeRequest<ChatResponse>('/chat/messages', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async sendVoiceMessage(
    audioData: string,
    transcript?: string
  ): Promise<ChatResponse> {
    const request: SendMessageRequest = {
      content: transcript || '',
      type: 'voice',
      audioData,
      context: {
        platform: 'mobile',
        timestamp: new Date().toISOString(),
        hasTranscript: Boolean(transcript),
      },
    };

    return this.makeRequest<ChatResponse>('/chat/messages', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getConversationHistory(limit: number = 50): Promise<ChatMessage[]> {
    try {
      // Try to get from API first
      const response = await this.makeRequest<{
        messages: Array<{
          id: string;
          content: string;
          isFromUser: boolean;
          timestamp: string;
          type: string;
          metadata?: Record<string, any>;
        }>;
      }>(`/chat/history?limit=${limit}`);

      const messages = response.messages.map(msg => ({
        id: msg.id,
        content: msg.content,
        isFromUser: msg.isFromUser,
        timestamp: new Date(msg.timestamp),
        type: msg.type as 'text' | 'voice' | 'system' | 'error',
        metadata: msg.metadata,
      }));

      // Cache the messages locally
      await this.saveConversationHistory(messages);
      return messages;
    } catch (error) {
      console.warn('Failed to fetch conversation history from API, using local cache:', error);
      // Fallback to local storage
      return this.getLocalConversationHistory();
    }
  }

  async saveConversationHistory(messages: ChatMessage[]): Promise<void> {
    try {
      const serializedMessages = messages.map(msg => ({
        ...msg,
        timestamp: msg.timestamp.toISOString(),
      }));
      
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(serializedMessages));
    } catch (error) {
      console.error('Failed to save conversation history:', error);
    }
  }

  async getLocalConversationHistory(): Promise<ChatMessage[]> {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEY);
      if (!stored) return [];

      const parsed = JSON.parse(stored);
      return parsed.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
      }));
    } catch (error) {
      console.error('Failed to get local conversation history:', error);
      return [];
    }
  }

  async addMessageToHistory(message: ChatMessage): Promise<void> {
    try {
      const currentHistory = await this.getLocalConversationHistory();
      const updatedHistory = [...currentHistory, message];
      
      // Keep only last 100 messages locally
      if (updatedHistory.length > 100) {
        updatedHistory.splice(0, updatedHistory.length - 100);
      }
      
      await this.saveConversationHistory(updatedHistory);
    } catch (error) {
      console.error('Failed to add message to history:', error);
    }
  }

  async clearConversationHistory(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error('Failed to clear conversation history:', error);
    }
  }

  // Quick actions
  async getQuickActions(): Promise<Array<{
    id: string;
    title: string;
    description: string;
    action: string;
    icon: string;
    category: string;
  }>> {
    try {
      return await this.makeRequest<Array<{
        id: string;
        title: string;
        description: string;
        action: string;
        icon: string;
        category: string;
      }>>('/chat/quick-actions');
    } catch (error) {
      console.warn('Failed to get quick actions from API, using defaults:', error);
      return [
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
          title: 'Orders',
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
          title: 'Sales',
          description: 'View sales data',
          action: 'Show me today\'s sales',
          icon: 'trending-up',
          category: 'analytics',
        },
      ];
    }
  }

  // Search functionality
  async searchMessages(query: string): Promise<ChatMessage[]> {
    try {
      const response = await this.makeRequest<{
        messages: Array<{
          id: string;
          content: string;
          isFromUser: boolean;
          timestamp: string;
          type: string;
          metadata?: Record<string, any>;
        }>;
      }>(`/chat/search?q=${encodeURIComponent(query)}`);

      return response.messages.map(msg => ({
        id: msg.id,
        content: msg.content,
        isFromUser: msg.isFromUser,
        timestamp: new Date(msg.timestamp),
        type: msg.type as 'text' | 'voice' | 'system' | 'error',
        metadata: msg.metadata,
      }));
    } catch (error) {
      console.error('Failed to search messages:', error);
      // Fallback to local search
      const history = await this.getLocalConversationHistory();
      return history.filter(msg =>
        msg.content.toLowerCase().includes(query.toLowerCase())
      );
    }
  }

  // Feedback
  async sendFeedback(messageId: string, feedback: 'positive' | 'negative', comment?: string): Promise<void> {
    try {
      await this.makeRequest('/chat/feedback', {
        method: 'POST',
        body: JSON.stringify({
          messageId,
          feedback,
          comment,
          timestamp: new Date().toISOString(),
        }),
      });
    } catch (error) {
      console.error('Failed to send feedback:', error);
      throw error;
    }
  }

  // Analytics
  async getUsageStats(): Promise<{
    totalMessages: number;
    voiceMessages: number;
    textMessages: number;
    averageResponseTime: number;
    mostUsedFeatures: string[];
  }> {
    try {
      return await this.makeRequest('/chat/stats');
    } catch (error) {
      console.error('Failed to get usage stats:', error);
      // Return default stats
      const history = await this.getLocalConversationHistory();
      const userMessages = history.filter(msg => msg.isFromUser);
      
      return {
        totalMessages: userMessages.length,
        voiceMessages: userMessages.filter(msg => msg.type === 'voice').length,
        textMessages: userMessages.filter(msg => msg.type === 'text').length,
        averageResponseTime: 0,
        mostUsedFeatures: [],
      };
    }
  }
}

export const chatService = new ChatService();