# WearForce-Clean Web Dashboard

A comprehensive React web dashboard for WearForce-Clean's conversational AI business management platform. Built with modern technologies for scalability, performance, and excellent user experience.

## 🚀 Features

### Core Functionality
- **Dashboard Analytics** - Real-time business metrics and visualizations using Recharts
- **CRM Management** - Customer relationship management with advanced data tables
- **ERP Operations** - Order management, inventory tracking, and supplier relationships  
- **AI Chat Interface** - Conversational AI assistant for business queries and operations
- **Real-time Updates** - WebSocket integration for live data synchronization
- **Authentication** - Secure Keycloak integration with role-based access control

### Technical Features
- **Modern React** - Built with React 18, TypeScript, and latest best practices
- **Advanced UI** - ShadCN/ui components with Tailwind CSS for responsive design
- **State Management** - Zustand for efficient client-state management
- **Data Fetching** - TanStack Query for server state management and caching
- **Real-time Data** - Socket.IO integration for live updates
- **Testing** - Comprehensive test suite with Vitest and Testing Library
- **Type Safety** - Full TypeScript coverage for enhanced developer experience

## 🛠️ Tech Stack

### Frontend
- **React 18** - Modern React with hooks and concurrent features
- **TypeScript** - Full type safety and enhanced developer experience
- **Vite** - Lightning fast build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework for rapid styling

### UI Components
- **ShadCN/ui** - High-quality, accessible component library
- **Radix UI** - Primitive components for complex UI patterns
- **Lucide React** - Beautiful, customizable icons
- **Recharts** - Composable charting library for data visualization

### Data Management
- **TanStack Query** - Powerful data synchronization for React
- **TanStack Table** - Feature-rich data grid with sorting, filtering, and pagination
- **Zustand** - Lightweight state management solution
- **Immer** - Immutable state updates made simple

### Authentication & Security
- **Keycloak Integration** - Enterprise-grade authentication and authorization
- **JWT Tokens** - Secure token-based authentication with refresh handling
- **Role-based Access** - Fine-grained permissions and role management

### Development Tools
- **Vitest** - Fast unit testing framework
- **Testing Library** - Simple and complete testing utilities
- **ESLint** - Code quality and consistency
- **Prettier** - Code formatting
- **Storybook** - Component development and documentation

## 📦 Installation

### Prerequisites
- Node.js 18+ 
- npm or yarn package manager
- Access to WearForce-Clean API endpoints
- Keycloak authentication server

### Setup Instructions

1. **Clone and install dependencies**
   ```bash
   cd /mnt/c/Users/Cankat/Documents/Startup/clients/web
   npm install
   ```

2. **Environment Configuration**
   Create `.env.local` with your configuration:
   ```env
   VITE_API_BASE_URL=http://localhost:3000/api
   VITE_WEBSOCKET_URL=ws://localhost:3001
   VITE_KEYCLOAK_URL=http://localhost:8080/auth
   VITE_KEYCLOAK_REALM=wearforce-clean
   VITE_KEYCLOAK_CLIENT_ID=wearforce-clean-web
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

4. **Run tests**
   ```bash
   npm run test
   npm run test:coverage
   ```

## 🏗️ Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── ui/              # Base UI components (ShadCN/ui)
│   ├── dashboard/       # Dashboard-specific components
│   ├── tables/          # Data table implementations
│   ├── chat/            # AI chat interface
│   ├── auth/            # Authentication components
│   ├── layouts/         # Page layout components
│   └── theme/           # Theme provider and utilities
├── pages/               # Route components
│   ├── auth/            # Authentication pages
│   ├── dashboard/       # Dashboard page
│   ├── crm/             # CRM pages
│   ├── erp/             # ERP pages
│   ├── chat/            # Chat interface page
│   └── ...
├── hooks/               # Custom React hooks
├── services/            # API and external service integrations
├── store/               # Zustand state management
├── types/               # TypeScript type definitions
├── utils/               # Utility functions
├── lib/                 # Library configurations
└── test/                # Test utilities and setup
```

## 🔧 Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run test` - Run unit tests
- `npm run test:ui` - Run tests with UI
- `npm run test:coverage` - Generate test coverage report
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run format` - Format code with Prettier
- `npm run storybook` - Start Storybook dev server

## 📊 Key Components

### Dashboard
- Real-time metrics cards with trend indicators
- Interactive sales charts and data visualizations
- Recent activity feed with live updates
- Top products and customer insights panels
- Quick action shortcuts for common tasks

### Data Tables
- **Customers Table** - Full customer management with search, filtering, and actions
- **Orders Table** - Order tracking with status updates and fulfillment management
- Advanced features: sorting, pagination, bulk operations, and export functionality

### Chat Interface
- Conversational AI assistant with context-aware responses
- Real-time message handling with typing indicators
- File upload support and suggested quick actions
- Integration with business data for intelligent responses

### Authentication
- Secure login/logout with Keycloak integration
- Role-based access control and permission management
- Session management with automatic token refresh
- Protected routes with redirect handling

## 🧪 Testing

The project includes comprehensive testing with:

- **Unit Tests** - Component and utility function testing
- **Integration Tests** - Multi-component interaction testing
- **Coverage Reports** - Detailed code coverage analysis
- **Testing Utilities** - Custom render functions with providers

Run tests:
```bash
npm run test              # Run all tests
npm run test:watch        # Watch mode
npm run test:coverage     # With coverage report
npm run test:ui           # Visual test runner
```

## 🎨 Styling and Theme

- **Design System** - Consistent design tokens and component patterns
- **Dark/Light Mode** - Full theme support with system preference detection
- **Responsive Design** - Mobile-first responsive layouts
- **Accessibility** - WCAG compliant components with proper ARIA attributes

## 🔗 Integration Points

### Backend APIs
- RESTful API endpoints for CRUD operations
- WebSocket connections for real-time data
- File upload and download capabilities
- Authentication and authorization endpoints

### External Services
- Keycloak for identity and access management
- Optional third-party integrations (email, notifications, etc.)

## 🚦 Development Workflow

1. **Feature Development** - Create feature branches from main
2. **Code Quality** - ESLint and Prettier enforce coding standards
3. **Testing** - Write tests for new components and features
4. **Type Safety** - Maintain full TypeScript coverage
5. **Documentation** - Update documentation for significant changes

## 📈 Performance Considerations

- **Code Splitting** - Route-based code splitting for optimal loading
- **Bundle Optimization** - Tree shaking and dependency optimization
- **Caching Strategy** - Intelligent API response caching with TanStack Query
- **Image Optimization** - Lazy loading and responsive images
- **WebSocket Efficiency** - Optimized real-time data handling

## 🔒 Security Features

- **Token Management** - Secure JWT handling with refresh mechanisms
- **CSRF Protection** - Cross-site request forgery protection
- **Input Validation** - Client-side validation with server-side verification
- **XSS Prevention** - Proper data sanitization and content security policies

## 🌍 Browser Support

- Chrome (latest 2 versions)
- Firefox (latest 2 versions) 
- Safari (latest 2 versions)
- Edge (latest 2 versions)

## 📱 Mobile Support

- Responsive design adapts to all screen sizes
- Touch-friendly interface elements
- Mobile-optimized navigation and interactions

## 🤝 Contributing

1. Follow the established code style and patterns
2. Write tests for new functionality
3. Update documentation for significant changes
4. Ensure TypeScript compliance
5. Test across supported browsers

## 📄 License

Copyright © 2024 WearForce-Clean. All rights reserved.

## 📞 Support

For technical support or questions:
- Internal Documentation: [Link to internal docs]
- Development Team: [Contact information]
- Issue Tracking: [Internal issue tracker]

---

Built with ❤️ by the WearForce-Clean development team