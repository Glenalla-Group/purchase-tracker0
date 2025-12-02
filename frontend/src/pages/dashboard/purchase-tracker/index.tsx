import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Title } from "@/ui/typography";
import { Icon } from "@/components/icon";
import { DataTable } from "@/components/data-table";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
import purchaseTrackerService, { type PurchaseTrackerItem } from "@/api/services/purchaseTrackerService";
import retailerOrderService from "@/api/services/retailerOrderService";

export default function PurchaseTracker() {
	const [purchaseData, setPurchaseData] = useState<PurchaseTrackerItem[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [processingOrders, setProcessingOrders] = useState(false);
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 100,
	});

	// Search filters
	const [searchOrderNumber, setSearchOrderNumber] = useState("");
	const [searchPlatform, setSearchPlatform] = useState("");
	const [searchLeadId, setSearchLeadId] = useState("");

	// Define columns for the purchase tracker table
	const columns: ColumnDef<PurchaseTrackerItem>[] = [
		{
			accessorKey: "date",
			header: "Date",
			cell: ({ row }) => (
				<div className="font-medium">
					{row.original.date ? new Date(row.original.date).toLocaleDateString() : "—"}
				</div>
			),
		},
		{
			accessorKey: "platform",
			header: "Platform",
			cell: ({ row }) => (
				<div className="flex items-center gap-2">
					{row.original.platform === "Footlocker" && (
						<Icon icon="mdi:store" className="text-orange-500" />
					)}
					{row.original.platform === "Champs Sports" && (
						<Icon icon="mdi:store" className="text-blue-500" />
					)}
					{row.original.platform === "Dick's Sporting Goods" && (
						<Icon icon="mdi:store" className="text-green-500" />
					)}
					{row.original.platform === "Hibbett Sports" && (
						<Icon icon="mdi:store" className="text-purple-500" />
					)}
					{row.original.platform === "Shoe Palace" && (
						<Icon icon="mdi:store" className="text-pink-500" />
					)}
					{row.original.platform === "Snipes" && (
						<Icon icon="mdi:store" className="text-red-500" />
					)}
					{row.original.platform === "Finish Line" && (
						<Icon icon="mdi:store" className="text-yellow-500" />
					)}
					{row.original.platform === "ShopSimon" && (
						<Icon icon="mdi:store" className="text-teal-500" />
					)}
					<span>{row.original.platform || "—"}</span>
				</div>
			),
		},
		{
			accessorKey: "order_number",
			header: "Order Number",
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.order_number || "—"}
				</div>
			),
		},
		{
			accessorKey: "name",
			header: "Product",
			cell: ({ row }) => (
				<div className="max-w-[300px]">
					<div className="font-medium truncate">{row.original.name || "—"}</div>
					{row.original.brand && (
						<div className="text-sm text-muted-foreground">{row.original.brand}</div>
					)}
				</div>
			),
		},
		{
			accessorKey: "lead_id",
			header: "Lead ID",
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.lead_id || "—"}
				</div>
			),
		},
		{
			accessorKey: "size",
			header: "Size",
			cell: ({ row }) => <div className="text-center">{row.original.size || "—"}</div>,
		},
		{
			accessorKey: "asin",
			header: "ASIN",
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.asin || "—"}
				</div>
			),
		},
		{
			accessorKey: "final_qty",
			header: "Qty",
			cell: ({ row }) => (
				<div className="text-center font-medium">
					{row.original.final_qty || 0}
				</div>
			),
		},
		{
			accessorKey: "ppu",
			header: "PPU",
			cell: ({ row }) => (
				<div className="text-right">
					{row.original.ppu ? `$${row.original.ppu.toFixed(2)}` : "—"}
				</div>
			),
		},
		{
			accessorKey: "total_spend",
			header: "Total",
			cell: ({ row }) => (
				<div className="text-right font-medium">
					{row.original.total_spend ? `$${row.original.total_spend.toFixed(2)}` : "—"}
				</div>
			),
		},
		{
			accessorKey: "status",
			header: "Status",
			cell: ({ row }) => {
				const status = row.original.status || "Unknown";
				const statusColors: Record<string, string> = {
					Ordered: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
					Shipped: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
					Delivered: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
					Cancelled: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
				};
				const colorClass = statusColors[status] || "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
				return (
					<div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
						{status}
					</div>
				);
			},
		},
	];

	// Load purchase tracker data
	const loadPurchaseData = async (paginationOverride?: PaginationState) => {
		const currentPagination = paginationOverride || pagination;
		setLoading(true);

		try {
			const response = await purchaseTrackerService.getPurchases({
				skip: currentPagination.pageIndex * currentPagination.pageSize,
				limit: currentPagination.pageSize,
				platform: searchPlatform || undefined,
			});

			// Validate response structure
			if (!response) {
				throw new Error("No response from server");
			}

			// The API client interceptor returns only the 'data' part of the response
			// So response should be the data object directly, not wrapped in response.data
			if (typeof response !== 'object') {
				console.error("Invalid response type:", typeof response, response);
				throw new Error("Invalid response type from server");
			}

			// Safely access the data with fallbacks
			const items = response.items || [];
			const total = response.total || 0;

			setPurchaseData(items);
			setTotal(total);
		} catch (error: any) {
			console.error("Error loading purchase data:", error);
			
			// Set empty state on error
			setPurchaseData([]);
			setTotal(0);
			
			// Show user-friendly error message
			const errorMessage = error?.response?.data?.message || 
								error?.message || 
								"Failed to load purchase data";
			
			toast.error("Failed to load purchase data", {
				description: errorMessage,
			});
		} finally {
			setLoading(false);
		}
	};

	// Load data on component mount
	useEffect(() => {
		loadPurchaseData();
	}, []);

	// Handle pagination change
	const handlePaginationChange = (newPagination: PaginationState) => {
		setPagination(newPagination);
		loadPurchaseData(newPagination);
	};

	// Handle search
	const handleSearch = () => {
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		loadPurchaseData(newPagination);
	};

	// Handle clear filters
	const handleClearFilters = () => {
		setSearchOrderNumber("");
		setSearchPlatform("");
		setSearchLeadId("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadPurchaseData(newPagination), 0);
	};

	// Handle processing all retailer orders
	const handleProcessAllRetailerOrders = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing retailer orders...", {
				description: "Searching for order confirmation emails from all retailers",
			});

			const result = await retailerOrderService.processAllRetailerOrders(1);

			// Validate result structure
			if (!result) {
				throw new Error("Invalid response from server");
			}

			const totalProcessed = result.processed || 0;
			const totalSkipped = result.skipped_duplicate || 0;
			const totalEmails = result.total_emails || 0;
			const errors = result.errors || 0;

			if (totalProcessed > 0) {
				toast.success(`Successfully processed ${totalProcessed} orders!`, {
					description: totalSkipped > 0 
						? `Skipped ${totalSkipped} duplicate(s)` 
						: "Purchase records created from retailer emails",
				});

				// Reload purchase data to show new entries
				setTimeout(() => {
					loadPurchaseData();
				}, 2000);
			} else if (totalEmails === 0) {
				toast.info("No unprocessed retailer emails found", {
					description: "All order emails have been processed",
				});
			} else if (errors > 0) {
				toast.warning("No orders were processed", {
					description: result.error_messages?.[0] || "Check the logs for details",
				});
			} else {
				toast.info("No new orders to process", {
					description: "All available emails have been processed",
				});
			}
		} catch (error: any) {
			console.error("Error processing retailer orders:", error);
			
			// Extract meaningful error message
			const errorMessage = error?.response?.data?.message || 
								error?.response?.data?.detail ||
								error?.message || 
								"Failed to process retailer orders";
			
			toast.error("Failed to process retailer orders", {
				description: errorMessage,
			});
		} finally {
			setProcessingOrders(false);
		}
	};

	const handleProcessRetailerOrders = async (retailer: string) => {
		setProcessingOrders(true);
		try {
			toast.info(`Processing ${retailer} orders...`, {
				description: `Searching for order confirmation emails from ${retailer}`,
			});

			let result;
			switch (retailer) {
				case 'footlocker':
					result = await retailerOrderService.processFootlockerOrders(1);
					break;
				case 'champs':
					result = await retailerOrderService.processChampsOrders(1);
					break;
				case 'dicks':
					result = await retailerOrderService.processDicksOrders(1);
					break;
				case 'hibbett':
					result = await retailerOrderService.processHibbettOrders(1);
					break;
				case 'shoepalace':
					result = await retailerOrderService.processShoePalaceOrders(1);
					break;
				case 'snipes':
					result = await retailerOrderService.processSnipesOrders(1);
					break;
				case 'finishline':
					result = await retailerOrderService.processFinishLineOrders(1);
					break;
				case 'shopsimon':
					result = await retailerOrderService.processShopSimonOrders(1);
					break;
				default:
					throw new Error(`Unknown retailer: ${retailer}`);
			}

			// Validate result structure
			if (!result) {
				throw new Error("Invalid response from server");
			}

			const totalProcessed = result.processed || 0;
			const totalSkipped = result.skipped_duplicate || 0;
			const totalEmails = result.total_emails || 0;
			const errors = result.errors || 0;

			if (totalProcessed > 0) {
				toast.success(`Successfully processed ${totalProcessed} ${retailer} orders!`, {
					description: totalSkipped > 0 
						? `Skipped ${totalSkipped} duplicate(s)` 
						: "Purchase records created from retailer emails",
				});

				// Reload purchase data to show new entries
				setTimeout(() => {
					loadPurchaseData();
				}, 2000);
			} else if (totalEmails === 0) {
				toast.info(`No unprocessed ${retailer} emails found`, {
					description: "All order emails have been processed",
				});
			} else if (errors > 0) {
				toast.warning(`No ${retailer} orders were processed`, {
					description: result.error_messages?.[0] || "Check the logs for details",
				});
			} else {
				toast.info(`No new ${retailer} orders to process`, {
					description: "All available emails have been processed",
				});
			}
		} catch (error: any) {
			console.error(`Error processing ${retailer} orders:`, error);
			
			// Extract meaningful error message
			const errorMessage = error?.response?.data?.message || 
								error?.response?.data?.detail ||
								error?.message || 
								`Failed to process ${retailer} orders`;
			
			toast.error(`Failed to process ${retailer} orders`, {
				description: errorMessage,
			});
		} finally {
			setProcessingOrders(false);
		}
	};

	const pageCount = Math.ceil(total / pagination.pageSize);

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<Card>
				<CardHeader>
					<CardTitle>
						<Title as="h2">Purchase Tracker</Title>
						<p className="text-sm text-muted-foreground mt-2">
							View and manage purchase records. Process Footlocker order emails automatically.
						</p>
					</CardTitle>
				</CardHeader>
			</Card>

			{/* Search and Actions */}
			<Card>
				<CardHeader>
					<CardTitle>
						<Title as="h3" className="text-lg">
							Search & Actions
						</Title>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
						<Input
							placeholder="Order Number..."
							value={searchOrderNumber}
							onChange={(e) => setSearchOrderNumber(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSearch();
							}}
						/>
						<Input
							placeholder="Platform..."
							value={searchPlatform}
							onChange={(e) => setSearchPlatform(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSearch();
							}}
						/>
						<Input
							placeholder="Lead ID..."
							value={searchLeadId}
							onChange={(e) => setSearchLeadId(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSearch();
							}}
						/>
						<div className="flex gap-2">
							<Button onClick={handleSearch} className="flex-1">
								<Icon icon="mdi:magnify" className="mr-1" />
								Search
							</Button>
							<Button onClick={handleClearFilters} variant="outline" className="flex-1">
								<Icon icon="mdi:filter-off" />
								Clear
							</Button>
						</div>
					</div>

					{/* Action Buttons */}
					<div className="flex flex-col gap-4">
						{/* Main Process Button */}
						<div className="flex gap-2">
							<Button
								onClick={handleProcessAllRetailerOrders}
								variant="default"
								className="bg-primary hover:bg-primary/90"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:email-sync" className="mr-2" />
								{processingOrders ? "Processing..." : "Process All Retailer Orders"}
							</Button>
							<Button 
								onClick={() => loadPurchaseData()} 
								variant="outline"
								disabled={loading}
							>
								<Icon icon="mdi:refresh" className="mr-2" />
								{loading ? "Loading..." : "Refresh"}
							</Button>
						</div>
						
						{/* Individual Retailer Buttons */}
						<div className="flex flex-wrap gap-2">
							<Button
								onClick={() => handleProcessRetailerOrders('footlocker')}
								variant="outline"
								size="sm"
								className="bg-orange-50 hover:bg-orange-100 border-orange-200"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:store" className="mr-1" />
								Footlocker
							</Button>
							<Button
								onClick={() => handleProcessRetailerOrders('champs')}
								variant="outline"
								size="sm"
								className="bg-blue-50 hover:bg-blue-100 border-blue-200"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:store" className="mr-1" />
								Champs Sports
							</Button>
							<Button
								onClick={() => handleProcessRetailerOrders('dicks')}
								variant="outline"
								size="sm"
								className="bg-green-50 hover:bg-green-100 border-green-200"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:store" className="mr-1" />
								Dick's Sporting Goods
							</Button>
						<Button
							onClick={() => handleProcessRetailerOrders('hibbett')}
							variant="outline"
							size="sm"
							className="bg-purple-50 hover:bg-purple-100 border-purple-200"
							disabled={processingOrders || loading}
						>
							<Icon icon="mdi:store" className="mr-1" />
							Hibbett Sports
						</Button>
						<Button
							onClick={() => handleProcessRetailerOrders('shoepalace')}
							variant="outline"
							size="sm"
							className="bg-pink-50 hover:bg-pink-100 border-pink-200"
							disabled={processingOrders || loading}
						>
							<Icon icon="mdi:store" className="mr-1" />
							Shoe Palace
						</Button>
						<Button
							onClick={() => handleProcessRetailerOrders('snipes')}
							variant="outline"
							size="sm"
							className="bg-red-50 hover:bg-red-100 border-red-200"
							disabled={processingOrders || loading}
						>
							<Icon icon="mdi:store" className="mr-1" />
							Snipes
						</Button>
						<Button
							onClick={() => handleProcessRetailerOrders('finishline')}
							variant="outline"
							size="sm"
							className="bg-yellow-50 hover:bg-yellow-100 border-yellow-200"
							disabled={processingOrders || loading}
						>
							<Icon icon="mdi:store" className="mr-1" />
							Finish Line
						</Button>
						<Button
							onClick={() => handleProcessRetailerOrders('shopsimon')}
							variant="outline"
							size="sm"
							className="bg-teal-50 hover:bg-teal-100 border-teal-200"
							disabled={processingOrders || loading}
						>
							<Icon icon="mdi:store" className="mr-1" />
							ShopSimon
						</Button>
					</div>
				</div>
				<p className="text-xs text-muted-foreground mt-2">
					Automatically processes order confirmation emails from all supported retailers (Footlocker, Champs Sports, Dick's Sporting Goods, Hibbett Sports, Shoe Palace, Snipes, Finish Line, ShopSimon, etc.)
				</p>
				</CardContent>
			</Card>

			{/* Purchase Tracker Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Purchase Records ({total.toLocaleString()} total)
						</Title>
					</CardTitle>
				</CardHeader>
				<CardContent>
					{!loading && purchaseData.length === 0 ? (
						<div className="flex flex-col items-center justify-center py-12 text-center">
							<Icon icon="mdi:package-variant-closed" className="text-4xl text-muted-foreground mb-4" />
							<h3 className="text-lg font-semibold mb-2">No Purchase Records Found</h3>
							<p className="text-muted-foreground mb-4">
								No purchase records found. Process retailer orders to create purchase records.
							</p>
						</div>
					) : (
						<DataTable
							columns={columns}
							data={purchaseData}
							pageCount={pageCount}
							pageIndex={pagination.pageIndex}
							pageSize={pagination.pageSize}
							totalItems={total}
							onPaginationChange={handlePaginationChange}
							manualPagination={true}
							loading={loading}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}

