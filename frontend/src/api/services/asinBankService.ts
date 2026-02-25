import apiClient from '../apiClient';

export interface AsinBankItem {
	id: number;
	lead_id: string;
	size: string | null;
	asin: string;
	created_at: string | null;
}

export interface AsinBankResponse {
	total: number;
	skip: number;
	limit: number;
	items: AsinBankItem[];
}

export interface CreateAsinRequest {
	lead_id: string;
	asin: string;
	size?: string | null;
}

class AsinBankService {
	/**
	 * Get all ASINs from the bank
	 */
	async getAsinBank(params?: {
		skip?: number;
		limit?: number;
		lead_id?: string;
		asin?: string;
		size?: string;
	}): Promise<AsinBankResponse> {
		return apiClient.get<AsinBankResponse>({
			url: '/api/v1/purchase-tracker/asin-bank',
			params,
		});
	}

	/**
	 * Create a new ASIN manually
	 */
	async createAsin(data: CreateAsinRequest): Promise<AsinBankItem> {
		return apiClient.post<AsinBankItem>({
			url: '/api/v1/purchase-tracker/asin-bank',
			data,
		});
	}

	/**
	 * Bulk delete ASINs by IDs
	 */
	async deleteAsins(ids: number[]): Promise<{ deleted_count: number; deleted_ids: number[] }> {
		return apiClient.delete<{ deleted_count: number; deleted_ids: number[] }>({
			url: '/api/v1/purchase-tracker/asin-bank',
			data: { ids },
		});
	}
}

export default new AsinBankService();

