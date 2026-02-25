import apiClient from '../apiClient';

export interface PTORequest {
	id: number;
	user_id: number;
	username?: string | null;
	start_date: string;
	end_date: string;
	total_days: number;
	request_type: 'pto' | 'sick' | 'personal' | 'holiday';
	status: 'pending' | 'approved' | 'rejected' | 'cancelled';
	reason?: string | null;
	notes?: string | null;
	approved_by_id?: number | null;
	approved_by_username?: string | null;
	approved_at?: string | null;
	created_at: string;
	updated_at: string;
}

export interface PTORequestResponse {
	total: number;
	items: PTORequest[];
}

export interface PTOStats {
	user_id: number;
	username: string;
	total_pto_days: number;
	pending_requests: number;
	approved_requests: number;
	rejected_requests: number;
	upcoming_pto: PTORequest[];
}

export interface AllUsersPTOStats {
	users: Array<{
		user_id: number;
		username: string;
		total_pto_days: number;
		pending_requests: number;
		approved_requests?: number;
		rejected_requests?: number;
	}>;
	start_date?: string;
	end_date?: string;
}

export interface Holiday {
	id: number;
	name: string;
	date: string;
	country: string;
	is_recurring: boolean;
	year?: number | null;
	description?: string | null;
	created_at: string;
	updated_at: string;
}

export interface HolidayResponse {
	total: number;
	items: Holiday[];
}

export interface CalendarEvent {
	id: string;
	title: string;
	start: string;
	end: string;
	allDay: boolean;
	backgroundColor: string;
	borderColor: string;
	extendedProps: {
		type: string;
		country?: string;
		description?: string;
		user_id?: number;
		username?: string;
		request_type?: string;
		status?: string;
	};
}

class PTOService {
	/**
	 * Get all PTO requests
	 */
	async getPTORequests(params?: {
		skip?: number;
		limit?: number;
		user_id?: number;
		status?: string;
		request_type?: string;
		start_date?: string;
		end_date?: string;
	}): Promise<PTORequestResponse> {
		const response = await apiClient.get<{ status: number; data: PTORequestResponse; message: string }>({
			url: '/api/v1/pto/',
			params,
		});
		return (response as any).data || response;
	}

	/**
	 * Get PTO request by ID
	 */
	async getPTORequestById(id: number): Promise<PTORequest> {
		const response = await apiClient.get<{ status: number; data: PTORequest; message: string }>({
			url: `/api/v1/pto/${id}`,
		});
		return (response as any).data || response;
	}

	/**
	 * Create new PTO request
	 */
	async createPTORequest(data: {
		user_id: number;
		start_date: string;
		end_date: string;
		request_type?: 'pto' | 'sick' | 'personal' | 'holiday';
		reason?: string;
		notes?: string;
	}): Promise<PTORequest> {
		const response = await apiClient.post<{ status: number; data: PTORequest; message: string }>({
			url: '/api/v1/pto/',
			data,
		});
		return (response as any).data || response;
	}

	/**
	 * Update PTO request
	 */
	async updatePTORequest(id: number, data: {
		start_date?: string;
		end_date?: string;
		request_type?: string;
		status?: string;
		reason?: string;
		notes?: string;
		approved_by_id?: number;
	}): Promise<PTORequest> {
		const response = await apiClient.put<{ status: number; data: PTORequest; message: string }>({
			url: `/api/v1/pto/${id}`,
			data,
		});
		return (response as any).data || response;
	}

	/**
	 * Delete PTO request
	 */
	async deletePTORequest(id: number): Promise<void> {
		await apiClient.delete({
			url: `/api/v1/pto/${id}`,
		});
	}

	/**
	 * Get PTO statistics for a user
	 */
	async getUserPTOStats(userId: number): Promise<PTOStats> {
		const response = await apiClient.get<{ status: number; data: PTOStats; message: string }>({
			url: `/api/v1/pto/user/${userId}/stats`,
		});
		return (response as any).data || response;
	}

	/**
	 * Get PTO statistics for all users
	 */
	async getAllUsersPTOStats(params?: {
		start_date?: string;
		end_date?: string;
	}): Promise<AllUsersPTOStats & { start_date?: string; end_date?: string }> {
		const response = await apiClient.get<{ status: number; data: AllUsersPTOStats & { start_date?: string; end_date?: string }; message: string }>({
			url: '/api/v1/pto/stats/all-users',
			params,
		});
		return (response as any).data || response;
	}

	/**
	 * Get all holidays
	 */
	async getHolidays(params?: {
		skip?: number;
		limit?: number;
		country?: string;
		year?: number;
		start_date?: string;
		end_date?: string;
		is_recurring?: boolean;
	}): Promise<HolidayResponse> {
		const response = await apiClient.get<{ status: number; data: HolidayResponse; message: string }>({
			url: '/api/v1/holidays/',
			params,
		});
		return (response as any).data || response;
	}

	/**
	 * Get holiday by ID
	 */
	async getHolidayById(id: number): Promise<Holiday> {
		const response = await apiClient.get<{ status: number; data: Holiday; message: string }>({
			url: `/api/v1/holidays/${id}`,
		});
		return (response as any).data || response;
	}

	/**
	 * Create new holiday
	 */
	async createHoliday(data: {
		name: string;
		date: string;
		country: string;
		is_recurring?: boolean;
		year?: number;
		description?: string;
	}): Promise<Holiday> {
		const response = await apiClient.post<{ status: number; data: Holiday; message: string }>({
			url: '/api/v1/holidays/',
			data,
		});
		return (response as any).data || response;
	}

	/**
	 * Update holiday
	 */
	async updateHoliday(id: number, data: {
		name?: string;
		date?: string;
		country?: string;
		is_recurring?: boolean;
		year?: number;
		description?: string;
	}): Promise<Holiday> {
		const response = await apiClient.put<{ status: number; data: Holiday; message: string }>({
			url: `/api/v1/holidays/${id}`,
			data,
		});
		return (response as any).data || response;
	}

	/**
	 * Delete holiday
	 */
	async deleteHoliday(id: number): Promise<void> {
		await apiClient.delete({
			url: `/api/v1/holidays/${id}`,
		});
	}

	/**
	 * Get calendar events (holidays and PTO) for a date range
	 */
	async getCalendarEvents(startDate: string, endDate: string, country?: string): Promise<{ events: CalendarEvent[] }> {
		const params: Record<string, string> = {
			start_date: startDate,
			end_date: endDate,
		};
		if (country) {
			params.country = country;
		}

		const response = await apiClient.get<{ status: number; data: { events: CalendarEvent[] }; message: string }>({
			url: '/api/v1/holidays/calendar/events',
			params,
		});
		return (response as any).data || response;
	}
}

export default new PTOService();

