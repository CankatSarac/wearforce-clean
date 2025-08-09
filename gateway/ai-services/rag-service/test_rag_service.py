"""Test script for RAG service functionality."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from shared.models import Document, VectorSearchRequest, RAGRequest
from document_processor import DocumentProcessor, DataFormat
from embeddings import EmbeddingEngine
from search_engine import HybridSearchEngine
from citation_generator import CitationGenerator, CitationFormat, CitationStyle


async def test_document_processing():
    """Test document processing with CRM/ERP data."""
    print("=== Testing Document Processing ===")
    
    processor = DocumentProcessor(chunk_size=256, chunk_overlap=50)
    
    # Test CRM contact data
    crm_contact_data = {
        "id": "contact_001",
        "name": "John Smith",
        "email": "john.smith@example.com", 
        "company": "Acme Corp",
        "phone": "+1-555-0123",
        "title": "Senior Manager",
        "notes": "Key decision maker for IT purchases"
    }
    
    crm_document = Document(
        content=json.dumps(crm_contact_data),
        source="crm://contacts",
        metadata={"format": "crm_contact", "table_name": "contacts"}
    )
    
    processed = await processor.process_document(crm_document)
    print(f"CRM Document processed:")
    print(f"  Original length: {processed.processing_metadata['original_length']}")
    print(f"  Processed length: {processed.processing_metadata['processed_length']}")
    print(f"  Chunks: {len(processed.chunks)}")
    print(f"  Data format: {processed.data_format.value}")
    print(f"  Content preview: {processed.chunks[0].content[:100]}...")
    
    # Test ERP product data
    erp_product_data = {
        "id": "prod_001",
        "name": "Wireless Headphones",
        "sku": "WH-1000XM4",
        "price": 299.99,
        "category": "Electronics",
        "description": "Premium noise-canceling wireless headphones",
        "stock": 50
    }
    
    erp_document = Document(
        content=json.dumps(erp_product_data),
        source="erp://products", 
        metadata={"format": "erp_product", "table_name": "products"}
    )
    
    processed_erp = await processor.process_document(erp_document)
    print(f"\nERP Document processed:")
    print(f"  Data format: {processed_erp.data_format.value}")
    print(f"  Content preview: {processed_erp.chunks[0].content[:100]}...")


async def test_embeddings():
    """Test embedding generation."""
    print("\n=== Testing Embeddings ===")
    
    embedding_engine = EmbeddingEngine(
        model_name="BAAI/bge-small-en-v1.5",
        enable_caching=True,
        batch_size=4
    )
    
    try:
        await embedding_engine.initialize()
        
        # Test single encoding
        test_text = "This is a test document about CRM and customer management."
        embedding = await embedding_engine.encode(test_text)
        print(f"Single encoding:")
        print(f"  Text: {test_text}")
        print(f"  Embedding dimension: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}")
        
        # Test batch encoding
        batch_texts = [
            "Customer relationship management system",
            "Enterprise resource planning software",
            "Sales pipeline and opportunity tracking",
            "Inventory management and stock control"
        ]
        
        batch_embeddings = await embedding_engine.encode_batch(batch_texts)
        print(f"\nBatch encoding:")
        print(f"  Batch size: {len(batch_texts)}")
        print(f"  Embeddings generated: {len(batch_embeddings)}")
        
        # Test query vs document encoding
        query_embedding = await embedding_engine.encode_query("Find CRM contacts")
        doc_embeddings = await embedding_engine.encode_documents(batch_texts[:2])
        
        print(f"\nSpecialized encoding:")
        print(f"  Query embedding dim: {len(query_embedding)}")
        print(f"  Document embeddings: {len(doc_embeddings)}")
        
        # Get stats
        stats = embedding_engine.get_stats()
        print(f"\nEmbedding engine stats:")
        print(f"  Total encodings: {stats['encoding_count']}")
        print(f"  Cache hit rate: {stats.get('cache', {}).get('hit_rate', 'N/A')}")
        
    except Exception as e:
        print(f"Embedding test failed: {e}")
        print("Note: This test requires the actual model to be available")


async def test_citation_generator():
    """Test citation generation."""
    print("\n=== Testing Citation Generator ===")
    
    from shared.models import SearchResult
    
    citation_gen = CitationGenerator(
        default_format=CitationFormat.APA,
        default_style=CitationStyle.NUMBERED
    )
    
    # Mock search results
    search_results = [
        SearchResult(
            id="doc_1",
            content="Customer relationship management (CRM) is a technology for managing all your company's relationships and interactions with customers and potential customers.",
            score=0.92,
            metadata={
                "source": "Business Guide",
                "author": "Smith, J.",
                "publication_date": "2023",
                "title": "Modern CRM Systems"
            },
            source="business-guide.com"
        ),
        SearchResult(
            id="doc_2", 
            content="Enterprise Resource Planning (ERP) integrates main business processes, often in real-time and mediated by software and technology.",
            score=0.87,
            metadata={
                "source": "ERP Handbook",
                "author": "Johnson, A.",
                "publication_date": "2024",
                "title": "ERP Integration Strategies"
            },
            source="erp-handbook.org"
        )
    ]
    
    # Generate citations
    question = "What is the difference between CRM and ERP systems?"
    citations = await citation_gen.generate_citations(
        search_results,
        question,
        format_type=CitationFormat.APA,
        style=CitationStyle.NUMBERED
    )
    
    print(f"Generated {len(citations)} citations:")
    for citation in citations:
        print(f"  [{citation.index}] {citation.formatted_citation}")
        print(f"      Relevance: {citation.relevance_score:.3f}")
        print(f"      Snippet: {citation.content_snippet[:80]}...")
    
    # Generate bibliography
    bibliography = await citation_gen.generate_bibliography(citations, CitationFormat.APA)
    print(f"\nBibliography:")
    print(bibliography)
    
    # Get stats
    stats = citation_gen.get_citation_stats()
    print(f"\nCitation stats: {stats}")


async def create_sample_documents():
    """Create sample documents for testing."""
    documents = []
    
    # CRM samples
    crm_contacts = [
        {
            "name": "Alice Johnson",
            "email": "alice@techcorp.com",
            "company": "TechCorp Solutions",
            "phone": "+1-555-0001",
            "title": "CTO",
            "notes": "Interested in AI integration solutions"
        },
        {
            "name": "Bob Williams", 
            "email": "bob@retailco.com",
            "company": "RetailCo",
            "phone": "+1-555-0002",
            "title": "Operations Manager",
            "notes": "Looking for inventory management system"
        }
    ]
    
    for i, contact in enumerate(crm_contacts):
        doc = Document(
            id=f"crm_contact_{i+1}",
            content=json.dumps(contact),
            source="crm://contacts",
            metadata={"format": "crm_contact", "record_type": "contact"}
        )
        documents.append(doc)
    
    # ERP samples
    erp_products = [
        {
            "name": "Laptop Computer",
            "sku": "LPT-001",
            "price": 1299.99,
            "category": "Electronics",
            "description": "High-performance business laptop with 16GB RAM",
            "stock": 25
        },
        {
            "name": "Office Chair",
            "sku": "CHR-001", 
            "price": 399.99,
            "category": "Furniture",
            "description": "Ergonomic office chair with lumbar support",
            "stock": 15
        }
    ]
    
    for i, product in enumerate(erp_products):
        doc = Document(
            id=f"erp_product_{i+1}",
            content=json.dumps(product),
            source="erp://products",
            metadata={"format": "erp_product", "record_type": "product"}
        )
        documents.append(doc)
    
    # Regular text documents
    text_docs = [
        {
            "content": "Customer Relationship Management (CRM) systems help businesses manage and analyze customer interactions and data throughout the customer lifecycle.",
            "source": "CRM Guide",
            "title": "Introduction to CRM"
        },
        {
            "content": "Enterprise Resource Planning (ERP) software integrates core business processes such as finance, HR, manufacturing, supply chain, services, and procurement.",
            "source": "ERP Overview", 
            "title": "ERP System Benefits"
        }
    ]
    
    for i, text_doc in enumerate(text_docs):
        doc = Document(
            id=f"text_doc_{i+1}",
            content=text_doc["content"],
            source=text_doc["source"],
            metadata={"title": text_doc["title"], "format": "text"}
        )
        documents.append(doc)
    
    return documents


async def test_integration():
    """Test full integration of components."""
    print("\n=== Testing Full Integration ===")
    
    try:
        # Initialize components
        embedding_engine = EmbeddingEngine("BAAI/bge-small-en-v1.5")
        await embedding_engine.initialize()
        
        processor = DocumentProcessor()
        citation_gen = CitationGenerator()
        
        # Create sample documents
        documents = await create_sample_documents()
        print(f"Created {len(documents)} sample documents")
        
        # Process documents
        processed_docs = []
        for doc in documents:
            processed = await processor.process_document(doc)
            processed_docs.append(processed)
        
        print(f"Processed {len(processed_docs)} documents")
        
        # Generate embeddings for all chunks
        all_chunks = []
        for processed_doc in processed_docs:
            all_chunks.extend(processed_doc.chunks)
        
        chunk_texts = [chunk.content for chunk in all_chunks]
        embeddings = await embedding_engine.encode_documents(chunk_texts)
        
        print(f"Generated embeddings for {len(all_chunks)} chunks")
        
        # Mock search results (in real implementation, these would come from vector DB)
        from shared.models import SearchResult
        
        mock_results = []
        for i, (chunk, embedding) in enumerate(zip(all_chunks[:3], embeddings[:3])):
            result = SearchResult(
                id=chunk.id,
                content=chunk.content,
                score=0.9 - (i * 0.1),
                metadata=chunk.metadata,
                source=f"doc_{chunk.document_id}"
            )
            mock_results.append(result)
        
        # Generate citations
        citations = await citation_gen.generate_citations(
            mock_results,
            "What products are available in the system?",
            CitationFormat.SIMPLE
        )
        
        print(f"Generated {len(citations)} citations for integration test")
        for citation in citations:
            print(f"  {citation.formatted_citation}")
        
        print("✓ Integration test completed successfully")
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    print("Starting RAG Service Tests")
    print("=" * 50)
    
    await test_document_processing()
    await test_embeddings()
    await test_citation_generator() 
    await test_integration()
    
    print("\n" + "=" * 50)
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())