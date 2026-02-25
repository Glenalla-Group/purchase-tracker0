import { Button } from "@/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Title } from "@/ui/typography";
import { Badge } from "@/ui/badge";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import checkinService, { type CheckinItem } from "@/api/services/checkinService";
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

export default function Checkin() {
	const [checkinData, setCheckinData] = useState<CheckinItem[]>([]);
	const [loading, setLoading] = useState(false);
	const [total, setTotal] = useState(0);
	const [searchOrderNumber, setSearchOrderNumber] = useState("");
	const [searchItemName, setSearchItemName] = useState("");
	const [searchAsin, setSearchAsin] = useState("");
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
	const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
	const [editingCheckin, setEditingCheckin] = useState<CheckinItem | null>(null);
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [deleteCount, setDeleteCount] = useState(0);
	const [newCheckin, setNewCheckin] = useState({
		order_number: "",
		item_name: "",
		asin: "",
		size: "",
		quantity: 1,
	});

	// Handle checkbox selection
	const handleSelectAll = (checked: boolean) => {
		if (checked) {
			const allIds = new Set(checkinData.map((item) => item.id));
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
	const columns = useMemo<ColumnDef<CheckinItem>[]>(
		() => [
			{
				id: "select",
				header: () => {
					const allSelected = checkinData.length > 0 && checkinData.every((item) => selectedIds.has(item.id));
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
				accessorKey: "order_number",
				header: "Order Number",
				size: 200,
				minSize: 150,
				cell: ({ row }) =>
					row.original.order_number ? (
						<span className="font-mono text-xs bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 px-2 py-1 rounded">
							{row.original.order_number}
						</span>
					) : (
						<span className="text-gray-400 italic">N/A</span>
					),
			},
			{
				accessorKey: "item_name",
				header: "Item Name",
				size: 300,
				minSize: 200,
				cell: ({ row }) =>
					row.original.item_name ? (
						<span className="font-medium">{row.original.item_name}</span>
					) : (
						<span className="text-gray-400 italic">N/A</span>
					),
			},
			{
				accessorKey: "asin",
				header: "ASIN",
				size: 150,
				minSize: 120,
				cell: ({ row }) =>
					row.original.asin ? (
						<div className="flex flex-col gap-1">
							<span className="font-mono font-semibold">{row.original.asin}</span>
							{row.original.size && (
								<span className="text-xs text-gray-500">Size: {row.original.size}</span>
							)}
						</div>
					) : (
						<span className="text-gray-400 italic">N/A</span>
					),
			},
			{
				accessorKey: "quantity",
				header: "Quantity",
				size: 120,
				minSize: 100,
				cell: ({ row }) => (
					<div className="flex items-center justify-center">
						<Badge variant="default" className="text-base font-bold">
							{row.original.quantity}
						</Badge>
					</div>
				),
			},
			{
				accessorKey: "checked_in_at",
				header: "Check-in Date",
				size: 200,
				minSize: 180,
				cell: ({ row }) => {
					const date = new Date(row.original.checked_in_at);
					return (
						<div className="flex flex-col gap-1">
							<span className="font-medium">
								{date.toLocaleDateString()}
							</span>
							<span className="text-xs text-gray-500">
								{date.toLocaleTimeString()}
							</span>
						</div>
					);
				},
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
			}
		],
		[pagination.pageIndex, pagination.pageSize, checkinData, selectedIds]
	);

	// Load checkin data from backend
	const loadCheckinData = async (newPagination?: PaginationState) => {
		setLoading(true);
		const currentPagination = newPagination || pagination;

		try {
			const params: any = {
				skip: currentPagination.pageIndex * currentPagination.pageSize,
				limit: currentPagination.pageSize,
			};

			if (searchOrderNumber) {
				params.order_number = searchOrderNumber;
			}
			if (searchAsin) {
				params.asin = searchAsin;
			}

			const response = await checkinService.getCheckins(params);

			// Filter by item name on client side if search is provided
			let filteredData: CheckinItem[] = response.items || [];
			if (searchItemName && response.items) {
				filteredData = response.items.filter((checkin: CheckinItem) =>
					checkin.item_name?.toLowerCase().includes(searchItemName.toLowerCase())
				);
			}

			setCheckinData(filteredData);
			setTotal(searchItemName ? filteredData.length : (response.total || 0));
			setSelectedIds(new Set()); // Clear selection when loading new data
		} catch (error: any) {
			console.error("Error loading checkin data:", error);
			toast.error("Failed to load check-in data", {
				description: error?.message || "Please try again",
			});
			setCheckinData([]);
			setTotal(0);
		} finally {
			setLoading(false);
		}
	};

	// Handle edit click
	const handleEditClick = (checkin: CheckinItem) => {
		setEditingCheckin(checkin);
		setIsEditDialogOpen(true);
	};

	// Handle bulk delete confirmation
	const handleBulkDeleteConfirm = () => {
		if (selectedIds.size === 0) {
			toast.warning("No check-in records selected");
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
			await checkinService.bulkDeleteCheckins(idsArray);

			toast.success(`Successfully deleted ${selectedIds.size} check-in record(s)`);
			setSelectedIds(new Set());
			setDeleteDialogOpen(false);
			await loadCheckinData();
		} catch (error: any) {
			console.error("Error deleting check-ins:", error);
			toast.error("Failed to delete check-in records", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle add check-in
	const handleAddCheckin = async () => {
		if (!newCheckin.order_number || !newCheckin.item_name || !newCheckin.quantity) {
			toast.error("Order number, item name, and quantity are required");
			return;
		}

		try {
			setLoading(true);
			await checkinService.createCheckin({
				order_number: newCheckin.order_number,
				item_name: newCheckin.item_name,
				asin: newCheckin.asin || undefined,
				size: newCheckin.size || undefined,
				quantity: newCheckin.quantity,
			});

			toast.success("Check-in created successfully");
			setIsAddDialogOpen(false);
			setNewCheckin({
				order_number: "",
				item_name: "",
				asin: "",
				size: "",
				quantity: 1,
			});
			await loadCheckinData();
		} catch (error: any) {
			console.error("Error creating check-in:", error);
			toast.error("Failed to create check-in", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle edit check-in
	const handleEditCheckin = async () => {
		if (!editingCheckin) return;

		if (!editingCheckin.order_number || !editingCheckin.item_name || !editingCheckin.quantity) {
			toast.error("Order number, item name, and quantity are required");
			return;
		}

		try {
			setLoading(true);
			await checkinService.updateCheckin(editingCheckin.id, {
				order_number: editingCheckin.order_number,
				item_name: editingCheckin.item_name,
				quantity: editingCheckin.quantity,
			});

			toast.success("Check-in updated successfully");
			setIsEditDialogOpen(false);
			setEditingCheckin(null);
			await loadCheckinData();
		} catch (error: any) {
			console.error("Error updating check-in:", error);
			toast.error("Failed to update check-in", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Load data on component mount
	useEffect(() => {
		loadCheckinData();
	}, []);

	// Handle pagination change
	const handlePaginationChange = (newPagination: PaginationState) => {
		setPagination(newPagination);
		loadCheckinData(newPagination);
	};

	// Handle search
	const handleSearch = () => {
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		loadCheckinData(newPagination);
	};

	// Handle clear filters
	const handleClearFilters = () => {
		setSearchOrderNumber("");
		setSearchItemName("");
		setSearchAsin("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadCheckinData(newPagination), 0);
	};

	// Handle processing PrepWorx emails
	const handleProcessPrepWorxEmails = async () => {
		try {
			toast.info("Processing PrepWorx emails...", {
				description: "Searching for unprocessed inbound emails",
			});

			const result = await checkinService.processPrepWorxEmails(3);

			if (result.processing_count > 0) {
				toast.success(`Processing up to ${result.processing_count} emails in background!`, {
					description: "Searching and processing emails. Data will appear in ~10 seconds.",
				});
				
				// Reload checkin data after a short delay to show new entries
				setTimeout(() => {
					loadCheckinData();
				}, 10000); // Wait 10 seconds for background search + processing
			} else {
				toast.info("No unprocessed PrepWorx emails found", {
					description: "All inbound emails have been processed",
				});
			}
		} catch (error: any) {
			console.error("Error processing PrepWorx emails:", error);
			toast.error("Failed to start processing PrepWorx emails", {
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
					Check-In Records
				</Title>
				<Button
					onClick={handleProcessPrepWorxEmails}
					disabled={loading}
					className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
				>
					<Icon icon="mdi:email-sync" className="mr-2" />
					Process Inbound Emails
				</Button>
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
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
						<div>
							<Input
								placeholder="Search by Order Number..."
								value={searchOrderNumber}
								onChange={(e) => setSearchOrderNumber(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div>
							<Input
								placeholder="Search by Item Name..."
								value={searchItemName}
								onChange={(e) => setSearchItemName(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div>
							<Input
								placeholder="Search by ASIN..."
								value={searchAsin}
								onChange={(e) => setSearchAsin(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div className="flex gap-2">
							<Button onClick={handleSearch} disabled={loading} className="flex-1">
								<Icon icon="mdi:magnify" className="mr-2" />
								Search
							</Button>
							<Button variant="outline" onClick={handleClearFilters} disabled={loading} className="flex-1">
								<Icon icon="mdi:filter-off" className="mr-2" />
								Clear
							</Button>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* Checkin Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Check-In List ({total.toLocaleString()} total)
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
								Add Check-in
							</Button>
							<Button
								size="sm"
								variant="outline"
								onClick={() => loadCheckinData()}
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
						data={checkinData}
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

			{/* Add Check-in Dialog */}
			<Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle>Add New Check-in</DialogTitle>
						<DialogDescription>
							Create a new check-in record. Order number, item name, and quantity are required.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid gap-2">
							<Label htmlFor="order_number">
								Order Number <span className="text-red-500">*</span>
							</Label>
							<Input
								id="order_number"
								placeholder="Enter order number"
								value={newCheckin.order_number}
								onChange={(e) => setNewCheckin({ ...newCheckin, order_number: e.target.value })}
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="item_name">
								Item Name <span className="text-red-500">*</span>
							</Label>
							<Input
								id="item_name"
								placeholder="Enter item name"
								value={newCheckin.item_name}
								onChange={(e) => setNewCheckin({ ...newCheckin, item_name: e.target.value })}
							/>
						</div>
						<div className="grid grid-cols-2 gap-4">
							<div className="grid gap-2">
								<Label htmlFor="asin">ASIN (Optional)</Label>
								<Input
									id="asin"
									placeholder="Enter ASIN"
									value={newCheckin.asin}
									onChange={(e) => setNewCheckin({ ...newCheckin, asin: e.target.value })}
								/>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="size">Size (Optional)</Label>
								<Input
									id="size"
									placeholder="Enter size"
									value={newCheckin.size}
									onChange={(e) => setNewCheckin({ ...newCheckin, size: e.target.value })}
								/>
							</div>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="quantity">
								Quantity <span className="text-red-500">*</span>
							</Label>
							<Input
								id="quantity"
								type="number"
								min="1"
								placeholder="Enter quantity"
								value={newCheckin.quantity}
								onChange={(e) => setNewCheckin({ ...newCheckin, quantity: parseInt(e.target.value) || 1 })}
							/>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setIsAddDialogOpen(false)} disabled={loading}>
							Cancel
						</Button>
						<Button onClick={handleAddCheckin} disabled={loading}>
							{loading ? "Creating..." : "Create Check-in"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Edit Check-in Dialog */}
			<Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle>Edit Check-in</DialogTitle>
						<DialogDescription>
							Update check-in information. Order number, item name, and quantity are required.
						</DialogDescription>
					</DialogHeader>
					{editingCheckin && (
						<div className="grid gap-4 py-4">
							<div className="grid gap-2">
								<Label htmlFor="edit-order_number">
									Order Number <span className="text-red-500">*</span>
								</Label>
								<Input
									id="edit-order_number"
									placeholder="Enter order number"
									value={editingCheckin.order_number || ""}
									onChange={(e) =>
										setEditingCheckin({ ...editingCheckin, order_number: e.target.value })
									}
								/>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="edit-item_name">
									Item Name <span className="text-red-500">*</span>
								</Label>
								<Input
									id="edit-item_name"
									placeholder="Enter item name"
									value={editingCheckin.item_name || ""}
									onChange={(e) =>
										setEditingCheckin({ ...editingCheckin, item_name: e.target.value })
									}
								/>
							</div>
							<div className="grid grid-cols-2 gap-4">
								<div className="grid gap-2">
									<Label htmlFor="edit-asin">ASIN (Read-only)</Label>
									<Input
										id="edit-asin"
										value={editingCheckin.asin || "N/A"}
										disabled
										className="bg-gray-50"
									/>
								</div>
								<div className="grid gap-2">
									<Label htmlFor="edit-size">Size (Read-only)</Label>
									<Input
										id="edit-size"
										value={editingCheckin.size || "N/A"}
										disabled
										className="bg-gray-50"
									/>
								</div>
							</div>
							<div className="grid gap-2">
								<Label htmlFor="edit-quantity">
									Quantity <span className="text-red-500">*</span>
								</Label>
								<Input
									id="edit-quantity"
									type="number"
									min="1"
									placeholder="Enter quantity"
									value={editingCheckin.quantity}
									onChange={(e) =>
										setEditingCheckin({ ...editingCheckin, quantity: parseInt(e.target.value) || 1 })
									}
								/>
							</div>
						</div>
					)}
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setIsEditDialogOpen(false);
								setEditingCheckin(null);
							}}
							disabled={loading}
						>
							Cancel
						</Button>
						<Button onClick={handleEditCheckin} disabled={loading}>
							{loading ? "Updating..." : "Update Check-in"}
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
							<span className="font-semibold text-foreground">{deleteCount}</span> check-in record
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

