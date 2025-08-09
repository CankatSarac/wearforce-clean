import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Mic, MicOff, Paperclip, MoreVertical, RefreshCw } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import { useChatStore } from '@/store/chat-store'
import { cn } from '@/lib/utils'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
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

interface ChatInterfaceProps {
  conversationId?: string
  className?: string
  placeholder?: string
  showHeader?: boolean
  title?: string
  height?: string
}

export function ChatInterface({
  conversationId,
  className,
  placeholder = "Type your message or ask me anything...",
  showHeader = true,
  title = "AI Assistant",
  height = "600px",
}: ChatInterfaceProps) {
  const [input, setInput] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const {
    messages,
    isLoading,
    error,
    sendMessage,
    clearConversation,
    regenerateResponse,
  } = useChatStore()

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return

    const messageContent = input.trim()
    setInput('')
    setIsTyping(true)

    try {
      await sendMessage(messageContent, conversationId)
    } catch (error) {
      console.error('Failed to send message:', error)
    } finally {
      setIsTyping(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleVoiceToggle = () => {
    setIsRecording(!isRecording)
    // TODO: Implement voice recording
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      // TODO: Implement file upload
      console.log('Files selected:', files)
    }
  }

  const formatMessageTime = (timestamp: string) => {
    return format(new Date(timestamp), 'HH:mm')
  }

  const renderMessage = (message: ChatMessage) => {
    const isUser = message.role === 'user'
    const isSystem = message.role === 'system'

    if (isSystem) {
      return (
        <div key={message.id} className="flex justify-center my-4">
          <Badge variant="secondary" className="text-xs">
            {message.content}
          </Badge>
        </div>
      )
    }

    return (
      <div
        key={message.id}
        className={cn(
          "flex gap-3 mb-4",
          isUser ? "justify-end" : "justify-start"
        )}
      >
        {!isUser && (
          <Avatar className="w-8 h-8 mt-1">
            <AvatarFallback>
              <Bot className="w-4 h-4" />
            </AvatarFallback>
          </Avatar>
        )}
        
        <div className={cn(
          "flex flex-col max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}>
          <div className={cn(
            "rounded-lg px-3 py-2 text-sm",
            isUser 
              ? "bg-primary text-primary-foreground" 
              : "bg-muted border"
          )}>
            {message.isLoading ? (
              <div className="flex items-center gap-1">
                <div className="animate-pulse">Thinking...</div>
              </div>
            ) : message.error ? (
              <div className="text-destructive">
                <p>Failed to send message</p>
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => regenerateResponse(message.id)}
                  className="p-0 h-auto text-xs"
                >
                  Try again
                </Button>
              </div>
            ) : (
              <div className="whitespace-pre-wrap">{message.content}</div>
            )}
          </div>
          
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-muted-foreground">
              {formatMessageTime(message.timestamp)}
            </span>
            {message.metadata?.actions && message.metadata.actions.length > 0 && (
              <div className="flex gap-1">
                {message.metadata.actions.map((action, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={() => {
                      // TODO: Handle action clicks
                      console.log('Action clicked:', action)
                    }}
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>

        {isUser && (
          <Avatar className="w-8 h-8 mt-1">
            <AvatarFallback>
              <User className="w-4 h-4" />
            </AvatarFallback>
          </Avatar>
        )}
      </div>
    )
  }

  return (
    <Card className={cn("flex flex-col", className)} style={{ height }}>
      {showHeader && (
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg font-semibold">{title}</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Chat Options</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={clearConversation}>
                Clear Conversation
              </DropdownMenuItem>
              <DropdownMenuItem>
                Export Chat
              </DropdownMenuItem>
              <DropdownMenuItem>
                Settings
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardHeader>
      )}

      <CardContent className="flex-1 flex flex-col p-0">
        {/* Messages Area */}
        <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <Bot className="w-8 h-8 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">How can I help you today?</h3>
                <p className="text-sm text-muted-foreground max-w-md">
                  I can help you with customer queries, order management, inventory tracking, 
                  sales analysis, and much more. Just ask me anything!
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                {[
                  "Show me today's sales",
                  "List low inventory items",
                  "Find customer orders",
                  "Generate sales report",
                ].map((suggestion) => (
                  <Button
                    key={suggestion}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setInput(suggestion)
                      inputRef.current?.focus()
                    }}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              {messages.map(renderMessage)}
              {isTyping && (
                <div className="flex gap-3 mb-4">
                  <Avatar className="w-8 h-8 mt-1">
                    <AvatarFallback>
                      <Bot className="w-4 h-4" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-muted border rounded-lg px-3 py-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </ScrollArea>

        <Separator />

        {/* Input Area */}
        <div className="p-4">
          {error && (
            <div className="mb-2 p-2 text-sm text-destructive bg-destructive/10 rounded border border-destructive/20">
              {error}
            </div>
          )}
          
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={placeholder}
                disabled={isLoading}
                className="pr-12"
              />
              
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "absolute right-1 top-1 h-8 w-8 p-0",
                  isRecording && "text-red-500"
                )}
                onClick={handleVoiceToggle}
              >
                {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
            </div>

            <Button
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              size="sm"
            >
              {isLoading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            onChange={handleFileUpload}
            accept="image/*,.pdf,.doc,.docx,.txt"
          />
        </div>
      </CardContent>
    </Card>
  )
}