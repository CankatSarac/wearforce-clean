export interface ChatMessage {
  id: string;
  content: string;
  isFromUser: boolean;
  timestamp: Date;
  type: 'text' | 'voice' | 'system' | 'error';
  metadata?: {
    audioUrl?: string;
    duration?: number;
    transcription?: string;
    confidence?: number;
    [key: string]: any;
  };
}

export interface ChatResponse {
  messageId: string;
  content: string;
  timestamp: string;
  type: 'text' | 'voice' | 'system';
  metadata?: {
    audioUrl?: string;
    suggestions?: string[];
    actions?: ChatAction[];
    [key: string]: any;
  };
}

export interface ChatAction {
  id: string;
  label: string;
  type: 'navigation' | 'query' | 'action';
  payload?: any;
}

export interface ChatRequest {
  content: string;
  type: 'text' | 'voice';
  timestamp: string;
  metadata?: {
    audioData?: string;
    duration?: number;
    language?: string;
    [key: string]: any;
  };
}

export interface ConversationHistory {
  messages: ChatMessage[];
  total: number;
  hasMore: boolean;
  lastMessageId?: string;
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  typingIndicator: boolean;
}

export interface WebSocketMessage {
  type: 'chat' | 'notification' | 'update' | 'heartbeat' | 'error' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    messageId?: string;
    userId?: string;
    sessionId?: string;
    [key: string]: any;
  };
}

export interface VoiceRecordingState {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  audioLevel: number;
  audioUrl?: string;
  transcription?: string;
  isProcessing: boolean;
  error?: string;
}

export interface QuickAction {
  id: string;
  title: string;
  subtitle?: string;
  icon: string;
  query: string;
  category: 'crm' | 'erp' | 'general' | 'navigation';
}