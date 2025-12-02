import apiClient from '../apiClient';

// ==================== Interfaces ====================

export interface AsinData {
	asin?: string;
	size?: string;
	recommendedQuantity?: number;
}

export interface LeadSubmittalData {
	submittedBy: string;
	productName: string;
	productSku: string;
	retailerLink?: string;
	retailerName: string;
	amazonLink?: string;
	uniqueId?: string;
	ppu: string;
	rsp: string;
	margin: string;
	pros: string;
	cons: string;
	otherNotes?: string;
	promoCode?: string;
	asins: AsinData[];
}

export interface LeadSubmittalResponse {
	success: boolean;
	lead_id: string;
	id: number;
	asins_created: number;
	asins_reused: number;
	total_asins: number;
	total_suggested_qty: number;
}

export interface Lead {
	id: number;
	lead_id: string;
	timestamp: string | null;
	sourcer: string;
	retailer_name: string;
	product_name: string;
	product_sku: string;
	retailer_link: string | null;
	amazon_link: string | null;
	unique_id: string | null;
	purchased: string | null;
	purchase_more: string | null;
	pros: string | null;
	cons: string | null;
	other_notes: string | null;
	head_review: string | null;
	feedback_qty: string | null;
	suggested_qty: number | null;
	pairs_per_lead: number | null;
	pairs_per_sku: number | null;
	ppu: number | null;
	rsp: number | null;
	margin: number | null;
	promo_code: string | null;
	sales_rank: string | null;
	buy_box: string | null;
	new_price: string | null;
	pick_pack_fee: number | null;
	referral_fee: number | null;
	total_fee: number | null;
	margin_using_rsp: number | null;
	monitored: string | null;
	// ASINs are fetched separately from asin_bank table
	asins?: AsinInLead[];
}

export interface AsinInLead {
	id: number;
	asin: string;
	size: string;
	recommended_quantity: number;
}

export interface LeadsResponse {
	total: number;
	skip: number;
	limit: number;
	items: Lead[];
}

export interface UpdateLeadData {
	productName?: string;
	retailerLink?: string;
	amazonLink?: string;
	purchased?: string;
	purchaseMoreIfAvailable?: string;
	monitored?: boolean;
	pros?: string;
	cons?: string;
	otherNotesConcerns?: string;
	headOfProductReviewNotes?: string;
	feedbackAndNotesOnQuantity?: string;
	pairsPerLeadId?: number;
	pairsPerSku?: number;
	salesRank?: string;
	asin1BuyBox?: number;
	asin1NewPrice?: number;
	pickPackFee?: number;
	referralFee?: number;
	totalFee?: number;
	promoCode?: string;
}

// ==================== Service ====================

class LeadService {
	/**
	 * Submit a new lead
	 */
	async submitLead(data: LeadSubmittalData): Promise<LeadSubmittalResponse> {
		return apiClient.post<LeadSubmittalResponse>({
			url: '/api/v1/purchase-tracker/leads',
			data,
		});
	}

	/**
	 * Get all leads with pagination and filters
	 */
	async getLeads(params?: {
		skip?: number;
		limit?: number;
		retailer?: string;
		sourcer?: string;
	}): Promise<LeadsResponse> {
		return apiClient.get<LeadsResponse>({
			url: '/api/v1/purchase-tracker/leads',
			params,
		});
	}

	/**
	 * Get lead by ID
	 */
	async getLeadById(leadId: string): Promise<Lead> {
		return apiClient.get<Lead>({
			url: `/api/v1/purchase-tracker/leads/${leadId}`,
		});
	}

	/**
	 * Update lead by ID
	 */
	async updateLead(leadId: string, data: UpdateLeadData): Promise<{ status: number; message: string; data: any }> {
		return apiClient.patch<{ status: number; message: string; data: any }>({
			url: `/api/v1/purchase-tracker/leads/${leadId}`,
			data,
		});
	}

	/**
	 * Delete lead by ID
	 */
	async deleteLead(leadId: string): Promise<{ success: boolean; message: string }> {
		return apiClient.delete<{ success: boolean; message: string }>({
			url: `/api/v1/purchase-tracker/leads/${leadId}`,
		});
	}
}

export default new LeadService();

