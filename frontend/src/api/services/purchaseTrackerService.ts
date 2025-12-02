import apiClient from '../apiClient';

export interface PurchaseTrackerItem {
	id: number;
	date: string | null;
	lead_id: string | null;
	platform: string | null;
	brand: string | null;
	name: string | null;
	size: string | null;
	asin: string | null;
	order_number: string | null;
	final_qty: number | null;
	ppu: number | null;
	total_spend: number | null;
	status: string | null;
}

export interface PurchaseTrackerResponse {
	total: number;
	skip: number;
	limit: number;
	items: PurchaseTrackerItem[];
}

class PurchaseTrackerService {
	/**
	 * Get all purchases with pagination and filters
	 */
	async getPurchases(params?: {
		skip?: number;
		limit?: number;
		platform?: string;
		status?: string;
		start_date?: string;
		end_date?: string;
	}): Promise<PurchaseTrackerResponse> {
		return apiClient.get<PurchaseTrackerResponse>({
			url: '/api/v1/purchase-tracker/purchases',
			params,
		});
	}

	/**
	 * Get purchase by ID
	 */
	async getPurchaseById(id: number): Promise<any> {
		return apiClient.get({
			url: `/api/v1/purchase-tracker/purchases/${id}`,
		});
	}
}

export default new PurchaseTrackerService();

