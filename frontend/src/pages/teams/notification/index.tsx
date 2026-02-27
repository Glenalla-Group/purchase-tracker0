import { useState, useMemo } from "react";
import { Icon } from "@/components/icon";
import { Badge } from "@/ui/badge";
import { Card, CardContent } from "@/ui/card";
import { Button } from "@/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/ui/tooltip";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import emailManualReviewService, {
	type ManualReviewEntry,
	type ResolvePayload,
} from "@/api/services/emailManualReviewService";
import { DataTable } from "@/components/data-table";
import type { ColumnDef } from "@tanstack/react-table";

export default function NotificationPage() {
	const queryClient = useQueryClient();

	const { data, isLoading } = useQuery({
		queryKey: ["email-manual-review"],
		queryFn: () => emailManualReviewService.list({ status: "pending", limit: 100 }),
	});

	const [selectedEntry, setSelectedEntry] = useState<ManualReviewEntry | null>(null);
	const [resolveForm, setResolveForm] = useState<ResolvePayload>({});
	const [resolveLoading, setResolveLoading] = useState(false);

	const resolveMutation = useMutation({
		mutationFn: ({ id, payload }: { id: number; payload: ResolvePayload }) =>
			emailManualReviewService.resolve(id, payload),
		onSuccess: () => {
			toast.success("Processed successfully");
			queryClient.invalidateQueries({ queryKey: ["email-manual-review"] });
			queryClient.invalidateQueries({ queryKey: ["email-manual-review-count"] });
			setSelectedEntry(null);
			setResolveForm({});
		},
		onError: (err: Error) => {
			toast.error(err.message || "Failed to process");
		},
	});

	const dismissMutation = useMutation({
		mutationFn: (id: number) => emailManualReviewService.dismiss(id),
		onSuccess: () => {
			toast.success("Entry dismissed");
			queryClient.invalidateQueries({ queryKey: ["email-manual-review"] });
			queryClient.invalidateQueries({ queryKey: ["email-manual-review-count"] });
			setSelectedEntry(null);
		},
		onError: (err: Error) => {
			toast.error(err.message || "Failed to dismiss");
		},
	});

	const handleResolve = () => {
		if (!selectedEntry) return;
		const missing = selectedEntry.missing_fields || [];
		// When no missing fields, data is complete (e.g. no matching records) - resolve with empty payload
		if (missing.length === 0) {
			setResolveLoading(true);
			resolveMutation.mutate(
				{ id: selectedEntry.id, payload: {} },
				{ onSettled: () => setResolveLoading(false) }
			);
			return;
		}
		if (missing.includes("order_number") && !resolveForm.order_number && !selectedEntry.extracted_order_number) {
			toast.error("Order number is required");
			return;
		}
		const hasMultiItem =
			(selectedEntry.retailer === "shopwss" || selectedEntry.retailer === "shoepalace") &&
			selectedEntry.email_type === "cancellation" &&
			missing.includes("unique_id") &&
			(resolveForm.items?.length ?? 0) > 1;
		if (missing.includes("unique_id") && !hasMultiItem && (!resolveForm.unique_id || !resolveForm.size)) {
			toast.error("Unique ID and size are required");
			return;
		}
		if (hasMultiItem && resolveForm.items) {
			const invalid = resolveForm.items.some((it) => !it.unique_id || !it.size);
			if (invalid) {
				toast.error("Each item must have Unique ID and size");
				return;
			}
		}
		const payload: ResolvePayload = {
			order_number: resolveForm.order_number ?? selectedEntry.extracted_order_number,
			...(hasMultiItem && resolveForm.items
				? { items: resolveForm.items.map((it) => ({ unique_id: it.unique_id!, size: it.size!, quantity: it.quantity ?? 1 })) }
				: {
						unique_id: resolveForm.unique_id,
						size: resolveForm.size,
						quantity: resolveForm.quantity ?? 1,
					}),
		};
		setResolveLoading(true);
		resolveMutation.mutate(
			{ id: selectedEntry.id, payload },
			{ onSettled: () => setResolveLoading(false) }
		);
	};

	const items = data?.items ?? [];
	const missingLabels: Record<string, string> = {
		order_number: "Order #",
		unique_id: "Unique ID",
	};

	const columns = useMemo<ColumnDef<ManualReviewEntry>[]>(
		() => [
			{
				accessorKey: "retailer",
				header: "Retailer",
				size: 110,
				minSize: 100,
				cell: ({ row }) => {
					const r = row.original;
					const gmailUrl = `https://mail.google.com/mail/#all/${r.gmail_message_id}`;
					return (
						<div className="flex items-center gap-1.5">
							<span className="capitalize">{r.retailer}</span>
							<Tooltip>
								<TooltipTrigger asChild>
									<a
										href={gmailUrl}
										target="_blank"
										rel="noopener noreferrer"
										className="inline-flex text-muted-foreground hover:text-foreground transition-colors"
										onClick={(e) => e.stopPropagation()}
									>
										<Icon icon="logos:google-gmail" size={16} />
									</a>
								</TooltipTrigger>
								<TooltipContent side="top">Open in Gmail</TooltipContent>
							</Tooltip>
						</div>
					);
				},
			},
			{
				accessorKey: "email_type",
				header: "Type",
				size: 100,
				minSize: 90,
			},
			{
				accessorKey: "subject",
				header: "Subject",
				size: 220,
				minSize: 160,
				cell: ({ row }) => (
					<Tooltip>
						<TooltipTrigger asChild>
							<span className="block truncate cursor-default" title={row.original.subject}>
								{row.original.subject ?? "-"}
							</span>
						</TooltipTrigger>
						<TooltipContent side="top" className="max-w-sm whitespace-normal break-words">
							{row.original.subject ?? ""}
						</TooltipContent>
					</Tooltip>
				),
			},
			{
				id: "extracted",
				header: "Extracted",
				size: 150,
				minSize: 100,
				cell: ({ row }) => {
					const r = row.original;
					return (
						<div className="text-sm space-y-1">
							{r.extracted_order_number && <span>Order: {r.extracted_order_number}</span>}
							{r.extracted_items?.length ? (
								<div>
									{r.extracted_items.map((it, i) => (
										<span key={i} className="block">
											{it.unique_id} / {it.size}
											{it.product_name ? ` (${it.product_name})` : ""}
										</span>
									))}
								</div>
							) : null}
							{!r.extracted_order_number && !r.extracted_items?.length && "-"}
						</div>
					);
				},
			},
			{
				id: "missing",
				header: "Missing",
				size: 140,
				minSize: 100,
				cell: ({ row }) => (
					<div className="flex flex-wrap gap-1">
						{(row.original.missing_fields || []).map((f) => (
							<Badge key={f} variant="outline">
								{f}
							</Badge>
						))}
					</div>
				),
			},
			{
				accessorKey: "created_at",
				header: "Created",
				size: 110,
				minSize: 90,
				cell: ({ row }) => (
					<span className="text-sm text-muted-foreground">
						{row.original.created_at ? new Date(row.original.created_at).toLocaleDateString() : "-"}
					</span>
				),
			},
			{
				id: "actions",
				header: "Actions",
				size: 180,
				minSize: 140,
				cell: ({ row }) => (
					<div className="flex gap-2">
						<Button
							size="sm"
							variant="default"
							onClick={() => {
								const entry = row.original;
								setSelectedEntry(entry);
								const missing = entry.missing_fields || [];
								const hasMultiItem =
									(entry.retailer === "shopwss" || entry.retailer === "shoepalace") &&
									entry.email_type === "cancellation" &&
									missing.includes("unique_id") &&
									(entry.extracted_items?.length ?? 0) > 1;
								if (hasMultiItem && entry.extracted_items) {
									setResolveForm({
										items: entry.extracted_items.map((it) => ({
											product_name: it.product_name,
											size: it.size ?? "",
											quantity: it.quantity ?? 1,
											unique_id: "",
										})),
									});
								} else {
									const first = entry.extracted_items?.[0];
									setResolveForm({
										quantity: first?.quantity ?? 1,
										size: first?.size ?? "",
									});
								}
							}}
						>
							Resolve
						</Button>
						<Button
							size="sm"
							variant="outline"
							onClick={() => dismissMutation.mutate(row.original.id)}
						>
							Dismiss
						</Button>
					</div>
				),
			},
		],
		[dismissMutation]
	);

	return (
		<div className="flex flex-col gap-4 p-2">
			<div>
				<h1 className="text-2xl font-semibold">Manual Review</h1>
				<p className="text-muted-foreground mt-1">
					Emails that need manual data entry (e.g. Revolve cancellation with missing order# or unique ID)
				</p>
			</div>

			{isLoading ? (
				<div className="text-muted-foreground">Loading...</div>
			) : items.length === 0 ? (
				<div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
					<Icon icon="solar:bell-bing-bold-duotone" size={48} className="mx-auto mb-4 opacity-50" />
					<p className="font-medium">No pending items</p>
					<p className="text-sm mt-1">When Revolve cancellations fail to parse, they will appear here.</p>
				</div>
			) : (
				<Card className="py-2">
					<CardContent className="px-2 py-1">
						<DataTable
							columns={columns}
							data={items}
							loading={isLoading}
						/>
					</CardContent>
				</Card>
			)}

			<Dialog open={!!selectedEntry} onOpenChange={(open) => !open && setSelectedEntry(null)}>
				<DialogContent className="sm:max-w-[480px]">
					<DialogHeader>
						<DialogTitle>Resolve Manual Review</DialogTitle>
						<DialogDescription>
							{(selectedEntry?.missing_fields || []).length === 0
								? "All data is available. Click Process to re-apply (e.g. after order confirmation is processed)."
								: selectedEntry?.email_type === "shipping"
									? "Fill in unique ID and size, then click Process to update shipped status."
									: (selectedEntry?.missing_fields || []).includes("order_number") &&
									  !(selectedEntry?.missing_fields || []).includes("unique_id")
										? "Enter order number to cancel all items for this order."
										: "Fill in the missing fields and click Process to apply the cancellation."}
						</DialogDescription>
					</DialogHeader>
					{selectedEntry && (
						<div className="space-y-4 py-4">
							{selectedEntry.extracted_order_number && (
								<p className="text-sm">
									<strong>Order #:</strong> {selectedEntry.extracted_order_number}
								</p>
							)}
							{selectedEntry.extracted_items && selectedEntry.extracted_items.length > 0 && (
								<div className="space-y-2">
									<strong className="text-sm">Extracted items</strong>
									<ul className="space-y-2 text-sm">
										{selectedEntry.extracted_items.map((it, i) => (
											<li
												key={i}
												className="rounded-md border bg-muted/30 px-3 py-2"
											>
												{it.product_name && (
													<div className="font-medium text-foreground">{it.product_name}</div>
												)}
												<div className="flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground">
													{it.unique_id != null && <span>ID: {it.unique_id}</span>}
													{it.size != null && <span>Size: {it.size}</span>}
													{it.product_number != null && <span>Product #: {it.product_number}</span>}
													{it.color != null && <span>Color: {it.color}</span>}
													<span>Qty: {it.quantity ?? 1}</span>
												</div>
											</li>
										))}
									</ul>
								</div>
							)}
							{(selectedEntry.missing_fields || []).map((field) => (
								<div key={field}>
									{/* Skip size when unique_id is also missing - we render both together */}
									{field === "size" && (selectedEntry.missing_fields || []).includes("unique_id") ? null : (
								<div className="space-y-2">
									{field !== "unique_id" && (
										<Label htmlFor={field}>
											{missingLabels[field] || field} <span className="text-destructive">*</span>
										</Label>
									)}
									{field === "order_number" && (
										<Input
											id={field}
											placeholder={
												selectedEntry?.retailer === "snipes"
													? "e.g. SNP15751775"
													: "e.g. 341221096"
											}
											value={resolveForm.order_number ?? ""}
											onChange={(e) => setResolveForm({ ...resolveForm, order_number: e.target.value })}
										/>
									)}
									{field === "unique_id" && (
										<>
											{(selectedEntry.retailer === "shopwss" ||
												selectedEntry.retailer === "shoepalace") &&
											(selectedEntry.extracted_items?.length ?? 0) > 1 &&
											resolveForm.items ? (
												<div className="space-y-3">
													<Label>Enter Unique ID per item</Label>
													{resolveForm.items.map((it, i) => (
														<div
															key={i}
															className="rounded-md border bg-muted/30 px-3 py-2 space-y-2"
														>
															{it.product_name && (
																<div className="font-medium text-sm">{it.product_name}</div>
															)}
															<div className="flex gap-2 items-end flex-wrap">
																<div className="flex-1 min-w-[100px]">
																	<Label className="text-xs text-muted-foreground">Size</Label>
																	<div className="text-sm py-1">{it.size}</div>
																</div>
																<div className="flex-1 min-w-[120px]">
																	<Label className="text-xs text-muted-foreground">
																		Unique ID <span className="text-destructive">*</span>
																	</Label>
																	<Input
																		placeholder="e.g. dv1308_104"
																		value={it.unique_id ?? ""}
																		onChange={(e) => {
																			const next = [...(resolveForm.items ?? [])];
																			next[i] = { ...next[i], unique_id: e.target.value };
																			setResolveForm({ ...resolveForm, items: next });
																		}}
																	/>
																</div>
																<div className="w-16">
																	<Label className="text-xs text-muted-foreground">Qty</Label>
																	<Input
																		type="number"
																		min={1}
																		value={it.quantity ?? 1}
																		onChange={(e) => {
																			const next = [...(resolveForm.items ?? [])];
																			next[i] = {
																				...next[i],
																				quantity: parseInt(e.target.value, 10) || 1,
																			};
																			setResolveForm({ ...resolveForm, items: next });
																		}}
																	/>
																</div>
															</div>
														</div>
													))}
												</div>
											) : (
												<>
													<div className="space-y-2">
														<Label htmlFor="unique_id">
															Unique ID <span className="text-destructive">*</span>
														</Label>
														<Input
															id="unique_id"
															placeholder="e.g. ONF-MZ454"
															value={resolveForm.unique_id ?? ""}
															onChange={(e) => setResolveForm({ ...resolveForm, unique_id: e.target.value })}
														/>
													</div>
													<div className="space-y-2">
														<Label htmlFor="size">
															Size <span className="text-destructive">*</span>
														</Label>
														<Input
															id="size"
															placeholder="e.g. 11"
															value={resolveForm.size ?? ""}
															onChange={(e) => setResolveForm({ ...resolveForm, size: e.target.value })}
														/>
													</div>
													<div className="space-y-2">
														<Label htmlFor="quantity">Quantity</Label>
														<Input
															id="quantity"
															type="number"
															min={1}
															placeholder="1"
															value={resolveForm.quantity ?? 1}
															onChange={(e) =>
																setResolveForm({ ...resolveForm, quantity: parseInt(e.target.value, 10) || 1 })
															}
														/>
													</div>
												</>
											)}
										</>
									)}
								</div>
									)}
								</div>
							))}
						</div>
					)}
					<DialogFooter>
						<Button variant="outline" onClick={() => setSelectedEntry(null)} disabled={resolveLoading}>
							Cancel
						</Button>
						<Button onClick={handleResolve} disabled={resolveLoading}>
							{resolveLoading
								? "Processing..."
								: selectedEntry?.email_type === "shipping"
									? "Process Shipping Update"
									: "Process Cancellation"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
