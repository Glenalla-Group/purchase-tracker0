import apiClient from '../apiClient';

export interface PurchaseTrackerItem {
	product_name: string;
	id: number;
	date: string | null;
	created_at: string | null;  // When the record was created in the system
	lead_id: string | null;
	platform: string | null;
	brand: string | null;
	name: string | null;
	size: string | null;
	asin: string | null;
	order_number: string | null;
	supplier: string | null;  // Retailer name from oa_sourcing
	unique_id: string | null;  // Retailer product ID (e.g. style code, SKU)
	og_qty: number | null;
	final_qty: number | null;
	cancelled_qty: number | null;
	ppu: number | null;
	total_spend: number | null;
	status: string | null;
	
	// Fulfillment tracking
	shipped_to_pw: number | null;
	arrived: number | null;
	checked_in: number | null;
	shipped_out: number | null;
	tracking: string | null;
	delivery_date: string | null;
	location: string | null;
	address: string | null;
	in_bound: boolean | null;
	
	// FBA fields
	outbound_name: string | null;
	fba_shipment: string | null;
	fba_msku: string | null;
	
	// Other
	audited: boolean | null;
	notes: string | null;
}

export interface PurchaseTrackerResponse {
	total: number;
	skip: number;
	limit: number;
	items: PurchaseTrackerItem[];
}

export interface ManualPurchaseRequest {
	unique_id: string;
	size: string;
	qty: number;
	order_number: string;
}

export interface ManualPurchaseResponse {
	id: number;
	lead_id: string;
	date: string | null;
	platform: string | null;
	order_number: string | null;
	product_name: string | null;
	size: string | null;
	asin: string | null;
	og_qty: number | null;
	final_qty: number | null;
	ppu: number | null;
	rsp: number | null;
	total_spend: number | null;
	status: string | null;
	fba_msku: string | null;
	supplier: string | null;
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
		product_name?: string;
		asin?: string;
		order_number?: string;
		supplier?: string;
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

	/**
	 * Manually create a purchase tracker entry
	 */
	async createManualPurchase(data: ManualPurchaseRequest): Promise<ManualPurchaseResponse> {
		return apiClient.post<ManualPurchaseResponse>({
			url: '/api/v1/purchase-tracker/purchases/manual',
			data,
		});
	}

	/**
	 * Update a purchase tracker entry
	 */
	async updatePurchase(id: number, data: Partial<PurchaseTrackerItem>): Promise<any> {
		return apiClient.patch({
			url: `/api/v1/purchase-tracker/purchases/${id}`,
			data,
		});
	}

	/**
	 * Bulk delete purchases by IDs
	 */
	async bulkDeletePurchases(ids: number[]): Promise<{ deleted_count: number; deleted_ids: number[] }> {
		return apiClient.delete<{ deleted_count: number; deleted_ids: number[] }>({
			url: '/api/v1/purchase-tracker/purchases',
			data: { ids },
		});
	}

	/**
	 * Process inbound creation automation
	 * Extracts purchase records where final_qty = shipped_to_pw
	 * and processes them through PrepWorx automation
	 * 
	 * Note: This operation can take several minutes due to browser automation,
	 * so we use a longer timeout (10 minutes = 600000ms)
	 */
	async processInboundCreation(): Promise<any> {
		return apiClient.post<any>({
			url: '/api/v1/purchase-tracker/process-inbound-creation',
			data: {},
			timeout: 600000, // 10 minutes timeout for browser automation
		});
	}

	/**
	 * Process outbound creation for Lloyd Lane
	 * Filters records where checked_in = shipped_to_pw
	 * Generates Inventory Lab CSV file with:
	 * - ASIN, TITLE, COSTUNIT (weighted average), LISTPRICE (from Keepa API)
	 * - QUANTITY, PURCHASEDDATE, SUPPLIER, CONDITION, MSKU
	 * 
	 * Note: This operation may take a few minutes due to Keepa API calls
	 */
	async processOutboundCreation(): Promise<any> {
		return apiClient.post<any>({
			url: '/api/v1/purchase-tracker/process-outbound-creation',
			data: {},
			timeout: 300000, // 5 minutes timeout for API calls
		});
	}

}

export default new PurchaseTrackerService();

