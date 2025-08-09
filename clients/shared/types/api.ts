// Base API Types
export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  errors?: APIError[];
  metadata?: APIMetadata;
}

export interface APIError {
  code: string;
  message: string;
  field?: string;
  details?: Record<string, any>;
}

export interface APIMetadata {
  page?: number;
  limit?: number;
  total?: number;
  totalPages?: number;
  requestId: string;
  timestamp: string;
  version?: string;
}

export interface PaginationParams {
  page?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface SearchParams extends PaginationParams {
  q?: string;
  filters?: Record<string, any>;
  include?: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrevious: boolean;
  };
}

// Authentication Types
export interface LoginRequest {
  email: string;
  password: string;
  rememberMe?: boolean;
  deviceInfo?: DeviceInfo;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
  user: User;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface DeviceInfo {
  platform: 'web' | 'ios' | 'android' | 'watchos' | 'wear-os';
  deviceId: string;
  appVersion: string;
  osVersion?: string;
  deviceName?: string;
}

// User Types
export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  avatar?: string;
  role: UserRole;
  permissions: Permission[];
  preferences: UserPreferences;
  isActive: boolean;
  emailVerified: boolean;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface UserRole {
  id: string;
  name: string;
  displayName: string;
  level: number;
  permissions: string[];
}

export interface Permission {
  id: string;
  resource: string;
  actions: string[];
  conditions?: Record<string, any>;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  language: string;
  timezone: string;
  notifications: NotificationSettings;
  dashboard: DashboardPreferences;
}

export interface NotificationSettings {
  email: boolean;
  push: boolean;
  sms: boolean;
  inApp: boolean;
  categories: {
    orders: boolean;
    customers: boolean;
    inventory: boolean;
    system: boolean;
    marketing: boolean;
  };
  quietHours?: {
    enabled: boolean;
    start: string;
    end: string;
  };
}

export interface DashboardPreferences {
  defaultTimeRange: string;
  widgets: DashboardWidget[];
  layout: 'grid' | 'list';
}

export interface DashboardWidget {
  id: string;
  type: string;
  position: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  config: Record<string, any>;
  isVisible: boolean;
}

// Chat Types
export interface ChatMessage {
  id: string;
  content: string;
  isFromUser: boolean;
  timestamp: string;
  type: 'text' | 'voice' | 'system' | 'error';
  metadata?: {
    audioUrl?: string;
    duration?: number;
    transcription?: string;
    confidence?: number;
    entities?: EntityExtraction[];
    actions?: MessageAction[];
  };
}

export interface EntityExtraction {
  entity: string;
  value: string;
  confidence: number;
  startIndex: number;
  endIndex: number;
}

export interface MessageAction {
  id: string;
  type: 'navigation' | 'query' | 'action';
  label: string;
  payload?: Record<string, any>;
}

export interface ChatRequest {
  content: string;
  type: 'text' | 'voice';
  timestamp: string;
  metadata?: {
    audioData?: string;
    duration?: number;
    language?: string;
    context?: ChatContext;
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
    actions?: MessageAction[];
    confidence?: number;
  };
}

export interface ChatContext {
  currentPage?: string;
  selectedItems?: string[];
  filters?: Record<string, any>;
  userIntent?: string;
}

// CRM Types
export interface Customer {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone?: string;
  company?: string;
  position?: string;
  website?: string;
  address?: Address;
  tags: string[];
  status: CustomerStatus;
  source: string;
  assignedTo?: string;
  totalValue: number;
  lastContactDate?: string;
  nextFollowUpDate?: string;
  customFields: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

export interface Lead {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone?: string;
  company?: string;
  position?: string;
  source: string;
  status: LeadStatus;
  score: number;
  value: number;
  probability: number;
  expectedCloseDate?: string;
  assignedTo?: string;
  tags: string[];
  notes?: string;
  customFields: Record<string, any>;
  activities: Activity[];
  createdAt: string;
  updatedAt: string;
}

export interface Opportunity {
  id: string;
  name: string;
  customerId: string;
  customer: Customer;
  value: number;
  stage: OpportunityStage;
  probability: number;
  expectedCloseDate?: string;
  actualCloseDate?: string;
  source: string;
  assignedTo?: string;
  products: OpportunityProduct[];
  notes?: string;
  tags: string[];
  customFields: Record<string, any>;
  activities: Activity[];
  createdAt: string;
  updatedAt: string;
}

export interface OpportunityProduct {
  productId: string;
  name: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  discount?: number;
}

export interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  description?: string;
  relatedTo: {
    type: 'customer' | 'lead' | 'opportunity' | 'order';
    id: string;
    name: string;
  };
  assignedTo?: string;
  completedBy?: string;
  dueDate?: string;
  completedAt?: string;
  priority: Priority;
  status: ActivityStatus;
  tags: string[];
  attachments: Attachment[];
  createdAt: string;
  updatedAt: string;
}

export interface Attachment {
  id: string;
  name: string;
  url: string;
  size: number;
  mimeType: string;
  uploadedBy: string;
  uploadedAt: string;
}

// ERP Types
export interface Order {
  id: string;
  orderNumber: string;
  customerId: string;
  customer: Customer;
  status: OrderStatus;
  type: OrderType;
  priority: Priority;
  items: OrderItem[];
  subtotal: number;
  tax: number;
  shipping: number;
  discount: number;
  total: number;
  currency: string;
  paymentStatus: PaymentStatus;
  paymentMethod?: string;
  shippingAddress?: Address;
  billingAddress?: Address;
  trackingNumber?: string;
  estimatedDeliveryDate?: string;
  actualDeliveryDate?: string;
  notes?: string;
  tags: string[];
  customFields: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  shippedAt?: string;
  deliveredAt?: string;
}

export interface OrderItem {
  id: string;
  productId: string;
  product: Product;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  discount?: number;
  tax?: number;
  notes?: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description?: string;
  category?: ProductCategory;
  brand?: string;
  price: number;
  cost?: number;
  currency: string;
  isActive: boolean;
  isDigital: boolean;
  weight?: number;
  dimensions?: Dimensions;
  images: string[];
  tags: string[];
  attributes: ProductAttribute[];
  variants: ProductVariant[];
  inventory: ProductInventory;
  customFields: Record<string, any>;
  seoTitle?: string;
  seoDescription?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProductCategory {
  id: string;
  name: string;
  slug: string;
  parentId?: string;
  description?: string;
  image?: string;
  isActive: boolean;
}

export interface ProductAttribute {
  name: string;
  value: string;
  type: 'text' | 'number' | 'boolean' | 'date' | 'color' | 'file';
}

export interface ProductVariant {
  id: string;
  sku: string;
  attributes: Record<string, string>;
  price?: number;
  cost?: number;
  inventory: ProductInventory;
}

export interface ProductInventory {
  quantity: number;
  reserved: number;
  available: number;
  lowStockThreshold: number;
  trackQuantity: boolean;
  locations: InventoryLocation[];
}

export interface InventoryLocation {
  locationId: string;
  locationName: string;
  quantity: number;
  reserved: number;
  available: number;
}

export interface Supplier {
  id: string;
  name: string;
  contactPerson?: string;
  email: string;
  phone?: string;
  website?: string;
  address?: Address;
  paymentTerms?: string;
  currency: string;
  taxId?: string;
  rating?: number;
  isActive: boolean;
  products: string[];
  notes?: string;
  tags: string[];
  customFields: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

// Common Types
export interface Address {
  street1: string;
  street2?: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

export interface Dimensions {
  length: number;
  width: number;
  height: number;
  unit: 'cm' | 'in' | 'm' | 'ft';
}

// Enums
export enum CustomerStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PROSPECT = 'prospect',
  LEAD = 'lead',
  CUSTOMER = 'customer',
  CHURNED = 'churned'
}

export enum LeadStatus {
  NEW = 'new',
  CONTACTED = 'contacted',
  QUALIFIED = 'qualified',
  PROPOSAL = 'proposal',
  NEGOTIATION = 'negotiation',
  WON = 'won',
  LOST = 'lost',
  UNQUALIFIED = 'unqualified'
}

export enum OpportunityStage {
  DISCOVERY = 'discovery',
  QUALIFICATION = 'qualification',
  PROPOSAL = 'proposal',
  NEGOTIATION = 'negotiation',
  CLOSED_WON = 'closed_won',
  CLOSED_LOST = 'closed_lost'
}

export enum ActivityType {
  CALL = 'call',
  EMAIL = 'email',
  MEETING = 'meeting',
  TASK = 'task',
  NOTE = 'note',
  FOLLOW_UP = 'follow_up'
}

export enum ActivityStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled',
  OVERDUE = 'overdue'
}

export enum OrderStatus {
  DRAFT = 'draft',
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  PROCESSING = 'processing',
  SHIPPED = 'shipped',
  DELIVERED = 'delivered',
  CANCELLED = 'cancelled',
  RETURNED = 'returned'
}

export enum OrderType {
  SALE = 'sale',
  RETURN = 'return',
  EXCHANGE = 'exchange',
  REFUND = 'refund'
}

export enum PaymentStatus {
  PENDING = 'pending',
  AUTHORIZED = 'authorized',
  CAPTURED = 'captured',
  PARTIALLY_PAID = 'partially_paid',
  PAID = 'paid',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  REFUNDED = 'refunded'
}

export enum Priority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  URGENT = 'urgent'
}

// WebSocket Types
export interface WebSocketMessage {
  id: string;
  type: WebSocketMessageType;
  payload: any;
  timestamp: string;
  userId?: string;
  sessionId?: string;
}

export enum WebSocketMessageType {
  CHAT = 'chat',
  NOTIFICATION = 'notification',
  UPDATE = 'update',
  HEARTBEAT = 'heartbeat',
  ERROR = 'error',
  SYSTEM = 'system',
  TYPING = 'typing',
  PRESENCE = 'presence'
}

// Notification Types
export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  data?: Record<string, any>;
  read: boolean;
  userId: string;
  createdAt: string;
  expiresAt?: string;
}

export enum NotificationType {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
  ORDER = 'order',
  CUSTOMER = 'customer',
  INVENTORY = 'inventory',
  SYSTEM = 'system'
}

// Analytics Types
export interface AnalyticsData {
  metrics: Metric[];
  timeRange: {
    start: string;
    end: string;
  };
  granularity: 'hour' | 'day' | 'week' | 'month' | 'quarter' | 'year';
}

export interface Metric {
  key: string;
  name: string;
  value: number;
  previousValue?: number;
  change?: number;
  changePercent?: number;
  trend: 'up' | 'down' | 'flat';
  unit?: string;
  format?: 'number' | 'currency' | 'percent';
}

export interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
}

export interface ChartDataset {
  label: string;
  data: number[];
  backgroundColor?: string;
  borderColor?: string;
  borderWidth?: number;
  fill?: boolean;
}

// Report Types
export interface Report {
  id: string;
  name: string;
  description?: string;
  type: ReportType;
  config: ReportConfig;
  schedule?: ReportSchedule;
  recipients: string[];
  isActive: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string;
  nextRunAt?: string;
}

export enum ReportType {
  SALES = 'sales',
  CUSTOMERS = 'customers',
  INVENTORY = 'inventory',
  FINANCIAL = 'financial',
  PERFORMANCE = 'performance',
  CUSTOM = 'custom'
}

export interface ReportConfig {
  filters: Record<string, any>;
  groupBy?: string[];
  metrics: string[];
  timeRange: {
    type: 'fixed' | 'relative';
    start?: string;
    end?: string;
    relative?: string;
  };
  format: 'table' | 'chart' | 'pivot';
  chartType?: 'line' | 'bar' | 'pie' | 'area';
}

export interface ReportSchedule {
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  dayOfWeek?: number;
  dayOfMonth?: number;
  time: string;
  timezone: string;
}