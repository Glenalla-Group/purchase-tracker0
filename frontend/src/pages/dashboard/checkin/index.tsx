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

	// Define table columns
	const columns = useMemo<ColumnDef<CheckinItem>[]>(
		() => [
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
			}
		],
		[pagination.pageIndex, pagination.pageSize]
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
						<Button
							size="sm"
							variant="outline"
							onClick={() => loadCheckinData()}
							disabled={loading}
						>
							<Icon icon="mdi:refresh" className="mr-1" />
							Refresh
						</Button>
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
		</div>
	);
}

