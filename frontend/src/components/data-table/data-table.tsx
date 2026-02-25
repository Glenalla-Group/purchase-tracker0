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
	rowHeight?: number;
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
	rowHeight = 30,
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
		defaultColumn: {
			minSize: 50,
			maxSize: 1000,
		},
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
			<div className="rounded-md border overflow-hidden relative">
				<div className="overflow-x-auto relative">
					{table.getHeaderGroups().length > 0 && (() => {
						const firstHeaderGroup = table.getHeaderGroups()[0];
						const stickyIndices: number[] = [];
						firstHeaderGroup.headers.forEach((header, index) => {
							if ((header.column.columnDef.meta as any)?.sticky) {
								stickyIndices.push(index);
							}
						});
						
						if (stickyIndices.length > 0) {
							const firstStickyIndex = stickyIndices[0];
							// Calculate total width of all sticky columns
							let stickyColumnsWidth = 0;
							for (let i = firstStickyIndex; i < firstHeaderGroup.headers.length; i++) {
								stickyColumnsWidth += firstHeaderGroup.headers[i].getSize();
							}
							
							return (
								<div
									className="sticky left-auto right-0 top-0 bottom-0 w-[2px] bg-gray-400 dark:bg-gray-500 z-[101] pointer-events-none"
									style={{
										right: `${stickyColumnsWidth}px`,
										boxShadow: '0 0 2px rgba(0, 0, 0, 0.1)',
									}}
								/>
							);
						}
						return null;
					})()}
					<table className="w-full border-collapse bg-background" style={{ tableLayout: 'auto', borderSpacing: 0 }}>
						<thead>
								{table.getHeaderGroups().map((headerGroup) => {
									// Find all sticky column indices and calculate their cumulative widths
									const stickyIndices: number[] = [];
									headerGroup.headers.forEach((header, index) => {
										if ((header.column.columnDef.meta as any)?.sticky) {
											stickyIndices.push(index);
										}
									});
									
									// Calculate right offset for each sticky column
									const getStickyRightOffset = (index: number): number => {
										if (!stickyIndices.includes(index)) return 0;
										const stickyIndex = stickyIndices.indexOf(index);
										// Sum widths of all sticky columns to the right of this one
										let offset = 0;
										for (let i = stickyIndex + 1; i < stickyIndices.length; i++) {
											offset += headerGroup.headers[stickyIndices[i]].getSize();
										}
										return offset;
									};
									
									const firstStickyIndex = stickyIndices[0];
									
									// Calculate total width of non-sticky columns for separator positioning
									let nonStickyWidth = 0;
									if (firstStickyIndex !== undefined && firstStickyIndex !== -1) {
										for (let i = 0; i < firstStickyIndex; i++) {
											nonStickyWidth += headerGroup.headers[i].getSize();
										}
									}
									
									return (
									<tr key={headerGroup.id} className="border-b bg-muted/50">
										{headerGroup.headers.map((header, index) => {
											const isSticky = (header.column.columnDef.meta as any)?.sticky;
											const isFirstSticky = isSticky && index === firstStickyIndex;
											const rightOffset = isSticky ? getStickyRightOffset(index) : 0;
											return (
											<th
												key={header.id}
												className={`text-left font-medium text-muted-foreground relative ${
													isSticky ? 'sticky z-[100]' : ''
												} ${
													isFirstSticky ? 'border-l-2 border-gray-400 dark:border-gray-500' : ''
												}`}
												style={{ 
													width: `${header.getSize()}px`,
													minWidth: `${header.getSize()}px`,
													maxWidth: `${header.getSize()}px`,
													right: isSticky ? `${rightOffset}px` : undefined,
													backgroundColor: isSticky ? 'var(--muted)' : undefined,
													boxShadow: isFirstSticky ? '-4px 0 8px -2px rgba(0, 0, 0, 0.15)' : undefined,
													height: '48px',
													paddingLeft: header.column.id === 'select' ? '0px' : '16px',
													paddingRight: header.column.id === 'select' ? '0px' : '16px',
													paddingTop: '12px',
													paddingBottom: '12px',
													verticalAlign: 'middle',
													textAlign: header.column.id === 'select' ? 'center' : 'left',
												}}
											>
											{isSticky && (
												<div
													className="absolute inset-0 pointer-events-none"
													style={{
														backgroundColor: 'var(--muted)',
														zIndex: -1,
														left: isFirstSticky ? '0px' : '-1px',
														right: '-1px',
													}}
												/>
											)}
											{header.isPlaceholder ? null : (
												<div
													className={
														header.column.getCanSort()
															? "flex items-center gap-2 cursor-pointer select-none hover:text-foreground h-full"
															: header.column.id === 'select' 
																? "flex items-center justify-center h-full"
																: "flex items-center h-full"
													}
													onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
													style={{ margin: 0 }}
												>
													{flexRender(header.column.columnDef.header, header.getContext())}
													{header.column.getCanSort() && (
														<span className="ml-auto flex-shrink-0">
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
											{!isSticky && header.column.getCanResize() && (
												<div
													onMouseDown={header.getResizeHandler()}
													onTouchStart={header.getResizeHandler()}
													className={`absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none hover:bg-primary transition-colors ${
														header.column.getIsResizing() ? "bg-primary w-2" : "bg-transparent"
													}`}
													style={{
														userSelect: 'none',
													}}
												/>
											)}
										</th>
									)})}
									</tr>
									);
								})}
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
								table.getRowModel().rows.map((row) => {
									// Find all sticky column indices and calculate their cumulative widths
									const stickyIndices: number[] = [];
									row.getVisibleCells().forEach((cell, index) => {
										if ((cell.column.columnDef.meta as any)?.sticky) {
											stickyIndices.push(index);
										}
									});
									
									// Calculate right offset for each sticky column
									const getStickyRightOffset = (index: number): number => {
										if (!stickyIndices.includes(index)) return 0;
										const stickyIndex = stickyIndices.indexOf(index);
										// Sum widths of all sticky columns to the right of this one
										let offset = 0;
										for (let i = stickyIndex + 1; i < stickyIndices.length; i++) {
											offset += row.getVisibleCells()[stickyIndices[i]].column.getSize();
										}
										return offset;
									};
									
									const firstStickyIndex = stickyIndices[0];
									
									return (
									<tr
										key={row.id}
										className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted group"
										style={{ height: `${rowHeight}px` }}
									>
										{row.getVisibleCells().map((cell, index) => {
											const isSticky = (cell.column.columnDef.meta as any)?.sticky;
											const isFirstSticky = isSticky && index === firstStickyIndex;
											const rightOffset = isSticky ? getStickyRightOffset(index) : 0;
											return (
											<td 
												key={cell.id} 
												className={`relative ${
													isSticky ? 'sticky z-[100]' : ''
												} ${
													isFirstSticky ? 'border-l-2 border-gray-400 dark:border-gray-500' : ''
												}`}
												style={{
													width: `${cell.column.getSize()}px`,
													minWidth: `${cell.column.getSize()}px`,
													maxWidth: `${cell.column.getSize()}px`,
													right: isSticky ? `${rightOffset}px` : undefined,
													backgroundColor: isSticky ? 'var(--background)' : undefined,
													boxShadow: isFirstSticky ? '-4px 0 8px -2px rgba(0, 0, 0, 0.15)' : undefined,
													paddingLeft: cell.column.id === 'select' ? '0px' : '16px',
													paddingRight: cell.column.id === 'select' ? '0px' : '16px',
													paddingTop: '8px',
													paddingBottom: '8px',
													verticalAlign: 'middle',
													textAlign: cell.column.id === 'select' ? 'center' : 'left',
												}}
												onMouseEnter={(e) => {
													if (isSticky) {
														e.currentTarget.style.backgroundColor = 'var(--muted)';
														const bgDiv = e.currentTarget.querySelector('.sticky-bg-extension') as HTMLElement;
														if (bgDiv) bgDiv.style.backgroundColor = 'var(--muted)';
													}
												}}
												onMouseLeave={(e) => {
													if (isSticky) {
														e.currentTarget.style.backgroundColor = 'var(--background)';
														const bgDiv = e.currentTarget.querySelector('.sticky-bg-extension') as HTMLElement;
														if (bgDiv) bgDiv.style.backgroundColor = 'var(--background)';
													}
												}}
											>
											{cell.column.id === 'select' ? (
												<div className="flex items-center justify-center h-full">
													{flexRender(cell.column.columnDef.cell, cell.getContext())}
												</div>
											) : (
												<>
													{isSticky && (
														<div
															className="sticky-bg-extension absolute inset-0 pointer-events-none"
															style={{
																backgroundColor: 'var(--background)',
																zIndex: -1,
																left: isFirstSticky ? '0px' : '-1px',
																right: '-1px',
															}}
														/>
													)}
													{flexRender(cell.column.columnDef.cell, cell.getContext())}
												</>
											)}
											</td>
										)})}
									</tr>
								)})
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

