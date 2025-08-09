// Validation utilities that can be shared across platforms

// Security-focused validation constants
const MAX_STRING_LENGTH = 10000;
const MAX_EMAIL_LENGTH = 254;
const MAX_NAME_LENGTH = 100;
const MAX_PHONE_LENGTH = 20;
const MAX_URL_LENGTH = 2048;

// Dangerous patterns to detect potential XSS/injection attempts
const DANGEROUS_PATTERNS = [
  /<script[^>]*>.*?<\/script>/gi,
  /javascript:/gi,
  /vbscript:/gi,
  /data:text\/html/gi,
  /on\w+\s*=/gi,
  /<iframe[^>]*>.*?<\/iframe>/gi,
  /<embed[^>]*>/gi,
  /<object[^>]*>.*?<\/object>/gi,
];

// SQL injection patterns
const SQL_INJECTION_PATTERNS = [
  /(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bCREATE\b|\bALTER\b)/gi,
  /('|(\\')|(;)|(\\)|(\s|\\|%|\/\*|\*\/|%27|%22|%23|%2D|%2F))/gi,
];

// Input sanitization
export const sanitizeString = (input: string): string => {
  if (typeof input !== 'string') return '';
  
  // Trim and limit length
  input = input.trim().substring(0, MAX_STRING_LENGTH);
  
  // Remove null bytes and control characters
  input = input.replace(/[\0\x08\x09\x1a\n\r"'\\\%]/g, '');
  
  // Basic HTML entity encoding for dangerous characters
  input = input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
  
  return input;
};

// Enhanced security validation
export const containsDangerousContent = (input: string): boolean => {
  if (typeof input !== 'string') return false;
  
  return DANGEROUS_PATTERNS.some(pattern => pattern.test(input)) ||
         SQL_INJECTION_PATTERNS.some(pattern => pattern.test(input));
};

// Email validation with enhanced security
export const isValidEmail = (email: string): boolean => {
  if (!email || typeof email !== 'string' || email.length > MAX_EMAIL_LENGTH) {
    return false;
  }
  
  // Check for dangerous content
  if (containsDangerousContent(email)) {
    return false;
  }
  
  // Improved email regex that's more restrictive
  const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
  return emailRegex.test(email.trim().toLowerCase());
};

// Phone validation with enhanced security
export const isValidPhone = (phone: string): boolean => {
  if (!phone || typeof phone !== 'string' || phone.length > MAX_PHONE_LENGTH) {
    return false;
  }
  
  // Check for dangerous content
  if (containsDangerousContent(phone)) {
    return false;
  }
  
  const cleanPhone = phone.replace(/[\s\-\(\)\.]/g, '');
  const phoneRegex = /^\+?[1-9]\d{1,14}$/;
  return phoneRegex.test(cleanPhone);
};

// URL validation with enhanced security
export const isValidUrl = (url: string): boolean => {
  if (!url || typeof url !== 'string' || url.length > MAX_URL_LENGTH) {
    return false;
  }
  
  // Check for dangerous content
  if (containsDangerousContent(url)) {
    return false;
  }
  
  try {
    const urlObj = new URL(url);
    
    // Only allow http and https protocols
    if (!['http:', 'https:'].includes(urlObj.protocol)) {
      return false;
    }
    
    // Prevent localhost and private IP access in production
    if (process.env.NODE_ENV === 'production') {
      const hostname = urlObj.hostname.toLowerCase();
      
      // Block localhost
      if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
        return false;
      }
      
      // Block private IP ranges
      const privateIPRanges = [
        /^10\./,
        /^192\.168\./,
        /^172\.(1[6-9]|2\d|3[01])\./,
        /^169\.254\./,
        /^fc00:/,
        /^fe80:/,
      ];
      
      if (privateIPRanges.some(range => range.test(hostname))) {
        return false;
      }
    }
    
    return true;
  } catch {
    return false;
  }
};

// Password strength validation
export interface PasswordStrength {
  score: number; // 0-4
  feedback: string[];
  isValid: boolean;
}

export const validatePassword = (password: string): PasswordStrength => {
  const feedback: string[] = [];
  let score = 0;

  // Basic type and length checks
  if (!password || typeof password !== 'string') {
    return {
      score: 0,
      feedback: ['Password is required'],
      isValid: false,
    };
  }

  // Check for dangerous content
  if (containsDangerousContent(password)) {
    return {
      score: 0,
      feedback: ['Password contains invalid characters'],
      isValid: false,
    };
  }

  // Length requirements
  if (password.length < 8) {
    feedback.push('Password must be at least 8 characters long');
  } else {
    score += 1;
  }

  if (password.length > 128) {
    feedback.push('Password must not exceed 128 characters');
    return {
      score: 0,
      feedback,
      isValid: false,
    };
  }

  // Character requirements
  if (!/[a-z]/.test(password)) {
    feedback.push('Password must contain at least one lowercase letter');
  } else {
    score += 1;
  }

  if (!/[A-Z]/.test(password)) {
    feedback.push('Password must contain at least one uppercase letter');
  } else {
    score += 1;
  }

  if (!/[0-9]/.test(password)) {
    feedback.push('Password must contain at least one number');
  } else {
    score += 1;
  }

  if (!/[^a-zA-Z0-9]/.test(password)) {
    feedback.push('Password must contain at least one special character');
  } else {
    score += 1;
  }

  // Bonus for longer passwords
  if (password.length >= 12) {
    score += 1;
  }

  // Check for common weak patterns
  const weakPatterns = [
    /(.)\1{2,}/,  // Repeated characters
    /123|abc|qwe|password|admin|test/i,  // Common sequences
    /^[a-zA-Z]+$|^[0-9]+$/, // Only letters or only numbers
  ];

  if (weakPatterns.some(pattern => pattern.test(password))) {
    feedback.push('Password contains common patterns that make it weak');
    score = Math.max(0, score - 1);
  }

  // Cap score at 4
  score = Math.min(score, 4);

  return {
    score,
    feedback,
    isValid: score >= 3 && feedback.length === 0,
  };
};

// Generic field validation
export const validateRequired = (value: any, fieldName: string): string | null => {
  if (value === null || value === undefined || value === '') {
    return `${fieldName} is required`;
  }
  return null;
};

export const validateMinLength = (value: string, minLength: number, fieldName: string): string | null => {
  if (value && value.length < minLength) {
    return `${fieldName} must be at least ${minLength} characters long`;
  }
  return null;
};

export const validateMaxLength = (value: string, maxLength: number, fieldName: string): string | null => {
  if (value && value.length > maxLength) {
    return `${fieldName} must not exceed ${maxLength} characters`;
  }
  return null;
};

export const validateMinValue = (value: number, minValue: number, fieldName: string): string | null => {
  if (value < minValue) {
    return `${fieldName} must be at least ${minValue}`;
  }
  return null;
};

export const validateMaxValue = (value: number, maxValue: number, fieldName: string): string | null => {
  if (value > maxValue) {
    return `${fieldName} must not exceed ${maxValue}`;
  }
  return null;
};

export const validatePattern = (value: string, pattern: RegExp, fieldName: string, message?: string): string | null => {
  if (value && !pattern.test(value)) {
    return message || `${fieldName} format is invalid`;
  }
  return null;
};

// Business-specific validations with enhanced security
export const validateCustomerData = (customer: any): Record<string, string> => {
  const errors: Record<string, string> = {};

  // Type validation
  if (!customer || typeof customer !== 'object') {
    errors._general = 'Invalid customer data format';
    return errors;
  }

  // Name validations with length limits and content checks
  const firstNameError = validateRequired(customer.firstName, 'First name');
  if (firstNameError) {
    errors.firstName = firstNameError;
  } else {
    const firstName = String(customer.firstName);
    if (firstName.length > MAX_NAME_LENGTH) {
      errors.firstName = `First name must not exceed ${MAX_NAME_LENGTH} characters`;
    } else if (containsDangerousContent(firstName)) {
      errors.firstName = 'First name contains invalid characters';
    } else if (!/^[a-zA-Z\s\-'\.]+$/.test(firstName)) {
      errors.firstName = 'First name can only contain letters, spaces, hyphens, apostrophes, and periods';
    }
  }

  const lastNameError = validateRequired(customer.lastName, 'Last name');
  if (lastNameError) {
    errors.lastName = lastNameError;
  } else {
    const lastName = String(customer.lastName);
    if (lastName.length > MAX_NAME_LENGTH) {
      errors.lastName = `Last name must not exceed ${MAX_NAME_LENGTH} characters`;
    } else if (containsDangerousContent(lastName)) {
      errors.lastName = 'Last name contains invalid characters';
    } else if (!/^[a-zA-Z\s\-'\.]+$/.test(lastName)) {
      errors.lastName = 'Last name can only contain letters, spaces, hyphens, apostrophes, and periods';
    }
  }

  // Email validation
  const emailError = validateRequired(customer.email, 'Email');
  if (emailError) {
    errors.email = emailError;
  } else if (!isValidEmail(customer.email)) {
    errors.email = 'Please enter a valid email address';
  }

  // Phone validation
  if (customer.phone && !isValidPhone(customer.phone)) {
    errors.phone = 'Please enter a valid phone number';
  }

  // Website validation
  if (customer.website && !isValidUrl(customer.website)) {
    errors.website = 'Please enter a valid website URL';
  }

  // Company name validation
  if (customer.companyName) {
    const companyName = String(customer.companyName);
    if (companyName.length > 200) {
      errors.companyName = 'Company name must not exceed 200 characters';
    } else if (containsDangerousContent(companyName)) {
      errors.companyName = 'Company name contains invalid characters';
    }
  }

  // Address validation
  if (customer.address) {
    const address = String(customer.address);
    if (address.length > 500) {
      errors.address = 'Address must not exceed 500 characters';
    } else if (containsDangerousContent(address)) {
      errors.address = 'Address contains invalid characters';
    }
  }

  return errors;
};

export const validateProductData = (product: any): Record<string, string> => {
  const errors: Record<string, string> = {};

  const nameError = validateRequired(product.name, 'Product name');
  if (nameError) errors.name = nameError;

  const skuError = validateRequired(product.sku, 'SKU');
  if (skuError) errors.sku = skuError;

  const priceError = validateRequired(product.price, 'Price');
  if (priceError) {
    errors.price = priceError;
  } else {
    const minPriceError = validateMinValue(product.price, 0, 'Price');
    if (minPriceError) errors.price = minPriceError;
  }

  if (product.cost !== undefined && product.cost !== null) {
    const costError = validateMinValue(product.cost, 0, 'Cost');
    if (costError) errors.cost = costError;
  }

  return errors;
};

export const validateOrderData = (order: any): Record<string, string> => {
  const errors: Record<string, string> = {};

  const customerError = validateRequired(order.customerId, 'Customer');
  if (customerError) errors.customerId = customerError;

  if (!order.items || order.items.length === 0) {
    errors.items = 'Order must contain at least one item';
  }

  if (order.items && order.items.length > 0) {
    order.items.forEach((item: any, index: number) => {
      if (!item.productId) {
        errors[`items.${index}.productId`] = 'Product is required';
      }
      if (!item.quantity || item.quantity <= 0) {
        errors[`items.${index}.quantity`] = 'Quantity must be greater than 0';
      }
      if (!item.unitPrice || item.unitPrice <= 0) {
        errors[`items.${index}.unitPrice`] = 'Unit price must be greater than 0';
      }
    });
  }

  return errors;
};

// Credit card validation
export const validateCreditCard = (cardNumber: string): boolean => {
  // Remove non-digits
  const number = cardNumber.replace(/\D/g, '');
  
  // Check if empty or too short
  if (!number || number.length < 13 || number.length > 19) {
    return false;
  }

  // Luhn algorithm
  let sum = 0;
  let shouldDouble = false;

  for (let i = number.length - 1; i >= 0; i--) {
    let digit = parseInt(number[i]);

    if (shouldDouble) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }

    sum += digit;
    shouldDouble = !shouldDouble;
  }

  return sum % 10 === 0;
};

// CVV validation
export const validateCVV = (cvv: string, cardType?: string): boolean => {
  const cleanCvv = cvv.replace(/\D/g, '');
  
  if (cardType === 'amex') {
    return cleanCvv.length === 4;
  }
  
  return cleanCvv.length === 3;
};

// Expiry date validation
export const validateExpiryDate = (month: string, year: string): boolean => {
  const currentDate = new Date();
  const currentMonth = currentDate.getMonth() + 1;
  const currentYear = currentDate.getFullYear() % 100;

  const expMonth = parseInt(month);
  const expYear = parseInt(year);

  if (expMonth < 1 || expMonth > 12) {
    return false;
  }

  if (expYear < currentYear || (expYear === currentYear && expMonth < currentMonth)) {
    return false;
  }

  return true;
};

// Form validation helpers
export type ValidationRule<T = any> = {
  validate: (value: T, data?: any) => boolean;
  message: string;
};

export const createValidationRules = <T = any>(rules: Record<string, ValidationRule<T>[]>) => {
  return (data: Record<string, T>): Record<string, string> => {
    const errors: Record<string, string> = {};

    Object.keys(rules).forEach(field => {
      const fieldRules = rules[field];
      const value = data[field];

      for (const rule of fieldRules) {
        if (!rule.validate(value, data)) {
          errors[field] = rule.message;
          break; // Stop at first error
        }
      }
    });

    return errors;
  };
};

// Common validation rules
export const validationRules = {
  required: (message = 'This field is required'): ValidationRule => ({
    validate: (value) => value !== null && value !== undefined && value !== '',
    message,
  }),

  email: (message = 'Please enter a valid email address'): ValidationRule<string> => ({
    validate: (value) => !value || isValidEmail(value),
    message,
  }),

  minLength: (length: number, message?: string): ValidationRule<string> => ({
    validate: (value) => !value || value.length >= length,
    message: message || `Must be at least ${length} characters long`,
  }),

  maxLength: (length: number, message?: string): ValidationRule<string> => ({
    validate: (value) => !value || value.length <= length,
    message: message || `Must not exceed ${length} characters`,
  }),

  pattern: (pattern: RegExp, message = 'Invalid format'): ValidationRule<string> => ({
    validate: (value) => !value || pattern.test(value),
    message,
  }),

  min: (minValue: number, message?: string): ValidationRule<number> => ({
    validate: (value) => value >= minValue,
    message: message || `Must be at least ${minValue}`,
  }),

  max: (maxValue: number, message?: string): ValidationRule<number> => ({
    validate: (value) => value <= maxValue,
    message: message || `Must not exceed ${maxValue}`,
  }),
};