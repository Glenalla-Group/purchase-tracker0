import { Button } from "@/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Title } from "@/ui/typography";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import asinBankService, { type AsinBankItem, type CreateAsinRequest } from "@/api/services/asinBankService";
import Icon from "@/components/icon/icon";
import { DataTable } from "@/components/data-table/data-table";
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

export default function AsinBank() {
	const [asinData, setAsinData] = useState<AsinBankItem[]>([]);
	const [loading, setLoading] = useState(false);
	const [total, setTotal] = useState(0);
	const [searchLeadId, setSearchLeadId] = useState("");
	const [searchAsin, setSearchAsin] = useState("");
	const [searchSize, setSearchSize] = useState("");
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});
	const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
	const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [deleteCount, setDeleteCount] = useState(0);
	const [newAsin, setNewAsin] = useState<CreateAsinRequest>({
		lead_id: "",
		asin: "",
		size: "",
	});

	// Handle checkbox selection
	const handleSelectAll = (checked: boolean) => {
		if (checked) {
			const allIds = new Set(asinData.map((item) => item.id));
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
	const columns = useMemo<ColumnDef<AsinBankItem>[]>(
		() => [
			{
				id: "select",
				header: () => {
					const allSelected = asinData.length > 0 && asinData.every((item) => selectedIds.has(item.id));
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
				accessorKey: "lead_id",
				header: "Lead ID",
				size: 250,
				minSize: 200,
				cell: ({ row }) => (
					<span className="font-mono text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2 py-1 rounded">
						{row.original.lead_id}
					</span>
				),
			},
			{
				accessorKey: "size",
				header: "Size",
				size: 120,
				minSize: 80,
				maxSize: 200,
				cell: ({ row }) =>
					row.original.size ? (
						<span className="font-medium">{row.original.size}</span>
					) : (
						<span className="text-gray-400 italic">N/A</span>
					),
			},
			{
				accessorKey: "asin",
				header: "ASIN Number",
				size: 200,
				minSize: 150,
				cell: ({ row }) => <span className="font-mono font-semibold">{row.original.asin}</span>,
			},
			{
				accessorKey: "created_at",
				header: "Created At",
				size: 180,
				minSize: 150,
				maxSize: 250,
				cell: ({ row }) => {
					if (!row.original.created_at) {
						return <span className="text-gray-400 italic">N/A</span>;
					}
					const date = new Date(row.original.created_at);
					return (
						<div className="flex flex-col">
							<span className="text-sm">{date.toLocaleDateString()}</span>
							<span className="text-xs text-gray-500">{date.toLocaleTimeString()}</span>
						</div>
					);
				},
			},
		],
	[pagination.pageIndex, pagination.pageSize, asinData, selectedIds]
);

	// Load ASIN data from backend
	const loadAsinData = async (newPagination?: PaginationState) => {
		setLoading(true);
		const currentPagination = newPagination || pagination;

		try {
			const params = {
				skip: currentPagination.pageIndex * currentPagination.pageSize,
				limit: currentPagination.pageSize,
				lead_id: searchLeadId || undefined,
				asin: searchAsin || undefined,
				size: searchSize || undefined,
			};
			
			const response = await asinBankService.getAsinBank(params);

			setAsinData(response.items);
			setTotal(response.total);
			setSelectedIds(new Set()); // Clear selection when loading new data
		} catch (error: any) {
			console.error("Error loading ASIN data:", error);
			toast.error("Failed to load ASIN data", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle bulk delete confirmation
	const handleBulkDeleteConfirm = () => {
		if (selectedIds.size === 0) {
			toast.warning("No ASINs selected");
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
			await asinBankService.deleteAsins(idsArray);

			toast.success(`Successfully deleted ${selectedIds.size} ASIN(s)`);
			setSelectedIds(new Set());
			setDeleteDialogOpen(false);
			await loadAsinData();
		} catch (error: any) {
			console.error("Error deleting ASINs:", error);
			toast.error("Failed to delete ASINs", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Handle add ASIN
	const handleAddAsin = async () => {
		if (!newAsin.lead_id || !newAsin.asin) {
			toast.error("Lead ID and ASIN are required");
			return;
		}

		try {
			setLoading(true);
			await asinBankService.createAsin(newAsin);

			toast.success("ASIN created successfully");
			setIsAddDialogOpen(false);
			setNewAsin({ lead_id: "", asin: "", size: "" });
			await loadAsinData();
		} catch (error: any) {
			console.error("Error creating ASIN:", error);
			toast.error("Failed to create ASIN", {
				description: error?.message || "Please try again",
			});
		} finally {
			setLoading(false);
		}
	};

	// Load data on component mount
	useEffect(() => {
		loadAsinData();
	}, []);

	// Handle pagination change
	const handlePaginationChange = (newPagination: PaginationState) => {
		setPagination(newPagination);
		loadAsinData(newPagination);
	};

	// Handle search
	const handleSearch = () => {
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		loadAsinData(newPagination);
	};

	// Handle clear filters
	const handleClearFilters = () => {
		setSearchLeadId("");
		setSearchAsin("");
		setSearchSize("");
		const newPagination = { ...pagination, pageIndex: 0 };
		setPagination(newPagination);
		setTimeout(() => loadAsinData(newPagination), 0);
	};

	const pageCount = Math.ceil(total / pagination.pageSize);

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<div className="flex items-center justify-between">
				<Title as="h1" className="text-2xl font-bold">
					ASIN Bank
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
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
						<div>
							<Input
								placeholder="Search by Lead ID..."
								value={searchLeadId}
								onChange={(e) => setSearchLeadId(e.target.value)}
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
						<div>
							<Input
								placeholder="Search by Size..."
								value={searchSize}
								onChange={(e) => setSearchSize(e.target.value)}
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

			{/* ASIN Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							ASIN Records ({total.toLocaleString()} total)
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
								Add ASIN
							</Button>
							<Button
								size="sm"
								variant="outline"
								onClick={() => loadAsinData()}
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
						data={asinData}
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

			{/* Add ASIN Dialog */}
			<Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Add New ASIN</DialogTitle>
						<DialogDescription>
							Manually add a new ASIN to the ASIN Bank. Fill in the required fields below.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid gap-2">
							<Label htmlFor="lead_id">
								Lead ID <span className="text-red-500">*</span>
							</Label>
							<Input
								id="lead_id"
								placeholder="Enter Lead ID"
								value={newAsin.lead_id}
								onChange={(e) => setNewAsin({ ...newAsin, lead_id: e.target.value })}
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="asin">
								ASIN <span className="text-red-500">*</span>
							</Label>
							<Input
								id="asin"
								placeholder="Enter ASIN"
								value={newAsin.asin}
								onChange={(e) => setNewAsin({ ...newAsin, asin: e.target.value })}
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="size">Size (Optional)</Label>
							<Input
								id="size"
								placeholder="Enter Size"
								value={newAsin.size || ""}
								onChange={(e) => setNewAsin({ ...newAsin, size: e.target.value })}
							/>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setIsAddDialogOpen(false)} disabled={loading}>
							Cancel
						</Button>
						<Button onClick={handleAddAsin} disabled={loading}>
							{loading ? "Creating..." : "Create ASIN"}
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
							<span className="font-semibold text-foreground">{deleteCount}</span> ASIN
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
