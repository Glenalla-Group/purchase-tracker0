import apiClient from '../apiClient';

// ==================== Interfaces ====================

export interface Purchase {
	id: number;
	date: string | null;
	lead_id: string | null;
	platform: string | null;
	brand: string | null;
	product_name: string | null;
	size: string | null;
	asin: string | null;
	order_number: string | null;
	sourced_by: string | null;
	supplier: string | null;
	
	// Quantities
	og_qty: number | null;
	final_qty: number | null;
	cancelled_qty: number | null;
	
	// Pricing
	ppu: number | null;
	rsp: number | null;
	total_spend: number | null;
	profit: number | null;
	margin_percent: number | null;
	
	// Fulfillment tracking (NUMBERS indicating stages)
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
	
	// Refund tracking
	amt_of_cancelled_qty_credit_card: number | null;
	amt_of_cancelled_qty_gift_card: number | null;
	expected_refund_amount: number | null;
	amount_refunded: number | null;
	refund_status: string | null;
	refund_method: string | null;
	date_of_refund: string | null;
	
	// Other
	status: string | null;
	audited: boolean | null;
	notes: string | null;
	validation_bank: string | null;
	concat: string | null;
}

export interface PurchasesResponse {
	total: number;
	skip: number;
	limit: number;
	items: Purchase[];
}

export interface UpdatePurchaseData {
	// Quantities
	og_qty?: number;
	final_qty?: number;
	cancelled_qty?: number;
	
	// Fulfillment tracking
	shipped_to_pw?: number;
	arrived?: number;
	checked_in?: number;
	shipped_out?: number;
	tracking?: string;
	delivery_date?: string;
	location?: string;
	address?: string;
	in_bound?: boolean;
	
	// FBA fields
	outbound_name?: string;
	fba_shipment?: string;
	fba_msku?: string;
	
	// Refund tracking
	amt_of_cancelled_qty_credit_card?: number;
	amt_of_cancelled_qty_gift_card?: number;
	expected_refund_amount?: number;
	amount_refunded?: number;
	refund_status?: string;
	refund_method?: string;
	date_of_refund?: string;
	
	// Other
	status?: string;
	audited?: boolean;
	notes?: string;
	validation_bank?: string;
}

// ==================== Service ====================

class PurchaseService {
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
	}): Promise<PurchasesResponse> {
		return apiClient.get<PurchasesResponse>({
			url: '/api/v1/purchase-tracker/purchases',
			params,
		});
	}

	/**
	 * Get purchase by ID
	 */
	async getPurchaseById(purchaseId: number): Promise<Purchase> {
		return apiClient.get<Purchase>({
			url: `/api/v1/purchase-tracker/purchases/${purchaseId}`,
		});
	}

	/**
	 * Update purchase by ID
	 */
	async updatePurchase(purchaseId: number, data: UpdatePurchaseData): Promise<{ status: number; message: string; data: any }> {
		return apiClient.patch<{ status: number; message: string; data: any }>({
			url: `/api/v1/purchase-tracker/purchases/${purchaseId}`,
			data,
		});
	}

	/**
	 * Delete purchase by ID
	 */
	async deletePurchase(purchaseId: number): Promise<{ success: boolean; message: string }> {
		return apiClient.delete<{ success: boolean; message: string }>({
			url: `/api/v1/purchase-tracker/purchases/${purchaseId}`,
		});
	}
}

export default new PurchaseService();

