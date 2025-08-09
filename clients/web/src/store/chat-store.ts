import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { subscribeWithSelector } from 'zustand/middleware'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  conversationId?: string
  metadata?: {
    context?: string
    actions?: Array<{
      type: string
      label: string
      data: any
    }>
    attachments?: Array<{
      id: string
      name: string
      type: string
      url: string
    }>
  }
  isLoading?: boolean
  error?: string
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
  metadata?: {
    context?: string
    tags?: string[]
  }
}

interface ChatStore {
  // State
  conversations: Conversation[]
  activeConversationId: string | null
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  connectionStatus: 'connected' | 'connecting' | 'disconnected'
  
  // Actions
  sendMessage: (content: string, conversationId?: string) => Promise<void>
  addMessage: (message: ChatMessage) => void
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void
  deleteMessage: (messageId: string) => void
  clearConversation: (conversationId?: string) => void
  createConversation: (title?: string) => string
  setActiveConversation: (conversationId: string | null) => void
  deleteConversation: (conversationId: string) => void
  regenerateResponse: (messageId: string) => Promise<void>
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setConnectionStatus: (status: 'connected' | 'connecting' | 'disconnected') => void
}

let messageCounter = 0

export const useChatStore = create<ChatStore>()(
  subscribeWithSelector(
    immer((set, get) => ({
      // Initial state
      conversations: [],
      activeConversationId: null,
      messages: [],
      isLoading: false,
      error: null,
      connectionStatus: 'disconnected',

      // Actions
      sendMessage: async (content: string, conversationId?: string) => {
        const state = get()
        
        // Create new conversation if none provided
        let currentConversationId = conversationId || state.activeConversationId
        if (!currentConversationId) {
          currentConversationId = get().createConversation()
        }

        // Create user message
        const userMessage: ChatMessage = {
          id: `msg_${Date.now()}_${messageCounter++}`,
          role: 'user',
          content,
          timestamp: new Date().toISOString(),
          conversationId: currentConversationId,
        }

        // Add user message
        set((state) => {
          state.messages.push(userMessage)
          state.error = null
          state.isLoading = true
          
          // Update conversation
          const conversation = state.conversations.find(c => c.id === currentConversationId)
          if (conversation) {
            conversation.messages.push(userMessage)
            conversation.updatedAt = new Date().toISOString()
          }
        })

        try {
          // Simulate API call
          const response = await simulateAIResponse(content, currentConversationId)
          
          const assistantMessage: ChatMessage = {
            id: `msg_${Date.now()}_${messageCounter++}`,
            role: 'assistant',
            content: response.content,
            timestamp: new Date().toISOString(),
            conversationId: currentConversationId,
            metadata: response.metadata,
          }

          // Add assistant message
          set((state) => {
            state.messages.push(assistantMessage)
            state.isLoading = false
            
            // Update conversation
            const conversation = state.conversations.find(c => c.id === currentConversationId)
            if (conversation) {
              conversation.messages.push(assistantMessage)
              conversation.updatedAt = new Date().toISOString()
            }
          })
        } catch (error) {
          set((state) => {
            state.error = error instanceof Error ? error.message : 'Failed to send message'
            state.isLoading = false
          })
          throw error
        }
      },

      addMessage: (message) =>
        set((state) => {
          state.messages.push(message)
        }),

      updateMessage: (messageId, updates) =>
        set((state) => {
          const messageIndex = state.messages.findIndex(m => m.id === messageId)
          if (messageIndex >= 0) {
            state.messages[messageIndex] = { ...state.messages[messageIndex], ...updates }
          }
        }),

      deleteMessage: (messageId) =>
        set((state) => {
          state.messages = state.messages.filter(m => m.id !== messageId)
        }),

      clearConversation: (conversationId) =>
        set((state) => {
          const targetConversationId = conversationId || state.activeConversationId
          if (targetConversationId) {
            // Clear messages for specific conversation
            state.messages = state.messages.filter(m => m.conversationId !== targetConversationId)
            
            // Update conversation
            const conversation = state.conversations.find(c => c.id === targetConversationId)
            if (conversation) {
              conversation.messages = []
              conversation.updatedAt = new Date().toISOString()
            }
          } else {
            // Clear all messages if no specific conversation
            state.messages = []
          }
        }),

      createConversation: (title) => {
        const conversationId = `conv_${Date.now()}`
        const conversation: Conversation = {
          id: conversationId,
          title: title || `Conversation ${Date.now()}`,
          messages: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }

        set((state) => {
          state.conversations.push(conversation)
          state.activeConversationId = conversationId
        })

        return conversationId
      },

      setActiveConversation: (conversationId) =>
        set((state) => {
          state.activeConversationId = conversationId
          
          if (conversationId) {
            const conversation = state.conversations.find(c => c.id === conversationId)
            state.messages = conversation?.messages || []
          } else {
            state.messages = []
          }
        }),

      deleteConversation: (conversationId) =>
        set((state) => {
          state.conversations = state.conversations.filter(c => c.id !== conversationId)
          
          if (state.activeConversationId === conversationId) {
            state.activeConversationId = null
            state.messages = []
          }
        }),

      regenerateResponse: async (messageId) => {
        const state = get()
        const messageIndex = state.messages.findIndex(m => m.id === messageId)
        
        if (messageIndex >= 0 && messageIndex > 0) {
          const previousMessage = state.messages[messageIndex - 1]
          if (previousMessage.role === 'user') {
            // Remove the failed message
            set((state) => {
              state.messages.splice(messageIndex, 1)
            })
            
            // Resend the previous user message
            await get().sendMessage(previousMessage.content, previousMessage.conversationId)
          }
        }
      },

      setLoading: (loading) =>
        set((state) => {
          state.isLoading = loading
        }),

      setError: (error) =>
        set((state) => {
          state.error = error
        }),

      setConnectionStatus: (status) =>
        set((state) => {
          state.connectionStatus = status
        }),
    }))
  )
)

// Mock AI response simulation
async function simulateAIResponse(userMessage: string, conversationId?: string): Promise<{
  content: string
  metadata?: ChatMessage['metadata']
}> {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000))

  const lowerMessage = userMessage.toLowerCase()
  
  // Context-aware responses based on message content
  if (lowerMessage.includes('sales') || lowerMessage.includes('revenue')) {
    return {
      content: `Based on your recent sales data, here's what I found:\n\n• Total sales this month: $125,430\n• Growth vs last month: +12.5%\n• Top performing product: Premium Wireless Headphones\n• Average order value: $87.50\n\nWould you like me to show you a detailed breakdown or generate a comprehensive sales report?`,
      metadata: {
        context: 'sales_analysis',
        actions: [
          {
            type: 'view_report',
            label: 'View Detailed Report',
            data: { reportType: 'sales', period: 'monthly' }
          },
          {
            type: 'export_data',
            label: 'Export Data',
            data: { format: 'xlsx', type: 'sales' }
          }
        ]
      }
    }
  }
  
  if (lowerMessage.includes('inventory') || lowerMessage.includes('stock')) {
    return {
      content: `Here's your current inventory status:\n\n• Total SKUs: 1,247\n• Low stock items: 12\n• Out of stock: 3\n• Overstock items: 8\n\nCritical items needing attention:\n• Bluetooth Speaker (8 units remaining)\n• Wireless Charging Pad (5 units remaining)\n• USB-C Cable (12 units remaining)\n\nWould you like me to create purchase orders for low stock items?`,
      metadata: {
        context: 'inventory_management',
        actions: [
          {
            type: 'view_inventory',
            label: 'View Full Inventory',
            data: { view: 'detailed' }
          },
          {
            type: 'create_purchase_order',
            label: 'Create Purchase Orders',
            data: { type: 'low_stock' }
          }
        ]
      }
    }
  }
  
  if (lowerMessage.includes('customer') || lowerMessage.includes('order')) {
    return {
      content: `I can help you with customer and order management. Here's a quick overview:\n\n• New customers this week: 45\n• Pending orders: 23\n• Orders shipped today: 12\n• Customer satisfaction: 4.8/5\n\nWhat specific customer or order information would you like me to look up? I can search by:\n• Customer name or email\n• Order number\n• Date range\n• Product or category`,
      metadata: {
        context: 'customer_service',
        actions: [
          {
            type: 'search_customers',
            label: 'Search Customers',
            data: { action: 'search' }
          },
          {
            type: 'search_orders',
            label: 'Search Orders',
            data: { action: 'search' }
          }
        ]
      }
    }
  }

  // Default response
  const responses = [
    "I'd be happy to help you with that! Could you provide more specific details about what you're looking for?",
    "That's an interesting question. Let me help you find the information you need. What specific aspect would you like to explore?",
    "I can assist you with various business operations including sales analysis, inventory management, customer service, and reporting. What would you like to focus on?",
    "Great question! I have access to your business data and can help you with insights, analysis, and actionable recommendations. What specific area interests you?",
  ]
  
  return {
    content: responses[Math.floor(Math.random() * responses.length)],
    metadata: {
      context: 'general_assistance'
    }
  }
}

// Initialize with welcome message
if (typeof window !== 'undefined') {
  setTimeout(() => {
    const store = useChatStore.getState()
    if (store.messages.length === 0) {
      store.addMessage({
        id: 'welcome',
        role: 'system',
        content: 'AI Assistant is ready to help!',
        timestamp: new Date().toISOString(),
      })
    }
  }, 100)
}