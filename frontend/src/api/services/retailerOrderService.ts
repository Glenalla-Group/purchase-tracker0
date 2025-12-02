import apiClient from '../apiClient';

export interface ProcessingResult {
	total_emails: number;
	processed: number;
	skipped_duplicate: number;
	errors: number;
	error_messages: string[];
}

export interface ProcessingStats {
	processed_emails: number;
	error_emails: number;
	processed_label: string | null;
	error_label: string | null;
}

class RetailerOrderService {
	/**
	 * Process order confirmation emails from ALL supported retailers
	 * @param maxEmails - Maximum number of emails to process per retailer
	 */
	async processAllRetailerOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process-all?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process Footlocker order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processFootlockerOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/footlocker?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process Champs Sports order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processChampsOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/champs?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process Dick's Sporting Goods order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
    async processDicksOrders(maxEmails: number = 20): Promise<ProcessingResult> {
        return apiClient.post<ProcessingResult>({
            url: `/api/v1/retailer-orders/process/dicks?max_emails=${maxEmails}`,
        });
    }

    async processHibbettOrders(maxEmails: number = 20): Promise<ProcessingResult> {
        return apiClient.post<ProcessingResult>({
            url: `/api/v1/retailer-orders/process/hibbett?max_emails=${maxEmails}`,
        });
    }

	/**
	 * Process Shoe Palace order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processShoePalaceOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/shoepalace?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process Snipes order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processSnipesOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/snipes?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process Finish Line order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processFinishLineOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/finishline?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Process ShopSimon order confirmation emails
	 * @param maxEmails - Maximum number of emails to process
	 */
	async processShopSimonOrders(maxEmails: number = 20): Promise<ProcessingResult> {
		return apiClient.post<ProcessingResult>({
			url: `/api/v1/retailer-orders/process/shopsimon?max_emails=${maxEmails}`,
		});
	}

	/**
	 * Get processing statistics
	 */
	async getProcessingStats(): Promise<ProcessingStats> {
		return apiClient.get<ProcessingStats>({
			url: '/api/v1/retailer-orders/processing-stats',
		});
	}
}

export default new RetailerOrderService();

