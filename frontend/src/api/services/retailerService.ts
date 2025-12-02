import apiClient from '../apiClient';

export interface RetailerItem {
	id: number;
	name: string;
	link: string | null;
	wholesale: string | null; // 'yes', 'no', 'n/a'
	cancel_for_bulk: boolean;
	location: string | null; // 'EU', 'USA', 'CANADA', 'AU', 'UK', 'SA'
	shopify: boolean;
	total_spend: number;
	total_qty_of_items_ordered: number;
	percent_of_cancelled_qty: number;
	created_at: string;
	updated_at: string;
}

export interface RetailerResponse {
	total: number;
	items: RetailerItem[];
}

export interface RetailerSummary {
	total_retailers: number;
	total_spend: number;
	total_items_ordered: number;
	by_location: Record<string, number>;
	by_wholesale: Record<string, number>;
	shopify_count: number;
}

class RetailerService {
	/**
	 * Get all retailers
	 */
	async getRetailers(params?: {
		skip?: number;
		limit?: number;
		location?: string;
		wholesale?: string;
		shopify?: boolean;
	}): Promise<RetailerResponse> {
		return apiClient.get<RetailerResponse>({
			url: '/api/v1/retailers/',
			params,
		});
	}

	/**
	 * Get retailer by ID
	 */
	async getRetailerById(id: number): Promise<RetailerItem> {
		return apiClient.get<RetailerItem>({
			url: `/api/v1/retailers/${id}`,
		});
	}

	/**
	 * Get retailer by name
	 */
	async getRetailerByName(name: string): Promise<RetailerItem> {
		return apiClient.get<RetailerItem>({
			url: `/api/v1/retailers/name/${name}`,
		});
	}

	/**
	 * Create new retailer
	 */
	async createRetailer(data: {
		name: string;
		link?: string;
		wholesale?: string;
		cancel_for_bulk?: boolean;
		location?: string;
		shopify?: boolean;
	}): Promise<RetailerItem> {
		return apiClient.post<RetailerItem>({
			url: '/api/v1/retailers/',
			data,
		});
	}

	/**
	 * Update retailer
	 */
	async updateRetailer(id: number, data: Partial<RetailerItem>): Promise<RetailerItem> {
		return apiClient.put<RetailerItem>({
			url: `/api/v1/retailers/${id}`,
			data,
		});
	}

	/**
	 * Delete retailer
	 */
	async deleteRetailer(id: number): Promise<void> {
		return apiClient.delete({
			url: `/api/v1/retailers/${id}`,
		});
	}

	/**
	 * Get summary statistics
	 */
	async getSummary(): Promise<RetailerSummary> {
		return apiClient.get<RetailerSummary>({
			url: '/api/v1/retailers/stats/summary',
		});
	}
}

export default new RetailerService();

