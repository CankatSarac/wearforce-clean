"""Document processing with chunking and preprocessing."""

import re
import json
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from shared.models import Document, DocumentChunk

logger = structlog.get_logger(__name__)

class DataFormat(str, Enum):
    """Data format types for processing."""
    TEXT = "text"
    JSON = "json"
    DATABASE_RECORD = "database_record"
    CRM_CONTACT = "crm_contact"
    CRM_OPPORTUNITY = "crm_opportunity"
    ERP_PRODUCT = "erp_product"
    ERP_ORDER = "erp_order"
    ERP_INVOICE = "erp_invoice"

@dataclass
class ProcessedDocument:
    """Processed document with chunks and metadata."""
    document: Document
    chunks: List[DocumentChunk]
    processing_metadata: Dict[str, Any]
    data_format: DataFormat = DataFormat.TEXT

class DocumentProcessor:
    """Document chunking and preprocessing."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # CRM/ERP field mappings
        self.crm_field_mappings = {
            'name': ['name', 'first_name', 'last_name', 'full_name', 'contact_name'],
            'email': ['email', 'email_address', 'contact_email'],
            'phone': ['phone', 'phone_number', 'mobile', 'telephone'],
            'company': ['company', 'organization', 'company_name'],
            'title': ['title', 'job_title', 'position'],
            'address': ['address', 'street_address', 'location'],
            'notes': ['notes', 'description', 'comments']
        }
        
        self.erp_field_mappings = {
            'product_name': ['name', 'product_name', 'title'],
            'sku': ['sku', 'product_code', 'item_code'],
            'price': ['price', 'unit_price', 'cost'],
            'category': ['category', 'product_category', 'type'],
            'description': ['description', 'product_description', 'details'],
            'stock': ['stock', 'quantity', 'inventory']
        }
    
    async def process_document(self, document: Document) -> ProcessedDocument:
        """Process document into chunks with format-specific handling."""
        # Determine data format
        data_format = self._detect_data_format(document)
        
        # Format-specific processing
        if data_format in [DataFormat.CRM_CONTACT, DataFormat.CRM_OPPORTUNITY]:
            processed_content = self._process_crm_data(document.content, data_format)
        elif data_format in [DataFormat.ERP_PRODUCT, DataFormat.ERP_ORDER, DataFormat.ERP_INVOICE]:
            processed_content = self._process_erp_data(document.content, data_format)
        elif data_format == DataFormat.JSON:
            processed_content = self._process_json_data(document.content)
        elif data_format == DataFormat.DATABASE_RECORD:
            processed_content = self._process_database_record(document.content)
        else:
            processed_content = document.content
        
        # Clean and preprocess text
        cleaned_content = self._clean_text(processed_content)
        
        # Create chunks
        chunks = self._create_chunks(document.id, cleaned_content)
        
        # Add metadata
        processing_metadata = {
            "original_length": len(document.content),
            "processed_length": len(processed_content),
            "cleaned_length": len(cleaned_content),
            "chunk_count": len(chunks),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "data_format": data_format.value,
        }
        
        return ProcessedDocument(
            document=document,
            chunks=chunks,
            processing_metadata=processing_metadata,
            data_format=data_format,
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        return text.strip()
    
    def _create_chunks(self, document_id: str, content: str) -> List[DocumentChunk]:
        """Create overlapping chunks from text."""
        chunks = []
        words = content.split()
        
        if len(words) <= self.chunk_size:
            # Single chunk
            chunks.append(DocumentChunk(
                document_id=document_id,
                content=content,
                chunk_index=0,
                metadata={"word_count": len(words)},
            ))
        else:
            # Multiple chunks with overlap
            for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                chunk_words = words[i:i + self.chunk_size]
                chunk_content = ' '.join(chunk_words)
                
                chunks.append(DocumentChunk(
                    document_id=document_id,
                    content=chunk_content,
                    chunk_index=len(chunks),
                    metadata={
                        "word_count": len(chunk_words),
                        "start_word_index": i,
                        "end_word_index": i + len(chunk_words),
                    },
                ))
                
                if i + self.chunk_size >= len(words):
                    break
        
        return chunks
    
    def _detect_data_format(self, document: Document) -> DataFormat:
        """Detect the format of the document data."""
        metadata = document.metadata or {}
        
        # Check metadata for format hints
        if 'format' in metadata:
            format_value = metadata['format'].lower()
            if format_value == 'crm_contact' or metadata.get('source_type') == 'crm':
                return DataFormat.CRM_CONTACT
            elif format_value == 'erp_product' or metadata.get('source_type') == 'erp':
                return DataFormat.ERP_PRODUCT
            elif format_value == 'database_record':
                return DataFormat.DATABASE_RECORD
            elif format_value == 'json':
                return DataFormat.JSON
        
        # Try to detect JSON format
        try:
            json.loads(document.content)
            return DataFormat.JSON
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Check source metadata
        source = document.source or ''
        if 'crm' in source.lower():
            return DataFormat.CRM_CONTACT
        elif 'erp' in source.lower():
            return DataFormat.ERP_PRODUCT
        
        return DataFormat.TEXT
    
    def _process_crm_data(self, content: str, data_format: DataFormat) -> str:
        """Process CRM data into readable text."""
        try:
            data = json.loads(content)
            
            if data_format == DataFormat.CRM_CONTACT:
                return self._process_crm_contact(data)
            elif data_format == DataFormat.CRM_OPPORTUNITY:
                return self._process_crm_opportunity(data)
            else:
                return self._process_generic_crm_data(data)
                
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse CRM data as JSON")
            return content
    
    def _process_crm_contact(self, data: Dict[str, Any]) -> str:
        """Process CRM contact data."""
        parts = []
        
        # Extract name
        name = self._extract_field(data, self.crm_field_mappings['name'])
        if name:
            parts.append(f"Contact: {name}")
        
        # Extract company
        company = self._extract_field(data, self.crm_field_mappings['company'])
        if company:
            parts.append(f"Company: {company}")
        
        # Extract title
        title = self._extract_field(data, self.crm_field_mappings['title'])
        if title:
            parts.append(f"Position: {title}")
        
        # Extract contact info
        email = self._extract_field(data, self.crm_field_mappings['email'])
        if email:
            parts.append(f"Email: {email}")
        
        phone = self._extract_field(data, self.crm_field_mappings['phone'])
        if phone:
            parts.append(f"Phone: {phone}")
        
        # Extract address
        address = self._extract_field(data, self.crm_field_mappings['address'])
        if address:
            parts.append(f"Address: {address}")
        
        # Extract notes/description
        notes = self._extract_field(data, self.crm_field_mappings['notes'])
        if notes:
            parts.append(f"Notes: {notes}")
        
        # Add any additional fields
        for key, value in data.items():
            if (key not in ['id', 'created_at', 'updated_at'] and 
                value and 
                not self._is_field_mapped(key)):
                parts.append(f"{key.replace('_', ' ').title()}: {value}")
        
        return '. '.join(parts) + '.'
    
    def _process_crm_opportunity(self, data: Dict[str, Any]) -> str:
        """Process CRM opportunity data."""
        parts = []
        
        # Opportunity name
        name = data.get('name') or data.get('opportunity_name')
        if name:
            parts.append(f"Opportunity: {name}")
        
        # Account/Company
        account = data.get('account_name') or data.get('company')
        if account:
            parts.append(f"Account: {account}")
        
        # Amount
        amount = data.get('amount') or data.get('value')
        if amount:
            parts.append(f"Value: {amount}")
        
        # Stage
        stage = data.get('stage') or data.get('sales_stage')
        if stage:
            parts.append(f"Stage: {stage}")
        
        # Close date
        close_date = data.get('close_date') or data.get('expected_close_date')
        if close_date:
            parts.append(f"Expected Close: {close_date}")
        
        # Description
        description = data.get('description') or data.get('notes')
        if description:
            parts.append(f"Description: {description}")
        
        return '. '.join(parts) + '.'
    
    def _process_erp_data(self, content: str, data_format: DataFormat) -> str:
        """Process ERP data into readable text."""
        try:
            data = json.loads(content)
            
            if data_format == DataFormat.ERP_PRODUCT:
                return self._process_erp_product(data)
            elif data_format == DataFormat.ERP_ORDER:
                return self._process_erp_order(data)
            elif data_format == DataFormat.ERP_INVOICE:
                return self._process_erp_invoice(data)
            else:
                return self._process_generic_erp_data(data)
                
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse ERP data as JSON")
            return content
    
    def _process_erp_product(self, data: Dict[str, Any]) -> str:
        """Process ERP product data."""
        parts = []
        
        # Product name
        name = self._extract_field(data, self.erp_field_mappings['product_name'])
        if name:
            parts.append(f"Product: {name}")
        
        # SKU
        sku = self._extract_field(data, self.erp_field_mappings['sku'])
        if sku:
            parts.append(f"SKU: {sku}")
        
        # Category
        category = self._extract_field(data, self.erp_field_mappings['category'])
        if category:
            parts.append(f"Category: {category}")
        
        # Price
        price = self._extract_field(data, self.erp_field_mappings['price'])
        if price:
            parts.append(f"Price: {price}")
        
        # Stock
        stock = self._extract_field(data, self.erp_field_mappings['stock'])
        if stock:
            parts.append(f"Stock: {stock}")
        
        # Description
        description = self._extract_field(data, self.erp_field_mappings['description'])
        if description:
            parts.append(f"Description: {description}")
        
        # Add other relevant fields
        for key, value in data.items():
            if (key not in ['id', 'created_at', 'updated_at'] and 
                value and 
                not self._is_field_mapped(key, 'erp')):
                parts.append(f"{key.replace('_', ' ').title()}: {value}")
        
        return '. '.join(parts) + '.'
    
    def _process_erp_order(self, data: Dict[str, Any]) -> str:
        """Process ERP order data."""
        parts = []
        
        # Order number
        order_num = data.get('order_number') or data.get('order_id')
        if order_num:
            parts.append(f"Order: {order_num}")
        
        # Customer
        customer = data.get('customer_name') or data.get('customer')
        if customer:
            parts.append(f"Customer: {customer}")
        
        # Status
        status = data.get('status') or data.get('order_status')
        if status:
            parts.append(f"Status: {status}")
        
        # Total
        total = data.get('total') or data.get('total_amount')
        if total:
            parts.append(f"Total: {total}")
        
        # Date
        order_date = data.get('order_date') or data.get('date')
        if order_date:
            parts.append(f"Date: {order_date}")
        
        return '. '.join(parts) + '.'
    
    def _process_erp_invoice(self, data: Dict[str, Any]) -> str:
        """Process ERP invoice data."""
        parts = []
        
        # Invoice number
        invoice_num = data.get('invoice_number') or data.get('invoice_id')
        if invoice_num:
            parts.append(f"Invoice: {invoice_num}")
        
        # Customer
        customer = data.get('customer_name') or data.get('bill_to')
        if customer:
            parts.append(f"Customer: {customer}")
        
        # Amount
        amount = data.get('total_amount') or data.get('amount')
        if amount:
            parts.append(f"Amount: {amount}")
        
        # Status
        status = data.get('status') or data.get('payment_status')
        if status:
            parts.append(f"Status: {status}")
        
        # Due date
        due_date = data.get('due_date')
        if due_date:
            parts.append(f"Due Date: {due_date}")
        
        return '. '.join(parts) + '.'
    
    def _process_json_data(self, content: str) -> str:
        """Process generic JSON data."""
        try:
            data = json.loads(content)
            return self._json_to_text(data)
        except (json.JSONDecodeError, ValueError):
            return content
    
    def _process_database_record(self, content: str) -> str:
        """Process database record data."""
        return self._process_json_data(content)
    
    def _process_generic_crm_data(self, data: Dict[str, Any]) -> str:
        """Process generic CRM data."""
        return self._json_to_text(data, 'CRM Record')
    
    def _process_generic_erp_data(self, data: Dict[str, Any]) -> str:
        """Process generic ERP data."""
        return self._json_to_text(data, 'ERP Record')
    
    def _json_to_text(self, data: Dict[str, Any], prefix: str = "Record") -> str:
        """Convert JSON data to readable text."""
        parts = [prefix + ":"]
        
        for key, value in data.items():
            if key in ['id', 'created_at', 'updated_at']:
                continue
            
            if value is not None:
                key_formatted = key.replace('_', ' ').title()
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)
                parts.append(f"{key_formatted}: {value_str}")
        
        return '. '.join(parts) + '.'
    
    def _extract_field(self, data: Dict[str, Any], field_names: List[str]) -> str:
        """Extract field value using multiple possible field names."""
        for field_name in field_names:
            if field_name in data and data[field_name]:
                return str(data[field_name])
        return ''
    
    def _is_field_mapped(self, field_name: str, system_type: str = 'crm') -> bool:
        """Check if a field is already mapped."""
        mappings = self.crm_field_mappings if system_type == 'crm' else self.erp_field_mappings
        
        for field_list in mappings.values():
            if field_name in field_list:
                return True
        return False