import { ChatInterface } from '@/components/chat/chat-interface'

export function ChatPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AI Assistant</h1>
          <p className="text-muted-foreground">
            Get help with your business operations using conversational AI
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Main chat interface */}
        <div className="lg:col-span-3">
          <ChatInterface
            title="WearForce AI Assistant"
            placeholder="Ask me anything about your business..."
            height="calc(100vh - 200px)"
          />
        </div>

        {/* Sidebar with quick actions and suggestions */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="rounded-lg border p-4">
            <h3 className="font-semibold mb-3">Quick Actions</h3>
            <div className="space-y-2">
              {[
                'Show today\'s sales',
                'List low inventory items',
                'Find recent orders',
                'Customer satisfaction report',
                'Revenue analytics',
              ].map((action) => (
                <button
                  key={action}
                  className="w-full text-left text-sm p-2 rounded hover:bg-muted transition-colors"
                  onClick={() => {
                    // TODO: Send message to chat
                    console.log('Quick action:', action)
                  }}
                >
                  {action}
                </button>
              ))}
            </div>
          </div>

          {/* Tips */}
          <div className="rounded-lg border p-4">
            <h3 className="font-semibold mb-3">Tips</h3>
            <div className="text-sm text-muted-foreground space-y-2">
              <p>💡 Ask specific questions for better results</p>
              <p>📊 Request charts and reports</p>
              <p>🔍 Search by customer, product, or order ID</p>
              <p>⚡ Use voice commands (coming soon)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}