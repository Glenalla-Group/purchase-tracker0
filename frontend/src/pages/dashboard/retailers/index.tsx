import { Button } from "@/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Title } from "@/ui/typography";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Badge } from "@/ui/badge";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import retailerService, { type RetailerItem } from "@/api/services/retailerService";
import Icon from "@/components/icon/icon";
import { DataTable } from "@/components/data-table";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
import { Checkbox } from "@/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import { Label } from "@/ui/label";

export default function Retailers() {
	const [retailerData, setRetailerData] = useState<RetailerItem[]>([]);
	const [loading, setLoading] = useState(false);
	const [total, setTotal] = useState(0);
	const [searchName, setSearchName] = useState("");
	const [filterLocation, setFilterLocation] = useState<string>("");
	const [filterWholesale, setFilterWholesale] = useState<string>("");
	const [filterShopify, setFilterShopify] = useState<string>("");
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
	const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
	const [editingRetailer, setEditingRetailer] = useState<RetailerItem | null>(null);
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [deleteCount, setDeleteCount] = useState(0);
	const [newRetailer, setNewRetailer] = useState({
		name: "",
		link: "",
		wholesale: "",
		cancel_for_bulk: false,
		location: "",
		shopify: false,
	});

	// Handle checkbox selection
	const handleSelectAll = (checked: boolean) => {
		if (checked) {
			const allIds = new Set(retailerData.map((item) => item.id));
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

	// Define table columns
	const columns = useMemo<ColumnDef<RetailerItem>[]>(
		() => [
			{
				id: "select",
				header: () => {
					const allSelected = retailerData.length > 0 && retailerData.every((item) => selectedIds.has(item.id));
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
				size: 50,
				minSize: 50,
				maxSize: 50,
			},
			{
				accessorKey: "id",
				header: "No",
				size: 80,
				minSize: 60,
				maxSize: 120,
				cell: ({ row }) => {
					const index = pagination.pageIndex * pagination.pageSize + row.index + 1;
					return <span className="font-medium">{index}</span>;
				},
			},
			{
				accessorKey: "name",
				header: "Retailer Name",
				size: 250,
				minSize: 200,
				cell: ({ row }) => (
					<div className="flex items-center gap-2">
						<span className="font-semibold">{row.original.name}</span>
						{row.original.link && (
							<a
								href={row.original.link}
								target="_blank"
								rel="noopener noreferrer"
								className="text-blue-500 hover:text-blue-700"
								onClick={(e) => e.stopPropagation()}
							>
								<Icon icon="mdi:link" className="w-4 h-4" />
							</a>
						)}
					</div>
				),
			},
			{
				accessorKey: "location",
				header: "Location",
				size: 120,
				minSize: 100,
				cell: ({ row }) =>
					row.original.location ? (
						<Badge variant="outline">{row.original.location}</Badge>
					) : (
						<span className="text-gray-400 italic">N/A</span>
					),
			},
		{
			accessorKey: "wholesale",
			header: "Wholesale",
			size: 120,
			minSize: 100,
			cell: ({ row }) => {
				const wholesale = row.original.wholesale;
				if (!wholesale) {
					return <span className="text-gray-400 italic">N/A</span>;
				}
				return wholesale === "yes" ? (
					<Badge className="bg-blue-500 hover:bg-blue-600">YES</Badge>
				) : wholesale === "no" ? (
					<Badge className="bg-orange-500 hover:bg-orange-600">NO</Badge>
				) : (
					<Badge variant="secondary">N/A</Badge>
				);
			},
		},
		{
			accessorKey: "shopify",
			header: "Shopify",
			size: 100,
			minSize: 80,
			cell: ({ row }) => (
				<div className="flex items-center justify-center">
					{row.original.shopify ? (
						<Icon icon="mdi:check-circle" className="text-green-600 w-5 h-5" />
					) : (
						<Icon icon="mdi:close-circle" className="text-gray-300 w-5 h-5" />
					)}
				</div>
			),
		},
		{
			accessorKey: "cancel_for_bulk",
			header: "Cancel Bulk",
			size: 120,
			minSize: 100,
			cell: ({ row }) => (
				<div className="flex items-center justify-center">
					{row.original.cancel_for_bulk ? (
						<Icon icon="mdi:close-circle" className="text-red-600 w-5 h-5" />
					) : (
						<Icon icon="mdi:check-circle" className="text-green-500 w-5 h-5" />
					)}
				</div>
			),
		},
			{
				id: "actions",
				header: "Actions",
				size: 100,
				minSize: 80,
				maxSize: 120,
				cell: ({ row }) => (
					<div className="flex items-center justify-center gap-2">
						<Button
							size="sm"
							variant="ghost"
							onClick={() => handleEditClick(row.original)}
							className="h-8 w-8 p-0"
						>
							<Icon icon="mdi:pencil" className="h-4 w-4" />
						</Button>
					</div>
				),
			},
			// {
			// 	accessorKey: "total_spend",
			// 	header: "Total Spend",
			// 	size: 150,
			// 	minSize: 120,
			// 	cell: ({ row }) => (
			// 		<span className="font-mono font-semibold text-green-600">
			// 			${row.original.total_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
			// 		</span>
			// 	),
			// },
			// {
			// 	accessorKey: "total_qty_of_items_ordered",
			// 	header: "Items Ordered",
			// 	size: 150,
			// 	minSize: 120,
			// 	cell: ({ row }) => (
			// 		<span className="font-medium">
			// 			{row.original.total_qty_of_items_ordered.toLocaleString()}
			// 		</span>
			// 	),
			// },
			// {
			// 	accessorKey: "percent_of_cancelled_qty",
			// 	header: "Cancel %",
			// 	size: 120,
			// 	minSize: 100,
			// 	cell: ({ row }) => {
			// 		const percent = row.original.percent_of_cancelled_qty;
			// 		const colorClass = percent > 10 ? "text-red-600" : percent > 5 ? "text-yellow-600" : "text-green-600";
			// 		return (
			// 			<span className={`font-semibold ${colorClass}`}>
			// 				{percent.toFixed(2)}%
			// 			</span>
			// 		);
			// 	},
			// },
		],
		[pagination.pageIndex, pagination.pageSize, retailerData, selectedIds]
	);

	// Load retailer data from backend
	const loadRetailerData = async (newPagination?: PaginationState) => {
		setLoading(true);
		const currentPagination = newPagination || pagination;

		try {
			const params: any = {
				skip: currentPagination.pageIndex * currentPagination.pageSize,
				limit: currentPagination.pageSize,
			};

			if (filterLocation && filterLocation !== "all") {
				params.location = filterLocation;
			}
			if (filterWholesale && filterWholesale !== "all") {
				params.wholesale = filterWholesale;
			}
			if (filterShopify && filterShopify !== "all") {
				params.shopify = filterShopify === "true";
			}

			const response = await retailerService.getRetailers(params);

			// Filter by name on client side if search is provided
			let filteredData = response.items;
			if (searchName) {
				filteredData = response.items.filter((retailer) =>
					retailer.name.toLowerCase().includes(searchName.toLowerCase())
				);
			}

			setRetailerData(filteredData);
			setTotal(searchName ? filteredData.length : response.total);
			setSelectedIds(new Set()); // Clear selection when loading new data
		} catch (error: any) {
			console.error("Error loading retailer data:", error);
			toast.error("Failed to load retailer data", {
				description: error?.message || "Please try again",
			});
			setRetailerData([]);
			setTotal(0);
		} finally {
			setLoading(false);
		}
	};

	// Handle bulk delete confirmation
	const handleBulkDeleteConfirm = () => {
		if (selectedIds.size === 0) {
			toast.warning("No retailers selected");
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
			await retailerService.bulkDeleteRetailers(idsArray);

			toast.success(`Successfully deleted ${selectedIds.size} retailer(s)`);
			setSelectedIds(new Set());
			setDeleteDialogOpen(false);
			await loadRetailerData();
		} catch (error: any) {
			console.error("Error deleting retailers:", error);
			toast.error("Failed to delete retailers", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle edit click
	const handleEditClick = (retailer: RetailerItem) => {
		setEditingRetailer(retailer);
		setIsEditDialogOpen(true);
	};

	// Handle add retailer
	const handleAddRetailer = async () => {
		if (!newRetailer.name) {
			toast.error("Retailer name is required");
			return;
		}

		try {
			setLoading(true);
			await retailerService.createRetailer({
				name: newRetailer.name,
				link: newRetailer.link || undefined,
				wholesale: newRetailer.wholesale || undefined,
				cancel_for_bulk: newRetailer.cancel_for_bulk,
				location: newRetailer.location || undefined,
				shopify: newRetailer.shopify,
			});

			toast.success("Retailer created successfully");
			setIsAddDialogOpen(false);
			setNewRetailer({
				name: "",
				link: "",
				wholesale: "",
				cancel_for_bulk: false,
				location: "",
				shopify: false,
			});
			await loadRetailerData();
		} catch (error: any) {
			console.error("Error creating retailer:", error);
			toast.error("Failed to create retailer", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle edit retailer
	const handleEditRetailer = async () => {
		if (!editingRetailer) return;

		if (!editingRetailer.name) {
			toast.error("Retailer name is required");
			return;
		}

		try {
			setLoading(true);
			await retailerService.updateRetailer(editingRetailer.id, {
				name: editingRetailer.name,
				link: editingRetailer.link || undefined,
				wholesale: editingRetailer.wholesale || undefined,
				cancel_for_bulk: editingRetailer.cancel_for_bulk,
				location: editingRetailer.location || undefined,
				shopify: editingRetailer.shopify,
			});

			toast.success("Retailer updated successfully");
			setIsEditDialogOpen(false);
			setEditingRetailer(null);
			await loadRetailerData();
		} catch (error: any) {
			console.error("Error updating retailer:", error);
			toast.error("Failed to update retailer", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Load data on component mount
	useEffect(() => {
		loadRetailerData();
	}, []);

	// Handle pagination change
	const handlePaginationChange = (newPagination: PaginationState) => {
		setPagination(newPagination);
		loadRetailerData(newPagination);
	};

	// Handle search
	const handleSearch = () => {
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		loadRetailerData(newPagination);
	};

	// Handle clear filters
	const handleClearFilters = () => {
		setSearchName("");
		setFilterLocation("");
		setFilterWholesale("");
		setFilterShopify("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadRetailerData(newPagination), 0);
	};

	const pageCount = Math.ceil(total / pagination.pageSize);

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<div className="flex items-center justify-between">
				<Title as="h1" className="text-2xl font-bold">
					Retailers
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
				<div className="space-y-3">
					{/* Row 1: Search Name & Location */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
						<Input
							placeholder="Search by name..."
							value={searchName}
							onChange={(e) => setSearchName(e.target.value)}
							onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							className="w-full"
						/>
						<Select value={filterLocation} onValueChange={setFilterLocation}>
							<SelectTrigger className="w-full">
								<SelectValue placeholder="All Locations" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="all">All Locations</SelectItem>
								<SelectItem value="USA">USA</SelectItem>
								<SelectItem value="UK">UK</SelectItem>
								<SelectItem value="EU">EU</SelectItem>
								<SelectItem value="CANADA">CANADA</SelectItem>
								<SelectItem value="AU">AU</SelectItem>
								<SelectItem value="SA">SA</SelectItem>
							</SelectContent>
						</Select>
					</div>
					
					{/* Row 2: Other Filters & Action Buttons */}
					<div className="grid grid-cols-1 md:grid-cols-4 gap-3">
						<Select value={filterWholesale} onValueChange={setFilterWholesale}>
							<SelectTrigger className="w-full">
								<SelectValue placeholder="All Wholesale" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="all">All Wholesale</SelectItem>
								<SelectItem value="yes">Yes</SelectItem>
								<SelectItem value="no">No</SelectItem>
								<SelectItem value="n/a">N/A</SelectItem>
							</SelectContent>
						</Select>
						
						<Select value={filterShopify} onValueChange={setFilterShopify}>
							<SelectTrigger className="w-full">
								<SelectValue placeholder="All Shopify" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="all">All</SelectItem>
								<SelectItem value="true">Shopify</SelectItem>
								<SelectItem value="false">Non-Shopify</SelectItem>
							</SelectContent>
						</Select>
						
						<Button 
							onClick={handleSearch} 
							disabled={loading} 
							className="w-full"
						>
							<Icon icon="mdi:magnify" className="mr-2" />
							Search
						</Button>
						
						<Button 
							variant="outline" 
							onClick={handleClearFilters} 
							disabled={loading} 
							className="w-full"
						>
							<Icon icon="mdi:filter-off" className="mr-2" />
							Clear
						</Button>
					</div>
				</div>
			</CardContent>
			</Card>

			{/* Retailer Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Retailer List ({total.toLocaleString()} total)
						</Title>
					</CardTitle>
					<CardAction>
						<div className="flex gap-2">
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
								onClick={() => setIsAddDialogOpen(true)}
								disabled={loading}
							>
								<Icon icon="mdi:plus" className="mr-1" />
								Add Retailer
							</Button>
							<Button
								size="sm"
								variant="outline"
								onClick={() => loadRetailerData()}
								disabled={loading}
							>
								<Icon icon="mdi:refresh" className="mr-1" />
								Refresh
							</Button>
						</div>
					</CardAction>
				</CardHeader>
				<CardContent>
					<DataTable
						columns={columns}
						data={retailerData}
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

			{/* Add Retailer Dialog */}
			<Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle>Add New Retailer</DialogTitle>
						<DialogDescription>
							Create a new retailer in the system. Name is required.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid gap-2">
							<Label htmlFor="name">
								Name <span className="text-red-500">*</span>
							</Label>
							<Input
								id="name"
								placeholder="Enter retailer name"
								value={newRetailer.name}
								onChange={(e) => setNewRetailer({ ...newRetailer, name: e.target.value })}
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="link">Website URL (Optional)</Label>
							<Input
								id="link"
								placeholder="https://example.com"
								value={newRetailer.link}
								onChange={(e) => setNewRetailer({ ...newRetailer, link: e.target.value })}
							/>
						</div>
						<div className="grid grid-cols-2 gap-4">
							<div className="grid gap-2">
								<Label htmlFor="location">Location (Optional)</Label>
								<Select
									value={newRetailer.location || undefined}
									onValueChange={(value) => setNewRetailer({ ...newRetailer, location: value })}
								>
									<SelectTrigger id="location">
										<SelectValue placeholder="Select location" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="USA">USA</SelectItem>
										<SelectItem value="UK">UK</SelectItem>
										<SelectItem value="EU">EU</SelectItem>
										<SelectItem value="CANADA">CANADA</SelectItem>
										<SelectItem value="AU">AU</SelectItem>
										<SelectItem value="SA">SA</SelectItem>
									</SelectContent>
								</Select>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="wholesale">Wholesale (Optional)</Label>
								<Select
									value={newRetailer.wholesale || undefined}
									onValueChange={(value) => setNewRetailer({ ...newRetailer, wholesale: value })}
								>
									<SelectTrigger id="wholesale">
										<SelectValue placeholder="Select wholesale status" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="yes">Yes</SelectItem>
										<SelectItem value="no">No</SelectItem>
										<SelectItem value="n/a">N/A</SelectItem>
									</SelectContent>
								</Select>
							</div>
						</div>
						<div className="grid grid-cols-2 gap-4">
							<div className="flex items-center space-x-2">
								<Checkbox
									id="shopify"
									checked={newRetailer.shopify}
									onCheckedChange={(checked) =>
										setNewRetailer({ ...newRetailer, shopify: checked as boolean })
									}
								/>
								<Label htmlFor="shopify" className="cursor-pointer">
									Shopify Store
								</Label>
							</div>
							<div className="flex items-center space-x-2">
								<Checkbox
									id="cancel_for_bulk"
									checked={newRetailer.cancel_for_bulk}
									onCheckedChange={(checked) =>
										setNewRetailer({ ...newRetailer, cancel_for_bulk: checked as boolean })
									}
								/>
								<Label htmlFor="cancel_for_bulk" className="cursor-pointer">
									Cancel for Bulk
								</Label>
							</div>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setIsAddDialogOpen(false)} disabled={loading}>
							Cancel
						</Button>
						<Button onClick={handleAddRetailer} disabled={loading}>
							{loading ? "Creating..." : "Create Retailer"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Edit Retailer Dialog */}
			<Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle>Edit Retailer</DialogTitle>
						<DialogDescription>
							Update retailer information. Name is required.
						</DialogDescription>
					</DialogHeader>
					{editingRetailer && (
						<div className="grid gap-4 py-4">
							<div className="grid gap-2">
								<Label htmlFor="edit-name">
									Name <span className="text-red-500">*</span>
								</Label>
								<Input
									id="edit-name"
									placeholder="Enter retailer name"
									value={editingRetailer.name}
									onChange={(e) => setEditingRetailer({ ...editingRetailer, name: e.target.value })}
								/>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="edit-link">Website URL (Optional)</Label>
								<Input
									id="edit-link"
									placeholder="https://example.com"
									value={editingRetailer.link || ""}
									onChange={(e) => setEditingRetailer({ ...editingRetailer, link: e.target.value })}
								/>
							</div>
							<div className="grid grid-cols-2 gap-4">
								<div className="grid gap-2">
									<Label htmlFor="edit-location">Location (Optional)</Label>
									<Select
										value={editingRetailer.location || undefined}
										onValueChange={(value) => setEditingRetailer({ ...editingRetailer, location: value })}
									>
										<SelectTrigger id="edit-location">
											<SelectValue placeholder="Select location" />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="USA">USA</SelectItem>
											<SelectItem value="UK">UK</SelectItem>
											<SelectItem value="EU">EU</SelectItem>
											<SelectItem value="CANADA">CANADA</SelectItem>
											<SelectItem value="AU">AU</SelectItem>
											<SelectItem value="SA">SA</SelectItem>
										</SelectContent>
									</Select>
								</div>
								<div className="grid gap-2">
									<Label htmlFor="edit-wholesale">Wholesale (Optional)</Label>
									<Select
										value={editingRetailer.wholesale || undefined}
										onValueChange={(value) => setEditingRetailer({ ...editingRetailer, wholesale: value })}
									>
										<SelectTrigger id="edit-wholesale">
											<SelectValue placeholder="Select wholesale status" />
										</SelectTrigger>
										<SelectContent>
											<SelectItem value="yes">Yes</SelectItem>
											<SelectItem value="no">No</SelectItem>
											<SelectItem value="n/a">N/A</SelectItem>
										</SelectContent>
									</Select>
								</div>
							</div>
							<div className="grid grid-cols-2 gap-4">
								<div className="flex items-center space-x-2">
									<Checkbox
										id="edit-shopify"
										checked={editingRetailer.shopify}
										onCheckedChange={(checked) =>
											setEditingRetailer({ ...editingRetailer, shopify: checked as boolean })
										}
									/>
									<Label htmlFor="edit-shopify" className="cursor-pointer">
										Shopify Store
									</Label>
								</div>
								<div className="flex items-center space-x-2">
									<Checkbox
										id="edit-cancel_for_bulk"
										checked={editingRetailer.cancel_for_bulk}
										onCheckedChange={(checked) =>
											setEditingRetailer({ ...editingRetailer, cancel_for_bulk: checked as boolean })
										}
									/>
									<Label htmlFor="edit-cancel_for_bulk" className="cursor-pointer">
										Cancel for Bulk
									</Label>
								</div>
							</div>
						</div>
					)}
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setIsEditDialogOpen(false);
								setEditingRetailer(null);
							}}
							disabled={loading}
						>
							Cancel
						</Button>
						<Button onClick={handleEditRetailer} disabled={loading}>
							{loading ? "Updating..." : "Update Retailer"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Are you sure?</DialogTitle>
						<DialogDescription>
							This will permanently delete{" "}
							<span className="font-semibold text-foreground">{deleteCount}</span> retailer
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

