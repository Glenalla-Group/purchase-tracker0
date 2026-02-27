import apiClient from "../apiClient";

export interface ManualReviewItem {
	unique_id?: string;
	size?: string;
	product_name?: string;
	product_number?: string;
	color?: string;
	quantity?: number;
}

export interface ManualReviewEntry {
	id: number;
	gmail_message_id: string;
	retailer: string;
	email_type: string;
	subject?: string;
	extracted_order_number?: string;
	extracted_items?: ManualReviewItem[];
	missing_fields: string[];
	error_reason?: string;
	status: string;
	created_at?: string;
}

export interface ResolvePayload {
	order_number?: string;
	unique_id?: string;
	size?: string;
	quantity?: number;
	items?: ManualReviewItem[];
}

export default {
	async list(params?: { status?: string; retailer?: string; limit?: number; offset?: number }) {
		const q = new URLSearchParams();
		if (params?.status) q.set("status", params.status);
		if (params?.retailer) q.set("retailer", params.retailer);
		if (params?.limit) q.set("limit", String(params.limit));
		if (params?.offset) q.set("offset", String(params.offset));
		const query = q.toString();
		return apiClient.get<{ items: ManualReviewEntry[]; total: number }>({
			url: `/api/v1/email-manual-review${query ? `?${query}` : ""}`,
		});
	},
	async getPendingCount() {
		return apiClient.get<{ pending_count: number }>({
			url: "/api/v1/email-manual-review/count",
		});
	},
	async get(id: number) {
		return apiClient.get<ManualReviewEntry>({
			url: `/api/v1/email-manual-review/${id}`,
		});
	},
	async resolve(id: number, payload: ResolvePayload) {
		return apiClient.post<{ success: boolean; message: string; items_count: number }>({
			url: `/api/v1/email-manual-review/${id}/resolve`,
			data: payload,
		});
	},
	async dismiss(id: number) {
		return apiClient.post<{ success: boolean; message: string }>({
			url: `/api/v1/email-manual-review/${id}/dismiss`,
		});
	},
};
