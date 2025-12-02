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

	// Define table columns
	const columns = useMemo<ColumnDef<RetailerItem>[]>(
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
					const variant =
						wholesale === "yes" ? "default" : wholesale === "no" ? "destructive" : "secondary";
					return wholesale ? (
						<Badge variant={variant}>{wholesale.toUpperCase()}</Badge>
					) : (
						<span className="text-gray-400 italic">N/A</span>
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
							<Icon icon="mdi:check-circle" className="text-green-500 w-5 h-5" />
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
							<Badge variant="destructive">Yes</Badge>
						) : (
							<Badge variant="outline">No</Badge>
						)}
					</div>
				),
			},
			{
				accessorKey: "total_spend",
				header: "Total Spend",
				size: 150,
				minSize: 120,
				cell: ({ row }) => (
					<span className="font-mono font-semibold text-green-600">
						${row.original.total_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
					</span>
				),
			},
			{
				accessorKey: "total_qty_of_items_ordered",
				header: "Items Ordered",
				size: 150,
				minSize: 120,
				cell: ({ row }) => (
					<span className="font-medium">
						{row.original.total_qty_of_items_ordered.toLocaleString()}
					</span>
				),
			},
			{
				accessorKey: "percent_of_cancelled_qty",
				header: "Cancel %",
				size: 120,
				minSize: 100,
				cell: ({ row }) => {
					const percent = row.original.percent_of_cancelled_qty;
					const colorClass = percent > 10 ? "text-red-600" : percent > 5 ? "text-yellow-600" : "text-green-600";
					return (
						<span className={`font-semibold ${colorClass}`}>
							{percent.toFixed(2)}%
						</span>
					);
				},
			},
		],
		[pagination.pageIndex, pagination.pageSize]
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
							Search & Filters
						</Title>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
						<div>
							<Input
								placeholder="Search by name..."
								value={searchName}
								onChange={(e) => setSearchName(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							/>
						</div>
						<div>
							<Select value={filterLocation} onValueChange={setFilterLocation}>
								<SelectTrigger>
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
						<div>
							<Select value={filterWholesale} onValueChange={setFilterWholesale}>
								<SelectTrigger>
									<SelectValue placeholder="All Wholesale" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="all">All Wholesale</SelectItem>
									<SelectItem value="yes">Yes</SelectItem>
									<SelectItem value="no">No</SelectItem>
									<SelectItem value="n/a">N/A</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div>
							<Select value={filterShopify} onValueChange={setFilterShopify}>
								<SelectTrigger>
									<SelectValue placeholder="All Shopify" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="all">All</SelectItem>
									<SelectItem value="true">Shopify</SelectItem>
									<SelectItem value="false">Non-Shopify</SelectItem>
								</SelectContent>
							</Select>
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

			{/* Retailer Table */}
			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-4">
					<CardTitle>
						<Title as="h3" className="text-lg">
							Retailer List ({total.toLocaleString()} total)
						</Title>
					</CardTitle>
					<CardAction>
						<Button
							size="sm"
							variant="outline"
							onClick={() => loadRetailerData()}
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
		</div>
	);
}

