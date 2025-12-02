import {
	flexRender,
	getCoreRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	type ColumnDef,
	type ColumnResizeMode,
	type PaginationState,
	type SortingState,
	useReactTable,
} from "@tanstack/react-table";
import { useState, useEffect } from "react";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import Icon from "@/components/icon/icon";

interface DataTableProps<TData, TValue> {
	columns: ColumnDef<TData, TValue>[];
	data: TData[];
	pageCount?: number;
	pageIndex?: number;
	pageSize?: number;
	totalItems?: number;
	onPaginationChange?: (pagination: PaginationState) => void;
	manualPagination?: boolean;
	loading?: boolean;
}

export function DataTable<TData, TValue>({
	columns,
	data,
	pageCount = -1,
	pageIndex = 0,
	pageSize = 10,
	totalItems = 0,
	onPaginationChange,
	manualPagination = false,
	loading = false,
}: DataTableProps<TData, TValue>) {
	const [sorting, setSorting] = useState<SortingState>([]);
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex,
		pageSize,
	});
	const [columnResizeMode] = useState<ColumnResizeMode>("onChange");
	const [pageInputValue, setPageInputValue] = useState<string>((pagination.pageIndex + 1).toString());

	// Sync input value when pagination changes
	useEffect(() => {
		setPageInputValue((pagination.pageIndex + 1).toString());
	}, [pagination.pageIndex]);

	const table = useReactTable({
		data,
		columns,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		getSortedRowModel: getSortedRowModel(),
		onSortingChange: setSorting,
		onPaginationChange: (updater) => {
			const newPagination = typeof updater === "function" ? updater(pagination) : updater;
			setPagination(newPagination);
			onPaginationChange?.(newPagination);
		},
		manualPagination,
		pageCount,
		columnResizeMode,
		enableColumnResizing: true,
		state: {
			sorting,
			pagination,
		},
	});

	const startIndex = pagination.pageIndex * pagination.pageSize + 1;
	const endIndex = Math.min((pagination.pageIndex + 1) * pagination.pageSize, totalItems || data.length);
	const totalCount = totalItems || data.length;

	return (
		<div className="space-y-4">
			{/* Table */}
			<div className="rounded-md border overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full">
						<thead>
							{table.getHeaderGroups().map((headerGroup) => (
								<tr key={headerGroup.id} className="border-b bg-muted/50">
									{headerGroup.headers.map((header) => (
										<th
											key={header.id}
											className="h-12 px-4 text-left align-middle font-medium text-muted-foreground relative"
											style={{ width: header.getSize() }}
										>
											{header.isPlaceholder ? null : (
												<div
													className={
														header.column.getCanSort()
															? "flex items-center gap-2 cursor-pointer select-none hover:text-foreground"
															: ""
													}
													onClick={header.column.getToggleSortingHandler()}
												>
													{flexRender(header.column.columnDef.header, header.getContext())}
													{header.column.getCanSort() && (
														<span className="ml-auto">
															{{
																asc: <Icon icon="mdi:arrow-up" size={16} />,
																desc: <Icon icon="mdi:arrow-down" size={16} />,
															}[header.column.getIsSorted() as string] ?? (
																<Icon icon="mdi:unfold-more-horizontal" size={16} className="opacity-50" />
															)}
														</span>
													)}
												</div>
											)}
											{/* Column Resizer */}
											<div
												onMouseDown={header.getResizeHandler()}
												onTouchStart={header.getResizeHandler()}
												className={`absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none hover:bg-primary ${
													header.column.getIsResizing() ? "bg-primary" : ""
												}`}
											/>
										</th>
									))}
								</tr>
							))}
						</thead>
						<tbody>
							{loading ? (
								<tr>
									<td colSpan={columns.length} className="h-64 text-center">
										<div className="flex items-center justify-center">
											<Icon icon="mdi:loading" className="animate-spin text-4xl text-muted-foreground" />
										</div>
									</td>
								</tr>
							) : table.getRowModel().rows?.length ? (
								table.getRowModel().rows.map((row) => (
									<tr
										key={row.id}
										className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted"
									>
										{row.getVisibleCells().map((cell) => (
											<td key={cell.id} className="p-4 align-middle">
												{flexRender(cell.column.columnDef.cell, cell.getContext())}
											</td>
										))}
									</tr>
								))
							) : (
								<tr>
									<td colSpan={columns.length} className="h-64 text-center">
										<div className="flex flex-col items-center justify-center text-muted-foreground">
											<Icon icon="mdi:database-off" className="text-6xl mb-4 opacity-50" />
											<p className="text-lg font-medium">No results found</p>
											<p className="text-sm">Try adjusting your filters</p>
										</div>
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{/* Pagination Controls */}
			<div className="flex flex-col sm:flex-row items-center justify-between gap-4">
				{/* Results Info */}
				<div className="text-sm text-muted-foreground">
					Showing <span className="font-medium">{startIndex}</span> to{" "}
					<span className="font-medium">{endIndex}</span> of{" "}
					<span className="font-medium">{totalCount}</span> results
				</div>

				<div className="flex items-center gap-4">
					{/* Page Size Selector */}
					<div className="flex items-center gap-2">
						<span className="text-sm text-muted-foreground">Rows per page:</span>
						<Select
							value={pagination.pageSize.toString()}
							onValueChange={(value) => {
								table.setPageSize(Number(value));
							}}
						>
							<SelectTrigger className="h-8 w-[70px]">
								<SelectValue placeholder={pagination.pageSize} />
							</SelectTrigger>
							<SelectContent side="top">
								{[10, 20, 30, 50, 100].map((pageSize) => (
									<SelectItem key={pageSize} value={pageSize.toString()}>
										{pageSize}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>

					{/* Page Navigation */}
					<div className="flex items-center gap-2">
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								table.setPageIndex(0);
								setPageInputValue("1");
							}}
							disabled={!table.getCanPreviousPage() || loading}
						>
							<Icon icon="mdi:chevron-double-left" />
						</Button>
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								table.previousPage();
								setPageInputValue((pagination.pageIndex).toString());
							}}
							disabled={!table.getCanPreviousPage() || loading}
						>
							<Icon icon="mdi:chevron-left" />
						</Button>
						
						{/* Editable Page Number */}
						<div className="flex items-center gap-2">
							<span className="text-sm text-muted-foreground">Page</span>
							<Input
								type="number"
								min="1"
								max={table.getPageCount()}
								value={pageInputValue}
								onChange={(e) => setPageInputValue(e.target.value)}
								onBlur={() => {
									const page = Number(pageInputValue);
									if (page >= 1 && page <= table.getPageCount()) {
										table.setPageIndex(page - 1);
									} else {
										// Reset to current page if invalid
										setPageInputValue((pagination.pageIndex + 1).toString());
									}
								}}
								onKeyDown={(e) => {
									if (e.key === "Enter") {
										const page = Number(pageInputValue);
										if (page >= 1 && page <= table.getPageCount()) {
											table.setPageIndex(page - 1);
										} else {
											setPageInputValue((pagination.pageIndex + 1).toString());
										}
									}
								}}
								className="h-8 w-[60px] text-center"
								disabled={loading}
							/>
							<span className="text-sm text-muted-foreground">of {table.getPageCount()}</span>
						</div>
						
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								table.nextPage();
								setPageInputValue((pagination.pageIndex + 2).toString());
							}}
							disabled={!table.getCanNextPage() || loading}
						>
							<Icon icon="mdi:chevron-right" />
						</Button>
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								table.setPageIndex(table.getPageCount() - 1);
								setPageInputValue(table.getPageCount().toString());
							}}
							disabled={!table.getCanNextPage() || loading}
						>
							<Icon icon="mdi:chevron-double-right" />
						</Button>
					</div>
				</div>
			</div>
		</div>
	);
}

