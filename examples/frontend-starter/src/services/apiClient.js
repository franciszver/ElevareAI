import axios from 'axios';

export const TOKEN_KEY = 'elevare_token';

// API Client Configuration - Updated 2025-11-08
// Use proxy in development, direct URL in production
// If VITE_API_BASE_URL is set, append /api/v1 if not already present
let baseUrl = import.meta.env.VITE_API_BASE_URL;
if (baseUrl && !baseUrl.includes('/api/v1')) {
  // Ensure base URL ends with /api/v1
  baseUrl = baseUrl.replace(/\/$/, '') + '/api/v1';
}

// IMPORTANT: Always use VITE_API_BASE_URL in production, never fall back to localhost
const API_BASE_URL = baseUrl || '/api/v1';
console.log('[API Client] Initialized with base URL:', API_BASE_URL, '- Build: 20251108-v2');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.log('[API] Response error:', {
      status: error.response?.status,
      url: error.config?.url,
      message: error.message
    });

    const isAuthEndpoint = error.config?.url?.includes('/auth/login') || error.config?.url?.includes('/auth/register');

    if (error.response?.status === 401 && !isAuthEndpoint) {
      console.log('[API] 401 - clearing token and redirecting to login');
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API methods
export const api = {
  // Summaries
  getSummaries: (userId) => apiClient.get(`/summaries/${userId}`),
  
  // Practice
  assignPractice: (data) => {
    // FastAPI endpoint expects query parameters for POST /practice/assign
    const params = new URLSearchParams();
    Object.keys(data).forEach(key => {
      if (data[key] !== null && data[key] !== undefined) {
        if (Array.isArray(data[key])) {
          // Handle arrays (like goal_tags)
          data[key].forEach(item => params.append(key, item));
        } else {
          params.append(key, data[key]);
        }
      }
    });
    return apiClient.post(`/practice/assign?${params.toString()}`);
  },
  // Async practice assignment (returns job ID immediately)
  assignPracticeAsync: (data) => {
    return apiClient.post('/practice/assign/async', data);
  },
  // Get job status
  getJobStatus: (jobId) => {
    return apiClient.get(`/jobs/${jobId}`);
  },
  completePractice: (assignmentId, itemId, data) => 
    apiClient.post(`/practice/complete?assignment_id=${assignmentId}&item_id=${itemId}`, data),
  
  // Q&A
  submitQuery: (data) => apiClient.post('/qa/query', data),
  getConversationHistory: (userId, limit = 10, hours = 24) => 
    apiClient.get(`/enhancements/qa/conversation-history/${userId}?limit=${limit}&hours=${hours}`),
  
  // Progress
  getProgress: (userId) => apiClient.get(`/progress/${userId}`),
  
  // Goals
  getGoals: (userId) => apiClient.get(`/goals?student_id=${userId}`),
  createGoal: (data) => apiClient.post('/goals', data),
  deleteGoal: (goalId) => apiClient.delete(`/goals/${goalId}`),
  resetGoal: (goalId) => apiClient.post(`/goals/${goalId}/reset`),
  
  // Messaging
  getThreads: (userId) => apiClient.get(`/messaging/threads?user_id=${userId}`),
  sendMessage: (threadId, data) => 
    apiClient.post(`/messaging/threads/${threadId}/messages`, data),
  
  // Nudges
  getNudges: (userId) => apiClient.get(`/nudges/users/${userId}`),
  engageNudge: (nudgeId, engagementType) => 
    apiClient.post(`/nudges/${nudgeId}/engage`, { engagement_type: engagementType }),
  
  // Auth
  getCurrentUser: () => apiClient.get('/auth/me'),
};

export default apiClient;

