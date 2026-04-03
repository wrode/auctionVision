import {
  LotCard,
  LotDetail,
  ViewResponse,
  WantedViewResponse,
  FetchParams,
  ActionPayload,
  JobRequest,
  JobResponse,
} from './types';

const API_BASE = '/api';

class APIClient {
  private async request<T>(
    endpoint: string,
    method: string = 'GET',
    body?: any,
  ): Promise<T> {
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, options);

    if (!response.ok) {
      throw new Error(
        `API Error: ${response.status} ${response.statusText}`,
      );
    }

    return response.json();
  }

  async fetchLots(params: FetchParams = {}): Promise<LotCard[]> {
    const queryParams = new URLSearchParams();

    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);

    const query = queryParams.toString();
    const endpoint = query ? `/lots?${query}` : '/lots';

    return this.request<LotCard[]>(endpoint);
  }

  async fetchLotDetail(id: string): Promise<LotDetail> {
    return this.request<LotDetail>(`/lots/${id}`);
  }

  async fetchView(
    viewName: string,
    params: FetchParams = {},
  ): Promise<ViewResponse> {
    const queryParams = new URLSearchParams();

    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);

    const query = queryParams.toString();
    const endpoint = query
      ? `/views/${viewName}?${query}`
      : `/views/${viewName}`;

    return this.request<ViewResponse>(endpoint);
  }

  async fetchWanted(limit: number = 100): Promise<WantedViewResponse> {
    return this.request<WantedViewResponse>(`/views/wanted?limit=${limit}`);
  }

  async postAction(
    lotId: string,
    action: ActionPayload,
  ): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(
      `/lots/${lotId}/action`,
      'POST',
      action,
    );
  }

  async triggerJob(
    jobType: string,
    params: Record<string, any> = {},
  ): Promise<JobResponse> {
    const payload: JobRequest = {
      job_type: jobType,
      params,
    };

    return this.request<JobResponse>('/jobs', 'POST', payload);
  }

  async refreshView(viewName: string): Promise<JobResponse> {
    return this.triggerJob('refresh_view', { view_name: viewName });
  }
}

export const apiClient = new APIClient();
