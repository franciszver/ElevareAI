import apiClient from '../services/apiClient';

/**
 * Register a new user
 * @param {string} email - User email
 * @param {string} password - User password
 * @param {string} [name] - Optional display name
 * @param {string} [role] - Optional role (student/tutor/parent)
 * @returns {Promise<Object>} { user_id, email, role }
 */
export async function register(email, password, name, role) {
  const payload = { email, password };
  if (name) payload.name = name;
  if (role) payload.role = role;

  const response = await apiClient.post('/auth/register', payload);
  return response.data;
}

/**
 * Log in a user
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<{token: string, user: Object}>}
 */
export async function login(email, password) {
  const response = await apiClient.post('/auth/login', { email, password });
  const { access_token, user_id, email: userEmail, role } = response.data;

  return {
    token: access_token,
    user: { id: user_id, email: userEmail, role },
  };
}

/**
 * Fetch the current authenticated user using the stored token
 * @returns {Promise<Object>} { id, email, role, ... }
 */
export async function getCurrentUser() {
  const response = await apiClient.get('/auth/me');
  return response.data.data;
}
