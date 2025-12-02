import apiClient from '../apiClient';

export interface AsinBankItem {
	id: number;
	lead_id: string;
	size: string | null;
	asin: string;
}

export interface AsinBankResponse {
	total: number;
	skip: number;
	limit: number;
	items: AsinBankItem[];
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
}

export default new AsinBankService();

