import axios, { AxiosError } from 'axios';

const BASE = '/api/v1';

const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  register: (d: { email: string; password: string; full_name: string; role: string }) =>
    api.post('/auth/register', d).then((r) => r.data),
  login: (d: { email: string; password: string }) =>
    api.post('/auth/login', d).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
};

// Vendors
export const vendorApi = {
  list: (params?: { skip?: number; limit?: number; search?: string }) =>
    api.get('/vendors', { params }).then((r) => r.data),
  get: (id: number) => api.get(`/vendors/${id}`).then((r) => r.data),
  create: (d: object) => api.post('/vendors', d).then((r) => r.data),
};

// Products
export const productApi = {
  list: (params?: { skip?: number; limit?: number; search?: string }) =>
    api.get('/products', { params }).then((r) => r.data),
  get: (id: number) => api.get(`/products/${id}`).then((r) => r.data),
  create: (d: object) => api.post('/products', d).then((r) => r.data),
};

// CRM / Leads
export const leadApi = {
  list: (params?: { skip?: number; limit?: number; stage?: string; segment?: string }) =>
    api.get('/leads', { params }).then((r) => r.data),
  get: (id: number) => api.get(`/leads/${id}`).then((r) => r.data),
  create: (d: object) => api.post('/leads', d).then((r) => r.data),
  updateStage: (id: number, stage: string) =>
    api.patch(`/leads/${id}/stage`, { stage }).then((r) => r.data),
  funnel: () => api.get('/crm/funnel').then((r) => r.data),
};

// Orders
export const orderApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) =>
    api.get('/orders/b2c', { params }).then((r) => r.data),
  get: (id: number) => api.get(`/orders/b2c/${id}`).then((r) => r.data),
  create: (d: object) => api.post('/orders/b2c', d).then((r) => r.data),
  tracking: (id: number) => api.get(`/orders/b2c/${id}/tracking`).then((r) => r.data),
  feedbackSummary: () => api.get('/orders/b2c/feedback/summary').then((r) => r.data),
};

// RFQ
export const rfqApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    api.get('/rfq/broadcasts', { params }).then((r) => r.data),
  create: (d: object) => api.post('/rfq/broadcasts', d).then((r) => r.data),
  responses: (id: number) => api.get(`/rfq/broadcasts/${id}/responses`).then((r) => r.data),
};

// Analytics
export const analyticsApi = {
  overview: () => api.get('/crm/dashboard').then((r) => r.data),
  funnel: () => api.get('/crm/funnel').then((r) => r.data),
  marketing: () => api.get('/analytics/sales/drill-down').then((r) => r.data),
  salesPredictive: () => api.get('/analytics/sales/predictive').then((r) => r.data),
};

export default api;
