/**
 * Form Validation Utilities
 * Reusable validation functions for forms
 */

export const validators = {
  required: (value) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return 'This field is required';
    }
    return null;
  },

  email: (value) => {
    if (!value) return null; // Use with required if needed
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) {
      return 'Please enter a valid email address';
    }
    return null;
  },

  minLength: (min) => (value) => {
    if (!value) return null;
    if (value.length < min) {
      return `Must be at least ${min} characters`;
    }
    return null;
  },

  maxLength: (max) => (value) => {
    if (!value) return null;
    if (value.length > max) {
      return `Must be no more than ${max} characters`;
    }
    return null;
  },

  date: (value) => {
    if (!value) return null;
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      return 'Please enter a valid date';
    }
    return null;
  },

  futureDate: (value) => {
    if (!value) return null;
    const date = new Date(value);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (date <= today) {
      return 'Date must be in the future';
    }
    return null;
  },

  url: (value) => {
    if (!value) return null;
    try {
      new URL(value);
      return null;
    } catch {
      return 'Please enter a valid URL';
    }
  },

  number: (value) => {
    if (!value) return null;
    if (isNaN(Number(value))) {
      return 'Please enter a valid number';
    }
    return null;
  },

  positiveNumber: (value) => {
    if (!value) return null;
    const num = Number(value);
    if (isNaN(num) || num <= 0) {
      return 'Please enter a positive number';
    }
    return null;
  },

  // Password policy validators (matching AWS Cognito requirements)
  passwordPolicy: (value) => {
    if (!value) return null;
    
    const errors = [];
    
    if (value.length < 8) {
      errors.push('at least 8 characters');
    }
    if (!/[A-Z]/.test(value)) {
      errors.push('one uppercase letter');
    }
    if (!/[a-z]/.test(value)) {
      errors.push('one lowercase letter');
    }
    if (!/[0-9]/.test(value)) {
      errors.push('one number');
    }
    if (!/[^A-Za-z0-9]/.test(value)) {
      errors.push('one symbol');
    }
    
    if (errors.length > 0) {
      return `Password must contain ${errors.join(', ')}`;
    }
    
    return null;
  },
};

/**
 * Validate a field with multiple validators
 * @param {*} value - The field value to validate
 * @param {Array} rules - Array of validation rules
 * @param {Object} allValues - All form values (for cross-field validation)
 */
export function validateField(value, rules, allValues = {}) {
  if (!rules || rules.length === 0) return null;

  for (const rule of rules) {
    let validator;
    let error;

    if (typeof rule === 'function') {
      validator = rule;
    } else if (typeof rule === 'string') {
      validator = validators[rule];
    } else if (typeof rule === 'object' && rule.validator) {
      validator = rule.validator;
      error = rule.error;
    }

    if (validator) {
      // Pass allValues if validator accepts 2 parameters (for cross-field validation)
      const result = validator.length === 2 ? validator(value, allValues) : validator(value);
      if (result) {
        return error || result;
      }
    }
  }

  return null;
}

/**
 * Validate an entire form
 */
export function validateForm(formData, schema) {
  const errors = {};

  for (const [field, rules] of Object.entries(schema)) {
    const value = formData[field];
    const error = validateField(value, rules, formData);
    if (error) {
      errors[field] = error;
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

