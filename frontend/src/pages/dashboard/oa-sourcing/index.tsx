import { Button } from "@/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Textarea } from "@/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/ui/form";
import { Title } from "@/ui/typography";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import Icon from "@/components/icon/icon";
import { DataTable } from "@/components/data-table/data-table";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
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
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/ui/tabs";
import { Badge } from "@/ui/badge";
import { Separator } from "@/ui/separator";
import { Checkbox } from "@/ui/checkbox";
import leadService, { type Lead } from "@/api/services/leadService";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { MultiSelect } from "@/ui/multi-select";

// Dropdown options - same as lead submittal
const prosOptions = [
	{ value: "extremely_strong_movement", label: "Extremely Strong Movement" },
	{ value: "strong_movement", label: "Strong Movement" },
	{ value: "average_movement", label: "Average Movement" },
	{ value: "extremely_high_margin", label: "Extremely High Margin" },
	{ value: "high_margin", label: "High Margin" },
	{ value: "average_margin", label: "Average Margin" },
	{ value: "low_sales_ranking", label: "Low Sales Ranking" },
	{ value: "average_sales_ranking", label: "Average Sales Ranking" },
	{ value: "downward_push_on_offer_count", label: "Downward Push on Offer Count" },
	{ value: "strong_reviews", label: "Strong Reviews" },
	{ value: "average_reviews", label: "Average Reviews" },
	{ value: "strong_ratings", label: "Strong Ratings" },
	{ value: "average_ratings", label: "Average Ratings" },
	{ value: "upward_buy_box_trend", label: "Upward Buy Box Trend" },
	{ value: "stable_buy_box", label: "Stable Buy Box" },
	{ value: "low_offer_count", label: "Low Offer Count" },
	{ value: "average_offer_count", label: "Average Offer Count" },
	{ value: "extremely_high_volume", label: "Extremely High Volume" },
	{ value: "high_volume", label: "High Volume" },
	{ value: "average_volume", label: "Average Volume" },
	{ value: "room_to_undercut_from_current_pricing", label: "Room to undercut from current pricing" },
	{ value: "proven_listing", label: "Proven Listing" },
	{ value: "full_size_listing", label: "Full Size Listing" },
	{ value: "previously_sold_this_model", label: "Previously Sold This Model" },
	{ value: "popular_color_sizes", label: "Popular Color/Sizes" },
];

const consOptions = [
	{ value: "extremely_slow_movement", label: "Extremely Slow Movement" },
	{ value: "slow_movement", label: "Slow Movement" },
	{ value: "extremely_thin_margin", label: "Extremely Thin Margin" },
	{ value: "thin_margin", label: "Thin Margin" },
	{ value: "high_sales_ranking", label: "High Sales Ranking" },
	{ value: "history_of_listing_separation", label: "History of Listing Separation" },
	{ value: "higher_sales_ranking", label: "Higher Sales Ranking" },
	{ value: "upward_push_on_offer_count", label: "Upward Push on Offer Count" },
	{ value: "little_to_none_reviews", label: "Little to None Reviews" },
	{ value: "weak_reviews", label: "Weak Reviews" },
	{ value: "little_to_none_ratings", label: "Little to None Ratings" },
	{ value: "weak_ratings", label: "Weak Ratings" },
	{ value: "downward_buy_box_trend", label: "Downward Buy Box Trend" },
	{ value: "extreme_buy_box_variance", label: "Extreme Buy Box Variance" },
	{ value: "strong_buy_box_variance", label: "Strong Buy Box Variance" },
	{ value: "unproven_listing", label: "Unproven Listing" },
	{ value: "partial_sizes_on_listing", label: "Partial Sizes on Listing" },
	{ value: "unpopular_sizes_color", label: "Unpopular Sizes/Color" },
];

// Form schema for editing leads
const editLeadSchema = z.object({
	productName: z.string().optional(),
	retailerLink: z.string().url("Please enter a valid URL").or(z.string().length(0)).optional(),
	amazonLink: z.string().url("Please enter a valid URL").or(z.string().length(0)).optional(),
	purchased: z.string().optional(),
	purchaseMoreIfAvailable: z.string().optional(),
	monitored: z.boolean().optional(),
	pros: z.array(z.string()).optional(),
	cons: z.array(z.string()).optional(),
	otherNotesConcerns: z.string().optional(),
	headOfProductReviewNotes: z.string().optional(),
	feedbackAndNotesOnQuantity: z.string().optional(),
	pairsPerLeadId: z.string().optional(),
	pairsPerSku: z.string().optional(),
	salesRank: z.string().optional(),
	asin1BuyBox: z.string().optional(),
	asin1NewPrice: z.string().optional(),
	pickPackFee: z.string().optional(),
	referralFee: z.string().optional(),
	totalFee: z.string().optional(),
	promoCode: z.string().optional(),
});

type EditLeadFormValues = z.infer<typeof editLeadSchema>;

export default function OASourcing() {
	const [leadData, setLeadData] = useState<Lead[]>([]);
	const [loading, setLoading] = useState(false);
	const [total, setTotal] = useState(0);
	const [searchRetailer, setSearchRetailer] = useState("");
	const [searchSourcer, setSearchSourcer] = useState("");
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	
	// Delete confirmation dialog
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null);
	
	// Detail drawer
	const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
	const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
	const [isEditMode, setIsEditMode] = useState(false);
	const [isSaving, setIsSaving] = useState(false);

	// Initialize form
	const editForm = useForm<EditLeadFormValues>({
		resolver: zodResolver(editLeadSchema),
		defaultValues: {
			productName: "",
			retailerLink: "",
			amazonLink: "",
			purchased: "",
			purchaseMoreIfAvailable: "",
			monitored: false,
			pros: [],
			cons: [],
			otherNotesConcerns: "",
			headOfProductReviewNotes: "",
			feedbackAndNotesOnQuantity: "",
			pairsPerLeadId: "",
			pairsPerSku: "",
			salesRank: "",
			asin1BuyBox: "",
			asin1NewPrice: "",
			pickPackFee: "",
			referralFee: "",
			totalFee: "",
			promoCode: "",
		},
	});

	// Define table columns - showing only key columns
	const columns = useMemo<ColumnDef<Lead>[]>(
		() => [
			{
				accessorKey: "id",
				header: "No",
				size: 60,
				minSize: 50,
				maxSize: 80,
				cell: ({ row }) => {
					const index = pagination.pageIndex * pagination.pageSize + row.index + 1;
					return <span className="font-medium text-sm">{index}</span>;
				},
			},
			{
				accessorKey: "lead_id",
				header: "Lead ID",
				size: 180,
				minSize: 150,
				cell: ({ row }) => (
					<button
						onClick={() => handleViewDetails(row.original)}
						className="font-mono text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2 py-1 rounded hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
					>
						{row.original.lead_id}
					</button>
				),
			},
		{
			accessorKey: "product_name",
			header: "Product Name",
			size: 320,
			minSize: 250,
			cell: ({ row }) => (
				<div className="flex items-center gap-2">
					<span className="font-medium text-sm truncate flex-1">{row.original.product_name}</span>
					<div className="flex items-center gap-1 flex-shrink-0">
						{row.original.retailer_link && (
							<a
								href={row.original.retailer_link}
								target="_blank"
								rel="noopener noreferrer"
								className="h-6 w-6 flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
								title="Open Retailer Link"
								onClick={(e) => e.stopPropagation()}
							>
								<Icon icon="mdi:store" size={14} className="text-blue-600 dark:text-blue-400" />
							</a>
						)}
						{row.original.amazon_link && (
							<a
								href={row.original.amazon_link}
								target="_blank"
								rel="noopener noreferrer"
								className="h-6 w-6 flex items-center justify-center rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
								title="Open Amazon Link"
								onClick={(e) => e.stopPropagation()}
							>
								<Icon icon="mdi:amazon" size={14} className="text-orange-600 dark:text-orange-400" />
							</a>
						)}
					</div>
				</div>
			),
		},
		{
			accessorKey: "retailer_name",
			header: "Retailer",
			size: 150,
			minSize: 120,
			cell: ({ row }) => <span className="capitalize text-sm">{row.original.retailer_name}</span>,
		},
		{
			accessorKey: "product_sku",
			header: "SKU",
			size: 160,
			minSize: 130,
			cell: ({ row }) => (
				<span className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
					{row.original.product_sku}
				</span>
			),
		},
		{
			accessorKey: "unique_id",
			header: "Unique ID",
			size: 180,
			minSize: 150,
			cell: ({ row }) =>
				row.original.unique_id ? (
					<span className="font-mono text-xs bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 px-2 py-1 rounded">
						{row.original.unique_id}
					</span>
				) : (
					<span className="text-gray-400 italic text-sm">N/A</span>
				),
		},
		{
			accessorKey: "ppu",
			header: "PPU",
			size: 120,
			minSize: 100,
			cell: ({ row }) =>
				row.original.ppu ? (
					<span className="font-semibold text-green-600 dark:text-green-400 text-sm">
						${row.original.ppu.toFixed(2)}
					</span>
				) : (
					<span className="text-gray-400 italic text-sm">N/A</span>
				),
		},
		{
			accessorKey: "rsp",
			header: "RSP",
			size: 120,
			minSize: 100,
			cell: ({ row }) =>
				row.original.rsp ? (
					<span className="font-semibold text-blue-600 dark:text-blue-400 text-sm">
						${row.original.rsp.toFixed(2)}
					</span>
				) : (
					<span className="text-gray-400 italic text-sm">N/A</span>
				),
		},
		{
			accessorKey: "margin",
			header: "Margin",
			size: 120,
			minSize: 100,
			cell: ({ row }) =>
				row.original.margin ? (
					<span className="font-semibold text-purple-600 dark:text-purple-400 text-sm">
						{row.original.margin.toFixed(1)}%
					</span>
				) : (
					<span className="text-gray-400 italic text-sm">N/A</span>
				),
		},
		{
			accessorKey: "sourcer",
			header: "Sourcer",
			size: 140,
			minSize: 110,
			cell: ({ row }) => (
				<Badge variant="secondary" className="text-xs">
					{row.original.sourcer}
				</Badge>
			),
		},
		{
			accessorKey: "timestamp",
			header: "Date & Time",
			size: 140,
			minSize: 120,
			cell: ({ row }) => {
				if (!row.original.timestamp) {
					return <span className="text-gray-400 italic text-xs">N/A</span>;
				}
				const date = new Date(row.original.timestamp);
				const dateStr = date.toLocaleDateString('en-US', { 
					month: 'short', 
					day: 'numeric',
					year: 'numeric'
				});
				const timeStr = date.toLocaleTimeString('en-US', { 
					hour: '2-digit', 
					minute: '2-digit',
					hour12: true 
				});
				return (
					<div className="flex flex-col text-xs leading-tight">
						<span className="text-gray-700 dark:text-gray-300 font-medium">{dateStr}</span>
						<span className="text-gray-500 dark:text-gray-500">{timeStr}</span>
					</div>
				);
			},
		},
		{
			id: "actions",
			header: "Actions",
			size: 160,
			minSize: 130,
				cell: ({ row }) => (
					<div className="flex items-center gap-1">
					<Button
						size="sm"
						variant="ghost"
						onClick={() => handleViewDetails(row.original)}
						className="h-8 w-8 p-0 hover:bg-blue-50 dark:hover:bg-blue-900/20"
						title="View Details"
					>
						<Icon icon="mdi:eye" size={16} className="text-blue-600 dark:text-blue-400" />
					</Button>
					<Button
						size="sm"
						variant="ghost"
						onClick={() => handleDeleteConfirm(row.original)}
						className="h-8 w-8 p-0 hover:bg-red-50 dark:hover:bg-red-900/20"
						title="Delete"
					>
						<Icon icon="mdi:delete" size={16} className="text-red-600 dark:text-red-400" />
					</Button>
					</div>
				),
			},
		],
		[pagination.pageIndex, pagination.pageSize]
	);

	// Load lead data from backend
	const loadLeadData = async (newPagination?: PaginationState) => {
		setLoading(true);
		const currentPagination = newPagination || pagination;

		try {
			const params = {
				skip: currentPagination.pageIndex * currentPagination.pageSize,
				limit: currentPagination.pageSize,
				retailer: searchRetailer || undefined,
				sourcer: searchSourcer || undefined,
			};

			const response = await leadService.getLeads(params);
			
			setLeadData(response.items);
			setTotal(response.total);
		} catch (error: any) {
			console.error("Error loading lead data:", error);
			toast.error("Failed to load lead data", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Load data on component mount
	useEffect(() => {
		loadLeadData();
	}, []);

	// Handle pagination change
	const handlePaginationChange = (newPagination: PaginationState) => {
		setPagination(newPagination);
		loadLeadData(newPagination);
	};

	// Handle search
	const handleSearch = () => {
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		loadLeadData(newPagination);
	};

	// Handle clear filters
	const handleClearFilters = () => {
		setSearchRetailer("");
		setSearchSourcer("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadLeadData(newPagination), 0);
	};

	// Handle view details
	const handleViewDetails = (lead: Lead) => {
		setSelectedLead(lead);
		setIsEditMode(false);
		setDetailDrawerOpen(true);
	};

	// Populate form with lead data
	const populateEditForm = (lead: Lead) => {
		// Parse comma-separated strings into arrays for pros/cons
		const prosArray = lead.pros ? lead.pros.split(',').map(p => p.trim()).filter(p => p) : [];
		const consArray = lead.cons ? lead.cons.split(',').map(c => c.trim()).filter(c => c) : [];
		
		editForm.reset({
			productName: lead.product_name || "",
			retailerLink: lead.retailer_link || "",
			amazonLink: lead.amazon_link || "",
			purchased: lead.purchased || "",
			purchaseMoreIfAvailable: lead.purchase_more || "",
			monitored: lead.monitored === "Yes" || lead.monitored === "true",
			pros: prosArray,
			cons: consArray,
			otherNotesConcerns: lead.other_notes || "",
			headOfProductReviewNotes: lead.head_review || "",
			feedbackAndNotesOnQuantity: lead.feedback_qty || "",
			pairsPerLeadId: lead.pairs_per_lead?.toString() || "",
			pairsPerSku: lead.pairs_per_sku?.toString() || "",
			salesRank: lead.sales_rank || "",
			asin1BuyBox: lead.buy_box || "",
			asin1NewPrice: lead.new_price || "",
			pickPackFee: lead.pick_pack_fee?.toString() || "",
			referralFee: lead.referral_fee?.toString() || "",
			totalFee: lead.total_fee?.toString() || "",
			promoCode: lead.promo_code || "",
		});
	};

	// Enter edit mode from detail view
	const enterEditMode = () => {
		if (selectedLead) {
			setIsEditMode(true);
			populateEditForm(selectedLead);
		}
	};

	// Cancel edit mode
	const cancelEditMode = () => {
		setIsEditMode(false);
		editForm.reset();
	};

	// Save edited lead
	const handleSaveLead = async (data: EditLeadFormValues) => {
		if (!selectedLead) return;

		setIsSaving(true);
		try {
			// Convert form data to API format
			const updateData: any = {};
			
			if (data.productName) updateData.productName = data.productName;
			if (data.retailerLink !== undefined) updateData.retailerLink = data.retailerLink;
			if (data.amazonLink !== undefined) updateData.amazonLink = data.amazonLink;
			if (data.purchased) updateData.purchased = data.purchased;
			if (data.purchaseMoreIfAvailable) updateData.purchaseMoreIfAvailable = data.purchaseMoreIfAvailable;
			if (data.monitored !== undefined) updateData.monitored = data.monitored;
			// Join arrays into comma-separated strings for backend
			if (data.pros !== undefined) updateData.pros = data.pros.join(", ");
			if (data.cons !== undefined) updateData.cons = data.cons.join(", ");
			if (data.otherNotesConcerns !== undefined) updateData.otherNotesConcerns = data.otherNotesConcerns;
			if (data.headOfProductReviewNotes !== undefined) updateData.headOfProductReviewNotes = data.headOfProductReviewNotes;
			if (data.feedbackAndNotesOnQuantity !== undefined) updateData.feedbackAndNotesOnQuantity = data.feedbackAndNotesOnQuantity;
			if (data.pairsPerLeadId) updateData.pairsPerLeadId = parseInt(data.pairsPerLeadId);
			if (data.pairsPerSku) updateData.pairsPerSku = parseInt(data.pairsPerSku);
			if (data.salesRank !== undefined) updateData.salesRank = data.salesRank;
			if (data.asin1BuyBox) updateData.asin1BuyBox = parseFloat(data.asin1BuyBox);
			if (data.asin1NewPrice) updateData.asin1NewPrice = parseFloat(data.asin1NewPrice);
			if (data.pickPackFee) updateData.pickPackFee = parseFloat(data.pickPackFee);
			if (data.referralFee) updateData.referralFee = parseFloat(data.referralFee);
			if (data.totalFee) updateData.totalFee = parseFloat(data.totalFee);
			if (data.promoCode !== undefined) updateData.promoCode = data.promoCode;

			// Call API
			await leadService.updateLead(selectedLead.lead_id, updateData);

			toast.success("Lead updated successfully", {
				description: `${selectedLead.lead_id} has been updated`,
			});

			// Exit edit mode
			setIsEditMode(false);

			// Refresh the lead data
			await loadLeadData();

			// Close drawer
			setDetailDrawerOpen(false);
		} catch (error: any) {
			console.error("Error updating lead:", error);
			toast.error("Failed to update lead", {
				description: error?.message || "Please try again",
			});
		} finally {
			setIsSaving(false);
		}
	};

	// Handle delete confirmation
	const handleDeleteConfirm = (lead: Lead) => {
		setLeadToDelete(lead);
		setDeleteDialogOpen(true);
	};

	// Handle delete
	const handleDelete = async () => {
		if (!leadToDelete) return;

		try {
			await leadService.deleteLead(leadToDelete.lead_id);
			
			toast.success(`Lead ${leadToDelete.lead_id} deleted successfully`);
			setDeleteDialogOpen(false);
			setLeadToDelete(null);
			loadLeadData(); // Reload data
		} catch (error: any) {
			console.error("Error deleting lead:", error);
			toast.error("Failed to delete lead", {
				description: error?.message || "Please try again",
			});
		}
	};

	const pageCount = Math.ceil(total / pagination.pageSize);

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<div className="flex items-center justify-between">
				<Title as="h1" className="text-2xl font-bold">
					OA Sourcing
				</Title>
			</div>

			{/* Search Filters */}
			<Card>
				<CardHeader className="pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Search Filters
						</Title>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						<div>
							<Input
								placeholder="Search by Retailer..."
								value={searchRetailer}
								onChange={(e) => setSearchRetailer(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div>
							<Input
								placeholder="Search by Sourcer..."
								value={searchSourcer}
								onChange={(e) => setSearchSourcer(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div className="flex gap-2">
							<Button onClick={handleSearch} disabled={loading} className="flex-1">
								<Icon icon="mdi:magnify" className="mr-2" />
								Search
							</Button>
							<Button variant="outline" onClick={handleClearFilters} disabled={loading}  className="flex-1">
								<Icon icon="mdi:filter-off" className="mr-2" />
								Clear
							</Button>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* Leads Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Lead Records ({total.toLocaleString()} total)
						</Title>
					</CardTitle>
					<CardAction>
						<Button size="sm" variant="outline" onClick={() => loadLeadData()} disabled={loading}>
							<Icon icon="mdi:refresh" className="mr-1" />
							Refresh
						</Button>
					</CardAction>
				</CardHeader>
				<CardContent>
					<DataTable
						columns={columns}
						data={leadData}
						pageCount={pageCount}
						pageIndex={pagination.pageIndex}
						pageSize={pagination.pageSize}
						totalItems={total}
						onPaginationChange={handlePaginationChange}
						manualPagination={true}
						loading={loading}
					/>
				</CardContent>
			</Card>

			{/* Detail Drawer */}
			<Sheet open={detailDrawerOpen} onOpenChange={(open) => {
				setDetailDrawerOpen(open);
				if (!open) {
					setIsEditMode(false);
					editForm.reset();
				}
			}}>
				<SheetContent className="w-full sm:max-w-2xl lg:max-w-4xl overflow-y-auto">
					<SheetHeader className="pr-6">
						<div className="flex justify-between items-start">
							<div>
								<SheetTitle className="text-xl font-bold">
									{isEditMode ? "Edit Lead" : "Lead Details"}
								</SheetTitle>
								<SheetDescription>
									<span className="font-mono text-sm">{selectedLead?.lead_id}</span>
								</SheetDescription>
							</div>
							<div className="flex gap-2 mr-6">
								{!isEditMode ? (
									<Button size="sm" onClick={enterEditMode}>
										<Icon icon="mdi:pencil" className="mr-1" />
										Edit
									</Button>
								) : (
									<>
										<Button size="sm" variant="outline" onClick={cancelEditMode} disabled={isSaving}>
											<Icon icon="mdi:close" className="mr-1" />
											Cancel
										</Button>
										<Button size="sm" onClick={editForm.handleSubmit(handleSaveLead)} disabled={isSaving}>
											<Icon icon="mdi:content-save" className="mr-1" />
											{isSaving ? "Saving..." : "Save"}
										</Button>
									</>
								)}
							</div>
						</div>
					</SheetHeader>

					{selectedLead && !isEditMode && (
						<div className="mt-6 pr-6">
							<Tabs defaultValue="basic" className="w-full ml-4">
								<TabsList className="grid w-full grid-cols-4">
									<TabsTrigger value="basic">Basic Info</TabsTrigger>
									<TabsTrigger value="review">Review</TabsTrigger>
									<TabsTrigger value="pricing">Pricing</TabsTrigger>
									<TabsTrigger value="asins">ASINs</TabsTrigger>
								</TabsList>

								{/* Basic Info Tab */}
								<TabsContent value="basic" className="space-y-4 mt-4">
									<div className="grid grid-cols-2 gap-4">
										<DetailField label="Lead ID" value={selectedLead.lead_id} mono />
										<DetailField label="Sourcer" value={selectedLead.sourcer}>
											<Badge variant="secondary">{selectedLead.sourcer}</Badge>
										</DetailField>
										<DetailField label="Timestamp" value={selectedLead.timestamp} isDate />
										<DetailField label="Product SKU" value={selectedLead.product_sku} mono />
									</div>

									<Separator />

									<div>
										<h4 className="font-semibold mb-2">Product Information</h4>
										<div className="grid grid-cols-1 gap-3">
											<DetailField label="Product Name" value={selectedLead.product_name} />
											<DetailField label="Retailer" value={selectedLead.retailer_name} />
											{selectedLead.retailer_link && (
												<DetailField label="Retailer Link" value={selectedLead.retailer_link} isLink />
											)}
											{selectedLead.amazon_link && (
												<DetailField label="Amazon Link" value={selectedLead.amazon_link} isLink />
											)}
										</div>
									</div>

									<Separator />

									<div className="grid grid-cols-2 gap-4">
										<DetailField label="Purchased" value={selectedLead.purchased}>
											{selectedLead.purchased && (
												<Badge variant={selectedLead.purchased === "Yes" ? "default" : "secondary"}>
													{selectedLead.purchased}
												</Badge>
											)}
										</DetailField>
										<DetailField label="Purchase More" value={selectedLead.purchase_more}>
											{selectedLead.purchase_more && (
												<Badge variant="outline">{selectedLead.purchase_more}</Badge>
											)}
										</DetailField>
										<DetailField label="Monitored" value={selectedLead.monitored}>
											{selectedLead.monitored && <Badge variant="outline">{selectedLead.monitored}</Badge>}
										</DetailField>
									</div>
								</TabsContent>

								{/* Review Tab */}
								<TabsContent value="review" className="space-y-4 mt-4">
									<DetailField label="Pros" value={selectedLead.pros} multiline />
									<Separator />
									<DetailField label="Cons" value={selectedLead.cons} multiline />
									<Separator />
									<DetailField label="Other Notes/Concerns" value={selectedLead.other_notes} multiline />
									<Separator />
									<DetailField label="Head of Product Review/Notes" value={selectedLead.head_review} multiline />
									<Separator />
									<DetailField
										label="Feedback and Notes on Quantity"
										value={selectedLead.feedback_qty}
										multiline
									/>
								</TabsContent>

								{/* Pricing Tab */}
								<TabsContent value="pricing" className="space-y-4 mt-4">
									<div className="grid grid-cols-2 gap-4">
										<DetailField label="PPU (including ship)" value={selectedLead.ppu} isCurrency />
										<DetailField label="RSP" value={selectedLead.rsp} isCurrency />
										<DetailField label="Margin" value={selectedLead.margin} isPercentage />
										<DetailField label="Margin Using RSP" value={selectedLead.margin_using_rsp} isPercentage />
									</div>

									<Separator />

									<div className="grid grid-cols-2 gap-4">
										<DetailField label="Suggested Total QTY" value={selectedLead.suggested_qty} />
										<DetailField label="Pairs Per LEAD ID" value={selectedLead.pairs_per_lead} />
										<DetailField label="Pairs Per SKU" value={selectedLead.pairs_per_sku} />
										<DetailField label="Sales Rank" value={selectedLead.sales_rank} />
									</div>

									<Separator />

									<div className="grid grid-cols-2 gap-4">
										<DetailField label="ASIN 1 Buy Box" value={selectedLead.buy_box} isCurrency />
										<DetailField label="ASIN 1 New Price" value={selectedLead.new_price} isCurrency />
										<DetailField label="Pick&Pack Fee" value={selectedLead.pick_pack_fee} isCurrency />
										<DetailField label="Referral Fee" value={selectedLead.referral_fee} isCurrency />
										<DetailField label="Total Fee" value={selectedLead.total_fee} isCurrency />
									</div>

									<Separator />

									<DetailField label="Promo Code" value={selectedLead.promo_code} mono />
								</TabsContent>

								{/* ASINs Tab */}
								<TabsContent value="asins" className="mt-4">
									{selectedLead.asins && selectedLead.asins.length > 0 ? (
										<div className="space-y-2">
											<h4 className="font-semibold mb-3">
												ASINs ({selectedLead.asins.length})
											</h4>
											<div className="border rounded-lg overflow-hidden">
												<table className="w-full text-sm">
													<thead className="bg-gray-50 dark:bg-gray-800">
														<tr>
															<th className="px-4 py-2 text-left font-semibold">#</th>
															<th className="px-4 py-2 text-left font-semibold">ASIN</th>
															<th className="px-4 py-2 text-left font-semibold">Size</th>
															<th className="px-4 py-2 text-right font-semibold">
																Recommended Qty
															</th>
														</tr>
													</thead>
													<tbody className="divide-y">
														{selectedLead.asins.map((asin, index) => (
															<tr key={asin.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
																<td className="px-4 py-2 text-gray-600">{index + 1}</td>
																<td className="px-4 py-2 font-mono text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
																	{asin.asin}
																</td>
																<td className="px-4 py-2">
																	<Badge variant="outline">{asin.size}</Badge>
																</td>
																<td className="px-4 py-2 text-right font-semibold">
																	{asin.recommended_quantity}
																</td>
															</tr>
														))}
													</tbody>
												</table>
											</div>
										</div>
									) : (
										<div className="text-center py-8 text-gray-500">
											<Icon icon="mdi:package-variant-closed" size={48} className="mx-auto mb-2 opacity-50" />
											<p>No ASINs found for this lead</p>
										</div>
									)}
								</TabsContent>
							</Tabs>
						</div>
					)}

					{/* Edit Mode */}
					{selectedLead && isEditMode && (
						<Form {...editForm}>
							<form onSubmit={editForm.handleSubmit(handleSaveLead)} className="mt-6 pr-6 space-y-6">
								<div className="ml-4 mb-4">
									{/* Basic Info Section */}
									<div className="space-y-4">
										<h3 className="text-lg font-semibold">Basic Information</h3>
										
										<FormField
											control={editForm.control}
											name="productName"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Product Name</FormLabel>
													<FormControl>
														<Input {...field} placeholder="Enter product name" />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="retailerLink"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Retailer Link</FormLabel>
													<FormControl>
														<Input {...field} placeholder="https://" type="url" />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="amazonLink"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Amazon Link</FormLabel>
													<FormControl>
														<Input {...field} placeholder="https://" type="url" />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<div className="grid grid-cols-3 gap-4">
											<FormField
												control={editForm.control}
												name="purchased"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Purchased</FormLabel>
														<Select onValueChange={field.onChange} value={field.value}>
															<FormControl>
																<SelectTrigger>
																	<SelectValue placeholder="Select" />
																</SelectTrigger>
															</FormControl>
															<SelectContent>
																<SelectItem value="Yes">Yes</SelectItem>
																<SelectItem value="No">No</SelectItem>
																<SelectItem value="Pending">Pending</SelectItem>
															</SelectContent>
														</Select>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="purchaseMoreIfAvailable"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Purchase More</FormLabel>
														<Select onValueChange={field.onChange} value={field.value}>
															<FormControl>
																<SelectTrigger>
																	<SelectValue placeholder="Select" />
																</SelectTrigger>
															</FormControl>
															<SelectContent>
																<SelectItem value="Yes">Yes</SelectItem>
																<SelectItem value="No">No</SelectItem>
																<SelectItem value="Maybe">Maybe</SelectItem>
															</SelectContent>
														</Select>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="monitored"
												render={({ field }) => (
													<FormItem className="flex flex-row items-start space-x-3 space-y-0 pt-8">
														<FormControl>
															<Checkbox
																checked={field.value}
																onCheckedChange={field.onChange}
															/>
														</FormControl>
														<div className="space-y-1 leading-none">
															<FormLabel>Monitored</FormLabel>
														</div>
													</FormItem>
												)}
											/>
										</div>
									</div>

									<Separator className="my-6" />

									{/* Review Section */}
									<div className="space-y-4">
										<h3 className="text-lg font-semibold">Review & Notes</h3>

										<FormField
											control={editForm.control}
											name="pros"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Pros</FormLabel>
													<FormControl>
														<MultiSelect
															options={prosOptions}
															value={field.value as string[]}
															onValueChange={field.onChange}
															placeholder="Select pros..."
															searchPlaceholder="Search pros..."
															emptyText="No pros found."
														/>
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="cons"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Cons</FormLabel>
													<FormControl>
														<MultiSelect
															options={consOptions}
															value={field.value as string[]}
															onValueChange={field.onChange}
															placeholder="Select cons..."
															searchPlaceholder="Search cons..."
															emptyText="No cons found."
														/>
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="otherNotesConcerns"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Other Notes/Concerns</FormLabel>
													<FormControl>
														<Textarea {...field} placeholder="Enter any additional notes" rows={3} />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="headOfProductReviewNotes"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Head of Product Review/Notes</FormLabel>
													<FormControl>
														<Textarea {...field} placeholder="Head of product review notes" rows={3} />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={editForm.control}
											name="feedbackAndNotesOnQuantity"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Feedback and Notes on Quantity</FormLabel>
													<FormControl>
														<Textarea {...field} placeholder="Feedback on quantities" rows={3} />
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>
									</div>

									<Separator className="my-6" />

									{/* Pricing & Fees Section */}
									<div className="space-y-4">
										<h3 className="text-lg font-semibold">Pricing & Fees</h3>

										<div className="grid grid-cols-2 gap-4">
											<FormField
												control={editForm.control}
												name="pairsPerLeadId"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Pairs Per LEAD ID</FormLabel>
														<FormControl>
															<Input {...field} type="number" placeholder="0" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="pairsPerSku"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Pairs Per SKU</FormLabel>
														<FormControl>
															<Input {...field} type="number" placeholder="0" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="salesRank"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Sales Rank</FormLabel>
														<FormControl>
															<Input {...field} placeholder="Enter sales rank" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="promoCode"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Promo Code</FormLabel>
														<FormControl>
															<Input {...field} placeholder="Enter promo code" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
										</div>

										<div className="grid grid-cols-2 gap-4">
											<FormField
												control={editForm.control}
												name="asin1BuyBox"
												render={({ field }) => (
													<FormItem>
														<FormLabel>ASIN 1 Buy Box</FormLabel>
														<FormControl>
															<Input {...field} type="number" step="0.01" placeholder="0.00" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="asin1NewPrice"
												render={({ field }) => (
													<FormItem>
														<FormLabel>ASIN 1 New Price</FormLabel>
														<FormControl>
															<Input {...field} type="number" step="0.01" placeholder="0.00" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="pickPackFee"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Pick & Pack Fee</FormLabel>
														<FormControl>
															<Input {...field} type="number" step="0.01" placeholder="0.00" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="referralFee"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Referral Fee</FormLabel>
														<FormControl>
															<Input {...field} type="number" step="0.01" placeholder="0.00" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={editForm.control}
												name="totalFee"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Total Fee</FormLabel>
														<FormControl>
															<Input {...field} type="number" step="0.01" placeholder="0.00" />
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>
										</div>
									</div>
								</div>
							</form>
						</Form>
					)}
				</SheetContent>
			</Sheet>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Are you sure?</DialogTitle>
						<DialogDescription>
							This will permanently delete the lead{" "}
							<span className="font-semibold text-foreground">{leadToDelete?.lead_id}</span> (
							{leadToDelete?.product_name}). This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
							Delete
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

// Helper component for displaying detail fields
function DetailField({
	label,
	value,
	mono = false,
	isDate = false,
	isLink = false,
	isCurrency = false,
	isPercentage = false,
	multiline = false,
	children,
}: {
	label: string;
	value?: string | number | null;
	mono?: boolean;
	isDate?: boolean;
	isLink?: boolean;
	isCurrency?: boolean;
	isPercentage?: boolean;
	multiline?: boolean;
	children?: React.ReactNode;
}) {
	const renderValue = () => {
		if (children) return children;
		if (!value) return <span className="text-gray-400 italic">N/A</span>;

		if (isDate) {
			return <span className="text-sm">{new Date(value).toLocaleString()}</span>;
		}

		if (isLink) {
			return (
				<a
					href={value.toString()}
					target="_blank"
					rel="noopener noreferrer"
					className="text-blue-600 dark:text-blue-400 hover:underline text-sm break-all"
				>
					{value}
				</a>
			);
		}

		if (isCurrency && typeof value === "number") {
			return <span className="font-semibold text-green-600 dark:text-green-400">${value.toFixed(2)}</span>;
		}

		if (isPercentage && typeof value === "number") {
			return <span className="font-semibold text-purple-600 dark:text-purple-400">{value.toFixed(1)}%</span>;
		}

		if (multiline) {
			return <p className="text-sm whitespace-pre-wrap">{value}</p>;
		}

		return <span className={mono ? "font-mono text-sm" : "text-sm"}>{value}</span>;
	};

	return (
		<div>
			<label className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider">
				{label}
			</label>
			<div className="mt-1">{renderValue()}</div>
		</div>
	);
}
