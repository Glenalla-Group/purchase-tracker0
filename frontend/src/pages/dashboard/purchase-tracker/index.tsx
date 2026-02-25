import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/ui/card";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Textarea } from "@/ui/textarea";
import { Title } from "@/ui/typography";
import { Icon } from "@/components/icon";
import { DataTable } from "@/components/data-table";
import { Label } from "@/ui/label";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
import purchaseTrackerService, { type PurchaseTrackerItem, type ManualPurchaseRequest } from "@/api/services/purchaseTrackerService";
import retailerOrderService from "@/api/services/retailerOrderService";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import {
	Sheet,
	SheetContent,
	SheetHeader,
	SheetTitle,
} from "@/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/ui/tabs";
import { Separator } from "@/ui/separator";
import { Checkbox } from "@/ui/checkbox";
import { Badge } from "@/ui/badge";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/ui/tooltip";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/ui/form";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

// Form schema for editing purchases
const editPurchaseSchema = z.object({
	og_qty: z.coerce.number().optional(),
	final_qty: z.coerce.number().optional(),
	cancelled_qty: z.coerce.number().optional(),
	shipped_to_pw: z.coerce.number().optional(),
	arrived: z.coerce.number().optional(),
	checked_in: z.coerce.number().optional(),
	shipped_out: z.coerce.number().optional(),
	tracking: z.string().optional(),
	delivery_date: z.string().optional(),
	location: z.string().optional(),
	address: z.string().optional(),
	in_bound: z.boolean().optional(),
	outbound_name: z.string().optional(),
	fba_shipment: z.string().optional(),
	fba_msku: z.string().optional(),
	status: z.string().optional(),
	audited: z.boolean().optional(),
	notes: z.string().optional(),
});

type EditPurchaseFormValues = z.infer<typeof editPurchaseSchema>;

/** Format ISO datetime string (date + time) for display. Only shows time when a real time exists (not midnight). */
function formatDateTime(dateStr: string | null | undefined): { date: string; time: string } {
	if (!dateStr) return { date: "-", time: "" };
	const raw = dateStr.trim();
	// Date-only (no T) or midnight = no real time, don't show to avoid timezone artifacts (e.g. 7:00 AM in UTC+7)
	const hasRealTime = raw.includes("T") && !/T00:00(:00)?(\.0+)?Z?$/i.test(raw);
	if (!hasRealTime) {
		const [y, m, d] = raw.split("T")[0].split("-").map(Number);
		const date = new Date(y, m - 1, d);
		return {
			date: date.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" }),
			time: "",
		};
	}
	// Has real time - parse as UTC and convert to local
	const iso = raw.endsWith("Z") ? raw : raw + "Z";
	const date = new Date(iso);
	return {
		date: date.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" }),
		time: date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
	};
}

export default function PurchaseTracker() {
	const [purchaseData, setPurchaseData] = useState<PurchaseTrackerItem[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [processingOrders, setProcessingOrders] = useState(false);
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

	// Search filters
	const [searchOrderNumber, setSearchOrderNumber] = useState("");
	const [searchProductName, setSearchProductName] = useState("");
	const [searchAsin, setSearchAsin] = useState("");

	// Manual purchase dialog state
	const [showManualDialog, setShowManualDialog] = useState(false);
	const [manualFormData, setManualFormData] = useState<ManualPurchaseRequest>({
		unique_id: "",
		size: "",
		qty: 1,
		order_number: "",
	});
	const [isSubmittingManual, setIsSubmittingManual] = useState(false);
	const [createdPurchaseData, setCreatedPurchaseData] = useState<any>(null);

	// Detail drawer state
	const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
	const [selectedPurchase, setSelectedPurchase] = useState<PurchaseTrackerItem | null>(null);
	const [isEditMode, setIsEditMode] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	// Delete confirmation dialog state
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [deleteCount, setDeleteCount] = useState(0);

	// Initialize form
	const editForm = useForm<EditPurchaseFormValues>({
		resolver: zodResolver(editPurchaseSchema),
		defaultValues: {
			og_qty: undefined,
			final_qty: undefined,
			cancelled_qty: undefined,
			shipped_to_pw: 0,
			arrived: 0,
			checked_in: 0,
			shipped_out: 0,
			tracking: "",
			delivery_date: "",
			location: "",
			address: "",
			in_bound: false,
			outbound_name: "",
			fba_shipment: "",
			fba_msku: "",
			status: "",
			audited: false,
			notes: "",
		},
	});

	// Handle checkbox selection
	const handleSelectAll = (checked: boolean) => {
		if (checked) {
			const allIds = new Set(purchaseData.map((item) => item.id));
			setSelectedIds(allIds);
		} else {
			setSelectedIds(new Set());
		}
	};

	const handleSelectRow = (id: number, checked: boolean) => {
		const newSelectedIds = new Set(selectedIds);
		if (checked) {
			newSelectedIds.add(id);
		} else {
			newSelectedIds.delete(id);
		}
		setSelectedIds(newSelectedIds);
	};

	// Handle bulk delete confirmation
	const handleBulkDeleteConfirm = () => {
		if (selectedIds.size === 0) {
			toast.warning("No purchases selected");
			return;
		}
		setDeleteCount(selectedIds.size);
		setDeleteDialogOpen(true);
	};

	// Handle bulk delete
	const handleBulkDelete = async () => {
		if (selectedIds.size === 0) return;

		try {
			setLoading(true);
			const idsArray = Array.from(selectedIds);
			await purchaseTrackerService.bulkDeletePurchases(idsArray);

			toast.success(`Successfully deleted ${selectedIds.size} purchase(s)`);
			setSelectedIds(new Set());
			setDeleteDialogOpen(false);
			await loadPurchaseData();
		} catch (error: any) {
			console.error("Error deleting purchases:", error);
			toast.error("Failed to delete purchases", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Define columns for the purchase tracker table
	const columns: ColumnDef<PurchaseTrackerItem>[] = [
		{
			id: "select",
			header: () => {
				const allSelected = purchaseData.length > 0 && purchaseData.every((item) => selectedIds.has(item.id));
				return (
					<Checkbox
						checked={allSelected}
						onCheckedChange={handleSelectAll}
						aria-label="Select all"
					/>
				);
			},
			cell: ({ row }) => (
				<Checkbox
					checked={selectedIds.has(row.original.id)}
					onCheckedChange={(checked) => handleSelectRow(row.original.id, checked as boolean)}
					aria-label="Select row"
				/>
			),
			size: 30,
			minSize: 30,
			maxSize: 50,
		},
		{
			accessorKey: "created_at",
			header: "Created",
			size: 95,
			minSize: 80,
			maxSize: 130,
			cell: ({ row }) => {
				if (!row.original.created_at) {
					return <span className="text-gray-400 italic text-sm">—</span>;
				}
				const { date, time } = formatDateTime(row.original.created_at);
				return (
					<div className="flex flex-col text-xs leading-tight">
						<span className="text-gray-700 dark:text-gray-300 font-medium">{date}</span>
						{time && <span className="text-gray-500 dark:text-gray-500">{time}</span>}
					</div>
				);
			},
		},
		{
			accessorKey: "product_name",
			header: "Product",
			size: 280,
			minSize: 150,
			maxSize: 400,
			cell: ({ row }) => {
				const productName = row.original.product_name || "—";
				const retailer = row.original.supplier;
				return (
					<Tooltip>
						<TooltipTrigger asChild>
							<div className="max-w-full min-w-0 cursor-default flex flex-col gap-0.5">
								<div className="font-medium truncate">{productName}</div>
								{retailer && (
									<Badge variant="outline" className="w-fit text-xs font-normal">
										{retailer}
									</Badge>
								)}
							</div>
						</TooltipTrigger>
						<TooltipContent side="top" className="max-w-[400px] break-words">
							{productName}
							{retailer && (
								<>
									<br />
									<span className="text-muted-foreground text-xs">{retailer}</span>
								</>
							)}
						</TooltipContent>
					</Tooltip>
				);
			},
		},
		{
			accessorKey: "size",
			header: "Size",
			size: 60,
			minSize: 60,
			maxSize: 100,
			cell: ({ row }) => <div className="text-center">{row.original.size || "—"}</div>,
		},
		{
			accessorKey: "asin",
			header: "ASIN",
			size: 100,
			minSize: 100,
			maxSize: 150,
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.asin || "—"}
				</div>
			),
		},
		{
			id: "qty",
			header: "Org / Final",
			size: 100,
			minSize: 90,
			maxSize: 120,
			cell: ({ row }) => {
				const og = row.original.og_qty ?? "—";
				const final = row.original.final_qty ?? 0;
				return (
					<div className="text-center font-medium">
						<span title="Original Qty / Final Qty">{og} / {final}</span>
					</div>
				);
			},
		},
		{
			accessorKey: "ppu",
			header: "PPU",
			size: 60,
			minSize: 60,
			maxSize: 120,
			cell: ({ row }) => (
				<div className="text-right">
					{row.original.ppu ? `$${row.original.ppu.toFixed(2)}` : "—"}
				</div>
			),
		},
		{
			accessorKey: "total_spend",
			header: "Total",
			size: 90,
			minSize: 90,
			maxSize: 140,
			cell: ({ row }) => (
				<div className="text-right font-medium">
					{row.original.total_spend ? `$${row.original.total_spend.toFixed(2)}` : "—"}
				</div>
			),
		},
		{
			accessorKey: "order_number",
			header: "Order Number",
			size: 150,
			minSize: 140,
			maxSize: 220,
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.order_number || "—"}
				</div>
			),
		},
		{
			accessorKey: "lead_id",
			header: "Lead ID",
			size: 150,
			minSize: 130,
			maxSize: 180,
			cell: ({ row }) => (
				<div className="font-mono text-sm">
					{row.original.lead_id || "—"}
				</div>
			),
		},
		{
			accessorKey: "shipped_to_pw",
			header: "Shipped to PW",
			size: 100,
			minSize: 100,
			maxSize: 180,
			meta: {
				sticky: true,
			},
			cell: ({ row }) => {
				const value = row.original.shipped_to_pw || 0;
				return (
					<div className="text-center font-medium">
						<span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
							{value}
						</span>
					</div>
				);
			},
		},
		{
			accessorKey: "checked_in",
			header: "Checked In",
			size: 130,
			minSize: 120,
			maxSize: 160,
			meta: {
				sticky: true,
			},
			cell: ({ row }) => {
				const value = row.original.checked_in || 0;
				return (
					<div className="text-center font-medium">
						<span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
							{value}
						</span>
					</div>
				);
			},
		},
		{
			accessorKey: "shipped_out",
			header: "Shipped Out",
			size: 130,
			minSize: 120,
			maxSize: 160,
			meta: {
				sticky: true,
			},
			cell: ({ row }) => {
				const value = row.original.shipped_out || 0;
				return (
					<div className="text-center font-medium">
						<span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
							{value}
						</span>
					</div>
				);
			},
		},
		{
			accessorKey: "status",
			header: "Status",
			size: 120,
			minSize: 100,
			maxSize: 150,
			meta: {
				sticky: true,
			},
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
		{
			id: "actions",
			header: "Actions",
			size: 100,
			minSize: 90,
			maxSize: 120,
			meta: {
				sticky: true,
			},
			cell: ({ row }) => (
				<Button
					variant="ghost"
					size="sm"
					onClick={() => handleViewDetails(row.original)}
				>
					<Icon icon="mdi:eye" className="mr-1" />
					View
				</Button>
			),
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
				product_name: searchProductName || undefined,
				asin: searchAsin || undefined,
				order_number: searchOrderNumber || undefined,
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
			setSelectedIds(new Set()); // Clear selection when loading new data
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
		setSearchProductName("");
		setSearchAsin("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadPurchaseData(newPagination), 0);
	};

	// Handle view details
	const handleViewDetails = (purchase: PurchaseTrackerItem) => {
		setSelectedPurchase(purchase);
		setDetailDrawerOpen(true);
		setIsEditMode(false);
		
		// Populate form with current values
		editForm.reset({
			og_qty: purchase.og_qty || undefined,
			final_qty: purchase.final_qty || undefined,
			cancelled_qty: purchase.cancelled_qty || undefined,
			shipped_to_pw: purchase.shipped_to_pw ?? 0,
			arrived: purchase.arrived ?? 0,
			checked_in: purchase.checked_in ?? 0,
			shipped_out: purchase.shipped_out ?? 0,
			tracking: purchase.tracking || "",
			delivery_date: purchase.delivery_date || "",
			location: purchase.location || "",
			address: purchase.address || "",
			in_bound: purchase.in_bound || false,
			outbound_name: purchase.outbound_name || "",
			fba_shipment: purchase.fba_shipment || "",
			fba_msku: purchase.fba_msku || "",
			status: purchase.status || "",
			audited: purchase.audited || false,
			notes: purchase.notes || "",
		});
	};

	const handleEditToggle = () => {
		setIsEditMode(!isEditMode);
	};

	const handleSaveChanges = async (data: EditPurchaseFormValues) => {
		if (!selectedPurchase) return;

		try {
			setIsSaving(true);
			await purchaseTrackerService.updatePurchase(selectedPurchase.id, data);
			console.log("[handleSaveChanges] - data", data);
			
			// Fetch the updated purchase record to refresh the drawer
			const updatedPurchase = await purchaseTrackerService.getPurchaseById(selectedPurchase.id);
			console.log("[handleSaveChanges] - updatedPurchase", updatedPurchase);
			
			// Update the selected purchase state with fresh data
			setSelectedPurchase(updatedPurchase);
			
			// Update the form with fresh data
			editForm.reset({
				og_qty: updatedPurchase.og_qty || undefined,
				final_qty: updatedPurchase.final_qty || undefined,
				cancelled_qty: updatedPurchase.cancelled_qty || undefined,
				shipped_to_pw: updatedPurchase.shipped_to_pw ?? 0,
				arrived: updatedPurchase.arrived ?? 0,
				checked_in: updatedPurchase.checked_in ?? 0,
				shipped_out: updatedPurchase.shipped_out ?? 0,
				tracking: updatedPurchase.tracking || "",
				delivery_date: updatedPurchase.delivery_date || "",
				location: updatedPurchase.location || "",
				address: updatedPurchase.address || "",
				in_bound: updatedPurchase.in_bound || false,
				outbound_name: updatedPurchase.outbound_name || "",
				fba_shipment: updatedPurchase.fba_shipment || "",
				fba_msku: updatedPurchase.fba_msku || "",
				status: updatedPurchase.status || "",
				audited: updatedPurchase.audited || false,
				notes: updatedPurchase.notes || "",
			});
			
			toast.success("Purchase updated successfully");
			setIsEditMode(false);
			
			// Update the record in the current page's data if it exists
			setPurchaseData(prevData => 
				prevData.map(item => 
					item.id === selectedPurchase.id ? updatedPurchase : item
				)
			);
			
			// Refresh the list in the background to ensure consistency
			// This preserves the current pagination state
			loadPurchaseData();
		} catch (error) {
			console.error("Failed to update purchase:", error);
			toast.error("Failed to update purchase");
		} finally {
			setIsSaving(false);
		}
	};

	// Handle processing all retailer orders
	const handleProcessAllRetailerOrders = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing retailer orders...", {
				description: "Searching for order confirmation emails from all retailers",
			});

			const result = await retailerOrderService.processAllRetailerOrders(20);

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

	// Handle processing Footlocker shipping/cancellation updates
	const handleProcessFootlockerUpdates = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing Footlocker updates...", {
				description: "Searching for shipping and cancellation notification emails",
			});

			const result = await retailerOrderService.processFootlockerUpdates(10);

			const totalProcessed = result.processed || 0;
			const totalEmails = result.total_emails || 0;
			const errors = result.errors || 0;

			if (totalProcessed > 0) {
				toast.success(`Successfully processed ${totalProcessed} Footlocker updates!`, {
					description: "Purchase tracker records have been updated",
				});

				// Reload purchase data to show updates
				setTimeout(() => {
					loadPurchaseData();
				}, 2000);
			} else if (totalEmails === 0) {
				toast.info("No unprocessed Footlocker update emails found", {
					description: "All shipping/cancellation emails have been processed",
				});
			} else if (errors > 0) {
				toast.warning("No Footlocker updates were processed", {
					description: result.error_messages?.[0] || "Check the logs for details",
				});
			} else {
				toast.info("No new Footlocker updates to process", {
					description: "All available emails have been processed",
				});
			}
		} catch (error: any) {
			console.error("Error processing Footlocker updates:", error);
			
			const errorMessage = error?.response?.data?.message || 
								error?.response?.data?.detail ||
								error?.message || 
								"Failed to process Footlocker updates";
			
			toast.error("Failed to process Footlocker updates", {
				description: errorMessage,
			});
		} finally {
			setProcessingOrders(false);
		}
	};

	// Handle processing JD Sports shipping/cancellation updates
	const handleProcessJDSportsUpdates = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing JD Sports updates...", {
				description: "Searching for shipping and cancellation notification emails",
			});
			const result = await retailerOrderService.processJDSportsUpdates(10);
			const data = result;
			const totalProcessed = data.processed || 0;
			const totalEmails = data.total_emails || 0;
			const errors = data.errors || 0;
			if (totalProcessed > 0) {
				toast.success(`Successfully processed ${totalProcessed} JD Sports updates!`, {
					description: "Purchase tracker records have been updated",
				});
				setTimeout(() => loadPurchaseData(), 2000);
			} else if (totalEmails === 0) {
				toast.info("No unprocessed JD Sports update emails found", {
					description: "All shipping/cancellation emails have been processed",
				});
			} else if (errors > 0) {
				toast.warning("No JD Sports updates were processed", {
					description: data.error_messages?.[0] || "Check the logs for details",
				});
			} else {
				toast.info("No new JD Sports updates to process", {
					description: "All available emails have been processed",
				});
			}
		} catch (error: any) {
			const errorMessage = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Failed to process JD Sports updates";
			toast.error("Failed to process JD Sports updates", { description: errorMessage });
		} finally {
			setProcessingOrders(false);
		}
	};

	// Handle processing Finish Line shipping/cancellation updates
	const handleProcessFinishLineUpdates = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing Finish Line updates...", {
				description: "Searching for shipping and cancellation notification emails",
			});

			const result = await retailerOrderService.processFinishLineUpdates(10);
			const data = result;
			const totalProcessed = data.processed || 0;
			const totalEmails = data.total_emails || 0;
			const errors = data.errors || 0;

			if (totalProcessed > 0) {
				toast.success(`Successfully processed ${totalProcessed} Finish Line updates!`, {
					description: "Purchase tracker records have been updated",
				});
				setTimeout(() => loadPurchaseData(), 2000);
			} else if (totalEmails === 0) {
				toast.info("No unprocessed Finish Line update emails found", {
					description: "All shipping/cancellation emails have been processed",
				});
			} else if (errors > 0) {
				toast.warning("No Finish Line updates were processed", {
					description: data.error_messages?.[0] || "Check the logs for details",
				});
			} else {
				toast.info("No new Finish Line updates to process", {
					description: "All available emails have been processed",
				});
			}
		} catch (error: any) {
			const errorMessage = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Failed to process Finish Line updates";
			toast.error("Failed to process Finish Line updates", { description: errorMessage });
		} finally {
			setProcessingOrders(false);
		}
	};

	// Handle processing inbound creation
	const handleProcessInboundCreation = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing inbound creation...", {
				description: "This may take several minutes. Extracting records and automating PrepWorx login...",
				duration: 10000, // Show for 10 seconds
			});

			const result = await purchaseTrackerService.processInboundCreation();

			const data = result;
			const totalRecords = data.total_records || 0;
			const success = data.success || false;
			const processedByAddress = data.processed_by_address || {};

			if (success && totalRecords > 0) {
				const addressCount = Object.keys(processedByAddress).length;
				const description = `Processed ${totalRecords} records across ${addressCount} address(es)`;
				
				toast.success(`Inbound creation completed!`, {
					description: description,
					duration: 5000,
				});
			} else if (totalRecords === 0) {
				toast.info("No records found for inbound creation", {
					description: "No purchase records where final_qty = shipped_to_pw",
				});
			} else if (!success) {
				const errors = data.errors || [];
				toast.error("Inbound creation failed", {
					description: errors[0] || "Check the logs for details",
				});
			} else {
				toast.info("Inbound creation completed", {
					description: "All records have been processed",
				});
			}
		} catch (error: any) {
			console.error("Error processing inbound creation:", error);
			
			// Check if it's a timeout error
			if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
				toast.error("Request timeout", {
					description: "The operation is taking longer than expected. Please check the backend logs to see if it's still processing.",
					duration: 10000,
				});
			} else {
				const errorMessage = error?.response?.data?.message || 
									error?.response?.data?.detail ||
									error?.message || 
									"Failed to process inbound creation";
				
				toast.error("Failed to process inbound creation", {
					description: errorMessage,
				});
			}
		} finally {
			setProcessingOrders(false);
		}
	};

	// Handle processing outbound creation
	const handleProcessOutboundCreation = async () => {
		setProcessingOrders(true);
		try {
			toast.info("Processing outbound creation...", {
				description: "Generating Inventory Lab and Prepworx CSV files from checked-in records...",
				duration: 10000,
			});

			const result = await purchaseTrackerService.processOutboundCreation();

			const data = result;
			const success = data.success || false;
			const ilFile = data.il_file || {};
			const pwFile = data.pw_file || {};

			if (success && ilFile.success && pwFile.success) {
				// Both files generated successfully
				const description = `Generated ${ilFile.filename} (${data.total_asins} ASINs) and ${pwFile.filename} (${data.total_items} items) from ${data.total_records} records`;
				toast.success(`Outbound creation completed!`, {
					description: description,
					duration: 10000,
				});
			} else if (ilFile.success && !pwFile.success) {
				// IL file generated but PW file failed
				toast.warning(`IL file generated, but Prepworx file failed`, {
					description: `Generated ${ilFile.filename} with ${data.total_asins} ASINs. Error: ${pwFile.error || "Unknown error"}`,
					duration: 10000,
				});
			} else if (!ilFile.success) {
				// IL file generation failed
				const errorMsg = ilFile.error || "Check the logs for details";
				toast.error("Outbound creation failed", {
					description: `IL file generation failed: ${errorMsg}`,
				});
			} else {
				// Partial success or unknown state
				const errorMsg = data.error || "Check the logs for details";
				toast.error("Outbound creation failed", {
					description: errorMsg,
				});
			}
		} catch (error: any) {
			console.error("Error processing outbound creation:", error);
			
			const errorMessage = error?.response?.data?.message || 
								error?.response?.data?.detail ||
								error?.message || 
								"Failed to process outbound creation";
			
			toast.error("Failed to process outbound creation", {
				description: errorMessage,
			});
		} finally {
			setProcessingOrders(false);
		}
	};

	// Handle opening manual purchase dialog
	const handleOpenManualDialog = () => {
		setManualFormData({
			unique_id: "",
			size: "",
			qty: 1,
			order_number: "",
		});
		setCreatedPurchaseData(null);
		setShowManualDialog(true);
	};

	// Handle manual form submission
	const handleManualSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		
		// Validate form
		if (!manualFormData.unique_id || !manualFormData.size || !manualFormData.qty || !manualFormData.order_number) {
			toast.error("All fields are required", {
				description: "Please fill in all fields before submitting",
			});
			return;
		}

		setIsSubmittingManual(true);
		try {
			const result = await purchaseTrackerService.createManualPurchase(manualFormData);
			
			setCreatedPurchaseData(result);
			toast.success("Purchase created successfully!", {
				description: `Purchase tracker record created for ${result.product_name}`,
			});
			
			// Reload purchase data to show new entry
			setTimeout(() => {
				loadPurchaseData();
			}, 1000);
			
			// Close dialog after a short delay
			setTimeout(() => {
				setShowManualDialog(false);
			}, 2000);
		} catch (error: any) {
			console.error("Error creating manual purchase:", error);
			
			const errorMessage = error?.response?.data?.message || 
								error?.response?.data?.detail ||
								error?.message || 
								"Failed to create purchase";
			
			toast.error("Failed to create purchase", {
				description: errorMessage,
			});
		} finally {
			setIsSubmittingManual(false);
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
							placeholder="Order Number"
							value={searchOrderNumber}
							onChange={(e) => setSearchOrderNumber(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSearch();
							}}
						/>
						<Input
							placeholder="Product Name"
							value={searchProductName}
							onChange={(e) => setSearchProductName(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSearch();
							}}
						/>
						<Input
							placeholder="ASIN"
							value={searchAsin}
							onChange={(e) => setSearchAsin(e.target.value)}
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
						{/* Main Process Buttons - Wrap on smaller screens */}
						<div className="flex flex-wrap gap-2">
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
								onClick={handleProcessFootlockerUpdates}
								variant="default"
								className="bg-orange-600 hover:bg-orange-700"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:truck-delivery" className="mr-2" />
								Process Footlocker Updates
							</Button>
							<Button
								onClick={handleProcessFinishLineUpdates}
								variant="default"
								className="bg-teal-600 hover:bg-teal-700"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:truck-delivery" className="mr-2" />
								Process Finish Line Updates
							</Button>
							<Button
								onClick={handleProcessJDSportsUpdates}
								variant="default"
								className="bg-emerald-600 hover:bg-emerald-700"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:truck-delivery" className="mr-2" />
								Process JD Sports Updates
							</Button>
							<Button
								onClick={handleProcessInboundCreation}
								variant="default"
								className="bg-purple-600 hover:bg-purple-700"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:package-variant-closed-check" className="mr-2" />
								Process Inbound Creation
							</Button>
							<Button
								onClick={handleProcessOutboundCreation}
								variant="default"
								className="bg-blue-600 hover:bg-blue-700"
								disabled={processingOrders || loading}
							>
								<Icon icon="mdi:package-variant" className="mr-2" />
								Process Outbound Creation
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
					<CardAction className="flex gap-2">
						{selectedIds.size > 0 && (
							<Button
								size="sm"
								variant="destructive"
								onClick={handleBulkDeleteConfirm}
								disabled={loading}
							>
								<Icon icon="mdi:delete" className="mr-1" />
								Delete ({selectedIds.size})
							</Button>
						)}
						<Button
							size="sm"
							onClick={handleOpenManualDialog}
							variant="default"
							className="bg-green-600 hover:bg-green-700"
							disabled={loading}
						>
							<Icon icon="mdi:plus" className="mr-1" />
							Add Purchase
						</Button>
						<Button 
							size="sm"
							onClick={() => loadPurchaseData()} 
							variant="outline"
							disabled={loading}
						>
							<Icon icon="mdi:refresh" className="mr-1" />
							Refresh
						</Button>
					</CardAction>
				</CardHeader>
				<CardContent>
					{/* {!loading && purchaseData.length === 0 ? (
						<div className="flex flex-col items-center justify-center py-12 text-center">
							<Icon icon="mdi:package-variant-closed" className="text-4xl text-muted-foreground mb-4" />
							<h3 className="text-lg font-semibold mb-2">No Purchase Records Found</h3>
							<p className="text-muted-foreground mb-4">
								No purchase records found. Process retailer orders to create purchase records.
							</p>
						</div>
					) : ( */}
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
					{/* )} */}
				</CardContent>
			</Card>

			{/* Detail Drawer/Sidebar */}
			<Sheet open={detailDrawerOpen} onOpenChange={setDetailDrawerOpen}>
				<SheetContent className="w-full sm:max-w-2xl overflow-y-auto gap-0">
					<SheetHeader>
						<SheetTitle>
							Purchase Details
							{selectedPurchase && (
								<span className="text-sm font-normal text-muted-foreground ml-2">
									Order: {selectedPurchase.order_number}
								</span>
							)}
						</SheetTitle>
					</SheetHeader>

					{selectedPurchase && (
						<div className="mt-2 p-3">
							<Tabs defaultValue="basic" className="w-full">
								<TabsList className="grid w-full grid-cols-4">
									<TabsTrigger value="basic">Basic</TabsTrigger>
									<TabsTrigger value="fulfillment">Fulfillment</TabsTrigger>
									<TabsTrigger value="fba">FBA</TabsTrigger>
									<TabsTrigger value="pricing">Pricing</TabsTrigger>
								</TabsList>

								{/* Basic Info Tab */}
								<TabsContent value="basic" className="space-y-4 mt-4">
									<div className="space-y-3 bg-muted p-4 rounded-lg">
										<h4 className="font-semibold text-sm">Product Information</h4>
										<div className="grid grid-cols-2 gap-3 text-sm">
											<div>
												<span className="text-muted-foreground">Created:</span>
												<p className="font-medium">
												{selectedPurchase.created_at ? (() => {
													const { date, time } = formatDateTime(selectedPurchase.created_at);
													return (
														<>
															{date}
															{time && (
																<span className="text-muted-foreground ml-1">{time}</span>
															)}
														</>
													);
												})() : "-"}
											</p>
											</div>
											<div>
												<span className="text-muted-foreground">Lead ID:</span>
												<p className="font-medium">{selectedPurchase.lead_id || "-"}</p>
											</div>
											<div>
												<span className="text-muted-foreground">Order #:</span>
												<p className="font-medium">{selectedPurchase.order_number || "-"}</p>
											</div>
											<div>
												<span className="text-muted-foreground">Platform:</span>
												<p className="font-medium">{selectedPurchase.platform || "-"}</p>
											</div>
											<div className="col-span-2">
												<span className="text-muted-foreground">Product:</span>
												<p className="font-medium">{selectedPurchase.product_name || "-"}</p>
											</div>
											<div>
												<span className="text-muted-foreground">Size:</span>
												<p className="font-medium">{selectedPurchase.size || "-"}</p>
											</div>
											<div>
												<span className="text-muted-foreground">ASIN:</span>
												<p className="font-medium">{selectedPurchase.asin || "-"}</p>
											</div>
										</div>
									</div>

									<Form {...editForm}>
										<form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-4">
											<Separator />
											<h4 className="font-semibold text-sm">Quantities</h4>
											<div className="grid grid-cols-3 gap-4">
												<FormField
													control={editForm.control}
													name="og_qty"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Original Qty</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
												<FormField
													control={editForm.control}
													name="final_qty"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Final Qty</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
												<FormField
													control={editForm.control}
													name="cancelled_qty"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Cancelled Qty</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
											</div>

											<Separator />
											<h4 className="font-semibold text-sm">Status & Notes</h4>
											<FormField
												control={editForm.control}
												name="status"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Status</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="audited"
												render={({ field }) => (
													<FormItem className="flex items-center gap-2 space-y-0">
														<FormControl>
															<Checkbox
																checked={field.value}
																onCheckedChange={field.onChange}
																disabled={!isEditMode}
															/>
														</FormControl>
														<FormLabel className="!mt-0">Audited</FormLabel>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="notes"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Notes</FormLabel>
														<FormControl>
															<Textarea {...field} rows={3} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Action Buttons */}
											<div className="flex gap-2 pt-4 justify-center">
												{!isEditMode ? (
													<Button type="button" onClick={handleEditToggle} className="w-1/2">
														<Icon icon="mdi:pencil" className="mr-2" />
														Edit
													</Button>
												) : (
													<>
														<Button type="button" variant="outline" onClick={handleEditToggle} className="flex-1">
															Cancel
														</Button>
														<Button type="submit" disabled={isSaving} className="flex-1">
															{isSaving ? "Saving..." : "Save Changes"}
														</Button>
													</>
												)}
											</div>
										</form>
									</Form>
								</TabsContent>

								{/* Fulfillment Tab */}
								<TabsContent value="fulfillment" className="space-y-4 mt-4">
									<Form {...editForm}>
										<form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-4">
											<h4 className="font-semibold text-sm">Fulfillment Stages (Numbers)</h4>
											<div className="grid grid-cols-2 gap-4">
												<FormField
													control={editForm.control}
													name="shipped_to_pw"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Shipped to PW</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
												<FormField
													control={editForm.control}
													name="arrived"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Arrived</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
												<FormField
													control={editForm.control}
													name="checked_in"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Checked In</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
												<FormField
													control={editForm.control}
													name="shipped_out"
													render={({ field }) => (
														<FormItem>
															<FormLabel>Shipped Out</FormLabel>
															<FormControl>
																<Input {...field} type="number" disabled={!isEditMode} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
											</div>

											<Separator />
											<h4 className="font-semibold text-sm">Shipping Information</h4>
											<FormField
												control={editForm.control}
												name="tracking"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Tracking Number #</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="delivery_date"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Delivery Date</FormLabel>
														<FormControl>
															<Input {...field} type="date" disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="location"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Location</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="address"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Address</FormLabel>
														<FormControl>
															<Textarea {...field} rows={2} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="in_bound"
												render={({ field }) => (
													<FormItem className="flex items-center gap-2 space-y-0">
														<FormControl>
															<Checkbox
																checked={field.value}
																onCheckedChange={field.onChange}
																disabled={!isEditMode}
															/>
														</FormControl>
														<FormLabel className="!mt-0">Inbound</FormLabel>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Action Buttons */}
											<div className="flex gap-2 pt-4 justify-center">
												{!isEditMode ? (
													<Button type="button" onClick={handleEditToggle} className="w-1/2">
														<Icon icon="mdi:pencil" className="mr-2" />
														Edit
													</Button>
												) : (
													<>
														<Button type="button" variant="outline" onClick={handleEditToggle} className="flex-1">
															Cancel
														</Button>
														<Button type="submit" disabled={isSaving} className="flex-1">
															{isSaving ? "Saving..." : "Save Changes"}
														</Button>
													</>
												)}
											</div>
										</form>
									</Form>
								</TabsContent>

								{/* FBA Tab */}
								<TabsContent value="fba" className="space-y-4 mt-4">
									<Form {...editForm}>
										<form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-4">
											<h4 className="font-semibold text-sm">FBA Information</h4>
											<FormField
												control={editForm.control}
												name="outbound_name"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Outbound Name</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="fba_shipment"
												render={({ field }) => (
													<FormItem>
														<FormLabel>FBA Shipment</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
											<FormField
												control={editForm.control}
												name="fba_msku"
												render={({ field }) => (
													<FormItem>
														<FormLabel>FBA MSKU</FormLabel>
														<FormControl>
															<Input {...field} disabled={!isEditMode} />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											{/* Action Buttons */}
											<div className="flex gap-2 pt-4 justify-center">
												{!isEditMode ? (
													<Button type="button" onClick={handleEditToggle} className="w-1/2">
														<Icon icon="mdi:pencil" className="mr-2" />
														Edit
													</Button>
												) : (
													<>
														<Button type="button" variant="outline" onClick={handleEditToggle} className="flex-1">
															Cancel
														</Button>
														<Button type="submit" disabled={isSaving} className="flex-1">
															{isSaving ? "Saving..." : "Save Changes"}
														</Button>
													</>
												)}
											</div>
										</form>
									</Form>
								</TabsContent>

								{/* Pricing Tab */}
								<TabsContent value="pricing" className="space-y-4 mt-4">
									<div className="space-y-3 bg-muted p-4 rounded-lg">
										<h4 className="font-semibold text-sm">Pricing Information (Read-Only)</h4>
										<div className="grid grid-cols-2 gap-3 text-sm">
											<div>
												<span className="text-muted-foreground">PPU:</span>
												<p className="font-medium">${selectedPurchase.ppu?.toFixed(2) || "0.00"}</p>
											</div>
											<div>
												<span className="text-muted-foreground">Total Spend:</span>
												<p className="font-medium">${selectedPurchase.total_spend?.toFixed(2) || "0.00"}</p>
											</div>
										</div>
									</div>
								</TabsContent>
							</Tabs>
						</div>
					)}
				</SheetContent>
			</Sheet>

			{/* Manual Purchase Dialog */}
			<Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
				<DialogContent className="sm:max-w-[500px]">
					<DialogHeader>
						<DialogTitle>Add Manual Purchase</DialogTitle>
						<DialogDescription>
							Create a purchase tracker record by providing the unique ID, size, quantity, and order number.
						</DialogDescription>
					</DialogHeader>
					
					{!createdPurchaseData ? (
						<form onSubmit={handleManualSubmit}>
							<div className="grid gap-4 py-4">
								<div className="grid gap-2">
									<Label htmlFor="unique_id">
										Unique ID <span className="text-red-500">*</span>
									</Label>
									<Input
										id="unique_id"
										placeholder="e.g., HJ7395"
										value={manualFormData.unique_id}
										onChange={(e) => setManualFormData({...manualFormData, unique_id: e.target.value})}
										required
									/>
									<p className="text-xs text-muted-foreground">
										The product unique ID from OA Sourcing table
									</p>
								</div>
								
								<div className="grid gap-2">
									<Label htmlFor="size">
										Size <span className="text-red-500">*</span>
									</Label>
									<Input
										id="size"
										placeholder="e.g., 10, 9.5"
										value={manualFormData.size}
										onChange={(e) => setManualFormData({...manualFormData, size: e.target.value})}
										required
									/>
								</div>
								
								<div className="grid gap-2">
									<Label htmlFor="qty">
										Quantity <span className="text-red-500">*</span>
									</Label>
									<Input
										id="qty"
										type="number"
										min="1"
										placeholder="1"
										value={manualFormData.qty}
										onChange={(e) => setManualFormData({...manualFormData, qty: parseInt(e.target.value) || 1})}
										required
									/>
								</div>
								
								<div className="grid gap-2">
									<Label htmlFor="order_number">
										Order Number <span className="text-red-500">*</span>
									</Label>
									<Input
										id="order_number"
										placeholder="e.g., P7382827751142612992"
										value={manualFormData.order_number}
										onChange={(e) => setManualFormData({...manualFormData, order_number: e.target.value})}
										required
									/>
								</div>
							</div>
							
							<DialogFooter>
								<Button 
									type="button" 
									variant="outline" 
									onClick={() => setShowManualDialog(false)}
									disabled={isSubmittingManual}
								>
									Cancel
								</Button>
								<Button 
									type="submit" 
									disabled={isSubmittingManual}
								>
									{isSubmittingManual ? "Creating..." : "Create Purchase"}
								</Button>
							</DialogFooter>
						</form>
					) : (
						<div className="py-6">
							<div className="flex items-center justify-center mb-4">
								<Icon icon="mdi:check-circle" className="text-5xl text-green-500" />
							</div>
							<h3 className="text-center text-lg font-semibold mb-4">
								Purchase Created Successfully!
							</h3>
							<div className="bg-muted p-4 rounded-lg space-y-2 text-sm">
								<div className="flex justify-between">
									<span className="text-muted-foreground">Product:</span>
									<span className="font-medium">{createdPurchaseData.product_name || "N/A"}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-muted-foreground">Size:</span>
									<span className="font-medium">{createdPurchaseData.size || "N/A"}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-muted-foreground">Quantity:</span>
									<span className="font-medium">{createdPurchaseData.final_qty || "N/A"}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-muted-foreground">Order #:</span>
									<span className="font-medium font-mono text-xs">{createdPurchaseData.order_number || "N/A"}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-muted-foreground">ASIN:</span>
									<span className="font-medium">{createdPurchaseData.asin || "N/A"}</span>
								</div>
							</div>
							<p className="text-center text-sm text-muted-foreground mt-4">
								Closing automatically...
							</p>
						</div>
					)}
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Are you sure?</DialogTitle>
						<DialogDescription>
							This will permanently delete{" "}
							<span className="font-semibold text-foreground">{deleteCount}</span> purchase
							{deleteCount !== 1 ? "s" : ""}. This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleBulkDelete} variant="destructive" disabled={loading}>
							{loading ? "Deleting..." : "Delete"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

