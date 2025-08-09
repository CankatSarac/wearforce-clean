-- Initialize NLU Service Database
-- This script sets up initial database schema and data for the NLU service

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create conversation tracking tables
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255),
    title TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    intent VARCHAR(100),
    confidence FLOAT,
    tools_used TEXT[],
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sequence_number INTEGER,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_conversations_conversation_id ON conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_role ON conversation_messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_intent ON conversation_messages(intent);
CREATE INDEX IF NOT EXISTS idx_messages_sequence ON conversation_messages(sequence_number);

-- Full-text search index for message content
CREATE INDEX IF NOT EXISTS idx_messages_content_search ON conversation_messages USING gin(to_tsvector('english', content));

-- Create intent analytics table
CREATE TABLE IF NOT EXISTS intent_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_name VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    user_id VARCHAR(255),
    conversation_id VARCHAR(255),
    text_sample TEXT,
    entities JSONB DEFAULT '[]',
    success BOOLEAN DEFAULT true,
    processing_time FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intent_analytics_intent ON intent_analytics(intent_name);
CREATE INDEX IF NOT EXISTS idx_intent_analytics_timestamp ON intent_analytics(timestamp);
CREATE INDEX IF NOT EXISTS idx_intent_analytics_user_id ON intent_analytics(user_id);

-- Create tool execution tracking table
CREATE TABLE IF NOT EXISTS tool_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id VARCHAR(255) UNIQUE NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    conversation_id VARCHAR(255),
    user_id VARCHAR(255),
    parameters JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    execution_time FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_executions_tool_name ON tool_executions(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_executions_conversation_id ON tool_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_executions_timestamp ON tool_executions(timestamp);
CREATE INDEX IF NOT EXISTS idx_tool_executions_success ON tool_executions(success);

-- Create entity extraction tracking table
CREATE TABLE IF NOT EXISTS entity_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    text_sample TEXT NOT NULL,
    entities JSONB DEFAULT '[]',
    extraction_method VARCHAR(50), -- spacy, business, regex
    processing_time FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_extractions_timestamp ON entity_extractions(timestamp);
CREATE INDEX IF NOT EXISTS idx_entity_extractions_method ON entity_extractions(extraction_method);

-- Create workflow execution tracking
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id VARCHAR(255) NOT NULL,
    workflow_state JSONB DEFAULT '{}',
    routing_decision VARCHAR(50), -- tools, rag, direct
    agent_type VARCHAR(50), -- crm_agent, erp_agent, etc.
    execution_time FLOAT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_conversation_id ON workflow_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_routing ON workflow_executions(routing_decision);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_agent_type ON workflow_executions(agent_type);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_timestamp ON workflow_executions(timestamp);

-- Update timestamps trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON conversations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample data for testing
INSERT INTO conversations (conversation_id, user_id, title) VALUES 
('sample-conv-123', 'user-456', 'Sample Conversation')
ON CONFLICT (conversation_id) DO NOTHING;

INSERT INTO conversation_messages (conversation_id, role, content, intent, confidence) VALUES 
('sample-conv-123', 'user', 'Hello, I need to create a new contact', 'create_contact', 0.9),
('sample-conv-123', 'assistant', 'I can help you create a new contact. What information do you have?', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Create views for analytics
CREATE OR REPLACE VIEW conversation_stats AS
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as total_conversations,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_duration_seconds
FROM conversations 
WHERE is_active = true
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;

CREATE OR REPLACE VIEW intent_stats AS
SELECT 
    intent_name,
    COUNT(*) as total_occurrences,
    AVG(confidence_score) as avg_confidence,
    COUNT(CASE WHEN success THEN 1 END) as successful_predictions,
    COUNT(CASE WHEN success THEN 1 END) * 100.0 / COUNT(*) as success_rate
FROM intent_analytics 
GROUP BY intent_name
ORDER BY total_occurrences DESC;

CREATE OR REPLACE VIEW tool_stats AS
SELECT 
    tool_name,
    COUNT(*) as total_executions,
    COUNT(CASE WHEN success THEN 1 END) as successful_executions,
    COUNT(CASE WHEN success THEN 1 END) * 100.0 / COUNT(*) as success_rate,
    AVG(execution_time) as avg_execution_time,
    MAX(timestamp) as last_used
FROM tool_executions 
GROUP BY tool_name
ORDER BY total_executions DESC;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nlu_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nlu_user;