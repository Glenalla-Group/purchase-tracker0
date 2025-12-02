import { Button } from "@/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Title } from "@/ui/typography";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import asinBankService, { type AsinBankItem } from "@/api/services/asinBankService";
import Icon from "@/components/icon/icon";
import { DataTable } from "@/components/data-table/data-table";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";

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

	// Define table columns
	const columns = useMemo<ColumnDef<AsinBankItem>[]>(
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
		],
		[pagination.pageIndex, pagination.pageSize]
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
		} catch (error: any) {
			console.error("Error loading ASIN data:", error);
			toast.error("Failed to load ASIN data", {
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
						<Button
							size="sm"
							variant="outline"
							onClick={() => loadAsinData()}
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
		</div>
	);
}
