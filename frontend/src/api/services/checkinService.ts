import apiClient from '../apiClient';

export interface CheckinItem {
	id: number;
	order_number: string | null;
	item_name: string | null;
	asin_bank_id: number | null;
	asin: string | null;
	size: string | null;
	quantity: number;
	checked_in_at: string;
}

export interface CheckinResponse {
	total: number;
	items: CheckinItem[];
}

export interface CheckinSummary {
	total_checkins: number;
	total_quantity_checked_in: number;
	checkins_today: number;
	top_orders: Array<{
		order_number: string;
		total_quantity: number;
		checkin_count: number;
	}>;
}

class CheckinService {
	/**
	 * Get all check-ins
	 */
	async getCheckins(params?: {
		skip?: number;
		limit?: number;
		order_number?: string;
		asin?: string;
		start_date?: string;
		end_date?: string;
	}): Promise<CheckinResponse> {
		return apiClient.get<CheckinResponse>({
			url: '/api/v1/checkin/',
			params,
		});
	}

	/**
	 * Get check-in by ID
	 */
	async getCheckinById(id: number): Promise<CheckinItem> {
		return apiClient.get<CheckinItem>({
			url: `/api/v1/checkin/${id}`,
		});
	}

	/**
	 * Get check-ins by order number
	 */
	async getCheckinsByOrder(orderNumber: string): Promise<{
		order_number: string;
		total_quantity: number;
		checkin_count: number;
		checkins: CheckinItem[];
	}> {
		return apiClient.get({
			url: `/api/v1/checkin/by-order/${orderNumber}`,
		});
	}

	/**
	 * Create new check-in
	 */
	async createCheckin(data: {
		order_number: string;
		item_name: string;
		asin?: string;
		size?: string;
		asin_bank_id?: number;
		quantity: number;
		notes?: string;
		checked_in_by?: string;
		checked_in_at?: string;
	}): Promise<CheckinItem> {
		return apiClient.post<CheckinItem>({
			url: '/api/v1/checkin/',
			data,
		});
	}

	/**
	 * Update check-in
	 */
	async updateCheckin(id: number, data: Partial<CheckinItem>): Promise<CheckinItem> {
		return apiClient.put<CheckinItem>({
			url: `/api/v1/checkin/${id}`,
			data,
		});
	}

	/**
	 * Delete check-in
	 */
	async deleteCheckin(id: number): Promise<void> {
		return apiClient.delete({
			url: `/api/v1/checkin/${id}`,
		});
	}

	/**
	 * Get summary statistics
	 */
	async getSummary(): Promise<CheckinSummary> {
		return apiClient.get<CheckinSummary>({
			url: '/api/v1/checkin/stats/summary',
		});
	}

	/**
	 * Process unprocessed PrepWorx inbound emails
	 */
	async processPrepWorxEmails(maxEmails: number = 20): Promise<{
		processing_count: number;
	}> {
		return apiClient.post({
			url: `/api/gmail/process-prepworx?max_emails=${maxEmails}`,
		});
	}
}

export default new CheckinService();
