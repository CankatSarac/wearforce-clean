-- RAG Service Database Initialization Script
-- This script sets up the database for the RAG service

-- Enable vector extension (if using pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for RAG service
CREATE SCHEMA IF NOT EXISTS rag;

-- Set search path
SET search_path TO rag, public;

-- Document registry table for tracking indexed documents
CREATE TABLE IF NOT EXISTS document_registry (
    id VARCHAR(255) PRIMARY KEY,
    source VARCHAR(500),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    chunk_count INTEGER DEFAULT 0,
    data_format VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    processing_time REAL,
    version INTEGER DEFAULT 1
);

-- Indexing jobs table for tracking batch processing
CREATE TABLE IF NOT EXISTS indexing_jobs (
    job_id VARCHAR(255) PRIMARY KEY,
    document_ids TEXT[],
    job_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    progress INTEGER DEFAULT 0,
    total_documents INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    error_summary TEXT[]
);

-- Data sources configuration table
CREATE TABLE IF NOT EXISTS data_sources (
    name VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    connection_params JSONB DEFAULT '{}',
    sync_frequency VARCHAR(50),
    incremental_field VARCHAR(255),
    batch_size INTEGER DEFAULT 1000,
    enabled BOOLEAN DEFAULT true,
    last_sync TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document chunks table (optional - if storing chunks in PostgreSQL)
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384), -- Adjust dimension based on your embedding model
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES document_registry(id) ON DELETE CASCADE
);

-- Batch processing statistics
CREATE TABLE IF NOT EXISTS batch_stats (
    id SERIAL PRIMARY KEY,
    stat_name VARCHAR(255) NOT NULL,
    stat_value NUMERIC,
    stat_metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_document_registry_status ON document_registry(status);
CREATE INDEX IF NOT EXISTS idx_document_registry_created_at ON document_registry(created_at);
CREATE INDEX IF NOT EXISTS idx_document_registry_source ON document_registry(source);
CREATE INDEX IF NOT EXISTS idx_document_registry_data_format ON document_registry(data_format);

CREATE INDEX IF NOT EXISTS idx_indexing_jobs_status ON indexing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_created_at ON indexing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_job_type ON indexing_jobs(job_type);

CREATE INDEX IF NOT EXISTS idx_data_sources_type ON data_sources(type);
CREATE INDEX IF NOT EXISTS idx_data_sources_enabled ON data_sources(enabled);
CREATE INDEX IF NOT EXISTS idx_data_sources_last_sync ON data_sources(last_sync);

-- Indexes for document chunks (if using PostgreSQL for vector storage)
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(chunk_index);

-- Vector similarity index (if using pgvector)
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_batch_stats_stat_name ON batch_stats(stat_name);
CREATE INDEX IF NOT EXISTS idx_batch_stats_recorded_at ON batch_stats(recorded_at);

-- Create triggers for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_document_registry_updated_at 
    BEFORE UPDATE ON document_registry 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_sources_updated_at 
    BEFORE UPDATE ON data_sources 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data sources (optional)
INSERT INTO data_sources (name, type, connection_params, sync_frequency, incremental_field, enabled) VALUES
    ('crm_contacts', 'crm', '{"table_name": "contacts", "connection_string": "postgresql://user:pass@crm-db:5432/crm"}', 'daily', 'updated_at', true),
    ('erp_products', 'erp', '{"table_name": "products", "connection_string": "postgresql://user:pass@erp-db:5432/erp"}', 'daily', 'updated_at', true),
    ('erp_orders', 'erp', '{"table_name": "orders", "connection_string": "postgresql://user:pass@erp-db:5432/erp"}', 'hourly', 'updated_at', true)
ON CONFLICT (name) DO NOTHING;

-- Grant permissions (adjust as needed)
-- GRANT USAGE ON SCHEMA rag TO rag_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO rag_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rag TO rag_user;

-- Create views for monitoring and analytics
CREATE OR REPLACE VIEW document_processing_stats AS
SELECT 
    data_format,
    status,
    COUNT(*) as document_count,
    AVG(processing_time) as avg_processing_time,
    AVG(chunk_count) as avg_chunk_count,
    MAX(updated_at) as last_updated
FROM document_registry 
GROUP BY data_format, status
ORDER BY data_format, status;

CREATE OR REPLACE VIEW indexing_job_summary AS
SELECT 
    job_type,
    status,
    COUNT(*) as job_count,
    SUM(total_documents) as total_documents,
    SUM(success_count) as total_success,
    SUM(failure_count) as total_failures,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
FROM indexing_jobs 
WHERE started_at IS NOT NULL
GROUP BY job_type, status
ORDER BY job_type, status;

-- Add comments for documentation
COMMENT ON TABLE document_registry IS 'Tracks all documents that have been indexed by the RAG service';
COMMENT ON TABLE indexing_jobs IS 'Tracks batch indexing jobs and their progress';
COMMENT ON TABLE data_sources IS 'Configuration for external data sources (CRM, ERP, etc.)';
COMMENT ON TABLE document_chunks IS 'Stores document chunks with embeddings (optional, can use Qdrant instead)';
COMMENT ON TABLE batch_stats IS 'Stores various statistics about batch processing operations';

COMMENT ON COLUMN document_registry.data_format IS 'The format/type of the document (crm_contact, erp_product, etc.)';
COMMENT ON COLUMN document_registry.metadata IS 'Additional metadata about the document as JSON';
COMMENT ON COLUMN indexing_jobs.document_ids IS 'Array of document IDs included in this job';
COMMENT ON COLUMN data_sources.connection_params IS 'Connection parameters as JSON (connection strings, API keys, etc.)';

-- Log the completion
INSERT INTO batch_stats (stat_name, stat_value, stat_metadata) VALUES 
    ('database_init_completed', 1, '{"version": "1.0", "timestamp": "' || NOW() || '"}');

COMMIT;