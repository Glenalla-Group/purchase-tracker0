import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/ui/form";
import { Input } from "@/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Textarea } from "@/ui/textarea";
import { Title, Text } from "@/ui/typography";
import { Separator } from "@/ui/separator";
import { Combobox } from "@/ui/combobox";
import { MultiSelect } from "@/ui/multi-select";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import leadService from "@/api/services/leadService";
import retailerService, { type RetailerItem } from "@/api/services/retailerService";
import Icon from "@/components/icon/icon";

// Utility function to extract unique ID from retailer links
const extractUniqueIdFromUrl = (url: string): string => {
	if (!url) return "";
	
	try {
		const urlLower = url.toLowerCase();
		
		// FootLocker pattern: /product/~/HJ7395.html or /product/~/~/6789122.html
		if (urlLower.includes("footlocker.com")) {
			const match = url.match(/\/product\/~\/(?:~\/)?([^/]+)\.html/);
			if (match && match[1]) {
				return match[1];
			}
		}
		
		// Champ Sports pattern: /product/~/ID0436.html
		if (urlLower.includes("champssports.com")) {
			const match = url.match(/\/product\/~\/([^/]+)\.html/);
			if (match && match[1]) {
				return match[1];
			}
		}
		
		// Finish Line pattern: /HV6417/001 -> convert to HV6417_001
		if (urlLower.includes("finishline.com")) {
			const match = url.match(/\/([A-Z0-9]+)\/(\d+)/i);
			if (match && match[1] && match[2]) {
				return `${match[1]}_${match[2]}`;
			}
		}
		
		// Hibbett pattern: /G2380.html
		if (urlLower.includes("hibbett.com")) {
			const match = url.match(/\/([^/]+)\.html/);
			if (match && match[1]) {
				return match[1];
			}
		}
		
		return "";
	} catch (error) {
		console.error("Error extracting unique ID from URL:", error);
		return "";
	}
};

// Schema for form validation
const leadSubmittalSchema = z.object({
	submittedBy: z.string().min(1, "Please select who submitted this"),
	productName: z.string().min(1, "Product name is required"),
	productSku: z.string().min(1, "Product SKU is required"),
	retailerLink: z.string().url("Please enter a valid URL").or(z.string().length(0)),
	retailerName: z.string().min(1, "Please select a retailer"),
	amazonLink: z.string().url("Please enter a valid URL").or(z.string().length(0)),
	uniqueId: z.string().optional(),
	ppu: z.string().min(1, "PPU is required"),
	rsp: z.string().min(1, "RSP is required"),
	margin: z.string().min(1, "Margin is required"),
	pros: z.array(z.string()).min(1, "Please select at least one pro"),
	cons: z.array(z.string()).min(1, "Please select at least one con"),
	otherNotes: z.string().optional(),
	promoCode: z.string().optional(),
	asins: z.array(
		z.object({
			asin: z.string().optional(),
			size: z.string().optional(),
			recommendedQuantity: z.string().optional(),
		}),
	),
});

type LeadSubmittalFormValues = z.infer<typeof leadSubmittalSchema>;

// Sample data for dropdowns
const submittedByOptions = [
	{ value: "Griffin", label: "Griffin" },
	{ value: "Rocky", label: "Rocky" },
	{ value: "Carlo", label: "Carlo" }
];

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

export default function LeadSubmittal() {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [asinCount, setAsinCount] = useState(10); // Start with 10 ASINs
	const [asinAmountInput, setAsinAmountInput] = useState("5"); // Default input value
	const [retailers, setRetailers] = useState<Array<{ value: string; label: string }>>([]);
	const [loadingRetailers, setLoadingRetailers] = useState(true);

	const form = useForm<LeadSubmittalFormValues>({
		resolver: zodResolver(leadSubmittalSchema),
		defaultValues: {
			submittedBy: "",
			productName: "",
			productSku: "",
			retailerLink: "",
			retailerName: "",
			amazonLink: "",
			uniqueId: "",
			ppu: "",
			rsp: "",
			margin: "",
			pros: [],
			cons: [],
			otherNotes: "",
			promoCode: "",
			asins: Array.from({ length: 50 }, () => ({
				asin: "",
				size: "",
				recommendedQuantity: "",
			})),
		},
	});

	// Load retailers from API
	useEffect(() => {
		const loadRetailers = async () => {
			try {
				setLoadingRetailers(true);
				const response = await retailerService.getRetailers({ skip: 0, limit: 1000 });
				
				// Convert retailers to dropdown options
				const retailerOptions = response.items.map((retailer: RetailerItem) => ({
					value: retailer.name,
					label: retailer.name
				})).sort((a, b) => a.label.localeCompare(b.label));
				
				setRetailers(retailerOptions);
			} catch (error) {
				console.error("Error loading retailers:", error);
				toast.error("Failed to load retailers", {
					description: "Using default retailer list"
				});
				// Fallback to a minimal list if API fails
				setRetailers([
					{ value: "Other", label: "Other" }
				]);
			} finally {
				setLoadingRetailers(false);
			}
		};

		loadRetailers();
	}, []);

	// Function to add multiple ASIN fields based on input
	const handleAddAsins = () => {
		const amount = Number.parseInt(asinAmountInput, 10);
		if (!Number.isNaN(amount) && amount > 0) {
			setAsinCount(asinCount + amount);
		}
	};

	// Function to remove a specific ASIN row
	const handleDeleteAsin = (indexToDelete: number) => {
		// Clear the values for that ASIN
		form.setValue(`asins.${indexToDelete}.asin`, "");
		form.setValue(`asins.${indexToDelete}.size`, "");
		form.setValue(`asins.${indexToDelete}.recommendedQuantity`, "");
		
		// Shift all ASINs after the deleted one up by one position
		for (let i = indexToDelete; i < asinCount - 1; i++) {
			const nextAsin = form.getValues(`asins.${i + 1}`);
			form.setValue(`asins.${i}.asin`, nextAsin.asin || "");
			form.setValue(`asins.${i}.size`, nextAsin.size || "");
			form.setValue(`asins.${i}.recommendedQuantity`, nextAsin.recommendedQuantity || "");
		}
		
		// Clear the last ASIN row
		form.setValue(`asins.${asinCount - 1}.asin`, "");
		form.setValue(`asins.${asinCount - 1}.size`, "");
		form.setValue(`asins.${asinCount - 1}.recommendedQuantity`, "");
		
		// Decrease the count
		setAsinCount(asinCount - 1);
	};

	// Function to load data from Chrome Extension
	const loadDataFromExtension = (data: {
		asins: Array<{ asin: string; size: string; quantity: string }>;
		retailerLink?: string;
		amazonLink?: string;
	}) => {
		console.log("Loading data from extension:", data);

		// Fill retailer link if provided
		if (data.retailerLink && data.retailerLink.trim() !== "") {
			form.setValue("retailerLink", data.retailerLink);
			console.log("Set retailer link:", data.retailerLink);
		}

		// Fill amazon link if provided
		if (data.amazonLink && data.amazonLink.trim() !== "") {
			form.setValue("amazonLink", data.amazonLink);
			console.log("Set amazon link:", data.amazonLink);
		}

		// Fill ASIN data
		if (data.asins && data.asins.length > 0) {
			// Set the ASIN count to match the incoming data
			setAsinCount(data.asins.length);

			// Populate each ASIN field
			data.asins.forEach((asinData, index) => {
				form.setValue(`asins.${index}.asin`, asinData.asin || "");
				form.setValue(`asins.${index}.size`, asinData.size || "");
				form.setValue(`asins.${index}.recommendedQuantity`, asinData.quantity || "");
			});

			console.log(`Loaded ${data.asins.length} ASINs from extension`);
		}

		// Show success notification
		showSuccessNotification(`✅ Loaded data from extension: ${data.asins?.length || 0} ASINs`);
	};

	// Function to show success notification
	const showSuccessNotification = (message: string) => {
		// Create a temporary notification element
		const notification = document.createElement("div");
		notification.textContent = message;
		notification.style.cssText = `
			position: fixed;
			top: 20px;
			right: 20px;
			padding: 16px 24px;
			background: #d4edda;
			color: #155724;
			border: 2px solid #c3e6cb;
			border-radius: 8px;
			font-weight: bold;
			font-size: 14px;
			z-index: 100000;
			box-shadow: 0 4px 20px rgba(0,0,0,0.3);
			animation: slideIn 0.3s ease-out;
		`;
		document.body.appendChild(notification);

		// Remove after 5 seconds
		setTimeout(() => {
			notification.style.animation = "slideOut 0.3s ease-in";
			setTimeout(() => notification.remove(), 300);
		}, 5000);
	};

	// Listen for messages from Chrome Extension
	useEffect(() => {
		const handleExtensionMessage = (event: MessageEvent) => {
			// Verify the message is from your extension
			if (event.data && event.data.type === "ASIN_DATA_FROM_EXTENSION") {
				console.log("Received data from extension:", event.data);
				loadDataFromExtension({
					asins: event.data.asins || [],
					retailerLink: event.data.retailerLink,
					amazonLink: event.data.amazonLink,
				});
			}
		};

		// Listen for postMessage from extension
		window.addEventListener("message", handleExtensionMessage);

		// Cleanup listener on unmount
		return () => {
			window.removeEventListener("message", handleExtensionMessage);
		};
	}, [form]);

	// Auto-populate Unique ID based on retailer link
	useEffect(() => {
		const subscription = form.watch((value, { name }) => {
			if (name === "retailerLink") {
				const retailerLink = value.retailerLink || "";
				
				if (retailerLink.trim() === "") {
					// Clear unique ID when retailer link is removed
					form.setValue("uniqueId", "");
				} else {
					const suggestedId = extractUniqueIdFromUrl(retailerLink);
					
					// Update with suggested ID if found, or clear if no pattern matches
					form.setValue("uniqueId", suggestedId);
				}
			}
		});
		
		return () => subscription.unsubscribe();
	}, [form]);

	const onSubmit = async (data: LeadSubmittalFormValues) => {
		setIsSubmitting(true);
		try {
		// Filter out empty ASIN entries
		const filteredAsins = data.asins.filter(
			(asin) => asin.asin || asin.size || asin.recommendedQuantity,
		);
		
		// Prepare data for backend (convert recommendedQuantity to number, join pros/cons arrays)
		const submitData = {
			submittedBy: data.submittedBy,
			productName: data.productName,
			productSku: data.productSku,
			retailerLink: data.retailerLink || undefined,
			retailerName: data.retailerName,
			amazonLink: data.amazonLink || undefined,
			uniqueId: data.uniqueId || undefined,
			ppu: data.ppu,
			rsp: data.rsp,
			margin: data.margin,
			pros: data.pros.join(", "),  // Join array into comma-separated string
			cons: data.cons.join(", "),  // Join array into comma-separated string
			otherNotes: data.otherNotes || undefined,
			promoCode: data.promoCode || undefined,
			asins: filteredAsins.map(asin => ({
				asin: asin.asin,
				size: asin.size,
				recommendedQuantity: asin.recommendedQuantity 
					? parseInt(asin.recommendedQuantity, 10) 
					: undefined
			})),
		};
			
			console.log("Submitting to backend:", submitData);
			
			// Call backend API
			const response = await leadService.submitLead(submitData);
			
			console.log("Backend response:", response);
			
			// Show success message
			const asinMessage = response.asins_reused > 0
				? `${response.asins_created} new, ${response.asins_reused} reused (${response.total_asins} total)`
				: `${response.asins_created} ASINs created`;
			
			toast.success(
				`Lead submitted successfully! Lead ID: ${response.lead_id}`,
				{
					description: `${asinMessage} | Total quantity: ${response.total_suggested_qty}`,
					duration: 5000,
				}
			);
			
			// Reset form after successful submission
			form.reset();
			setAsinCount(10); // Reset ASIN count to default
			
		} catch (error: any) {
			console.error("Error submitting form:", error);
			
			// Show error message
			toast.error("Failed to submit lead", {
				description: error?.message || "Please try again or contact support.",
				duration: 5000,
			});
		} finally {
			setIsSubmitting(false);
		}
	};

	// Handler for validation errors (when form is invalid)
	const onInvalid = (errors: any) => {
		console.log("Form validation errors:", errors);
		
		// Count the number of errors
		const errorCount = Object.keys(errors).length;
		
		// Show error notification
		toast.error("Form validation failed", {
			description: `Please fill in all required fields. ${errorCount} error${errorCount > 1 ? 's' : ''} found.`,
			duration: 5000,
		});
	};

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<div className="flex flex-col gap-2">
				<Title as="h2" className="text-2xl">
					Lead Submittal Form
				</Title>
				<Text variant="body2" className="text-muted-foreground">
					Submit a new product lead with all relevant details and ASIN information
				</Text>
			</div>

			<Form {...form}>
				<form onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-6">
					{/* Basic Information Card */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Icon icon="mdi:information" size={20} />
								Basic Information
							</CardTitle>
						</CardHeader>
						<CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<FormField
								control={form.control}
								name="submittedBy"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Submitted By *</FormLabel>
										<Select onValueChange={field.onChange} value={field.value}>
											<FormControl>
												<SelectTrigger className="w-1/2">
													<SelectValue placeholder="Select submitter" />
												</SelectTrigger>
											</FormControl>
											<SelectContent>
												{submittedByOptions.map((option) => (
													<SelectItem key={option.value} value={option.value}>
														{option.label}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="productName"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Product Name *</FormLabel>
										<FormControl>
											<Input placeholder="Enter product name" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

					<FormField
						control={form.control}
						name="retailerName"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Retailer Name *</FormLabel>
								<FormControl>
									<Combobox
										options={retailers}
										value={field.value}
										onValueChange={field.onChange}
										placeholder={loadingRetailers ? "Loading retailers..." : "Select retailer"}
										searchPlaceholder="Search retailers..."
										emptyText="No retailer found."
										disabled={loadingRetailers}
										className="w-1/2"
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

							<FormField
								control={form.control}
								name="productSku"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Product SKU *</FormLabel>
										<FormControl>
											<Input placeholder="Enter product SKU" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="retailerLink"
								render={({ field }) => (
									<FormItem className="md:col-span-2">
										<FormLabel>Retailer Link</FormLabel>
										<FormControl>
											<Input placeholder="https://example.com/product" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

						<FormField
							control={form.control}
							name="amazonLink"
							render={({ field }) => (
								<FormItem className="md:col-span-2">
									<FormLabel>Amazon Link</FormLabel>
									<FormControl>
										<Input placeholder="https://amazon.com/product" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="uniqueId"
							render={({ field }) => (
								<FormItem className="md:col-span-2">
									<FormLabel>Unique ID (Image URL)</FormLabel>
									<FormControl>
										<Input 
											placeholder="Auto-filled from retailer link (editable)" 
											{...field} 
										/>
									</FormControl>
									<Text variant="body2" className="text-xs text-muted-foreground mt-1">
										This field is automatically populated from the retailer link but can be edited manually.
									</Text>
									<FormMessage />
								</FormItem>
							)}
						/>
					</CardContent>
				</Card>

					{/* Pricing & Margin Card */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Icon icon="mdi:currency-usd" size={20} />
								Pricing & Margin
							</CardTitle>
						</CardHeader>
						<CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
							<FormField
								control={form.control}
								name="ppu"
								render={({ field }) => (
									<FormItem>
										<FormLabel>PPU (Price Per Unit) *</FormLabel>
										<FormControl>
											<Input type="text" placeholder="0.00" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="rsp"
								render={({ field }) => (
									<FormItem>
										<FormLabel>RSP (Retail Selling Price) *</FormLabel>
										<FormControl>
											<Input type="text" placeholder="0.00" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="margin"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Margin *</FormLabel>
										<FormControl>
											<Input type="text" placeholder="0.00 or 0%" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="promoCode"
								render={({ field }) => (
									<FormItem className="md:col-span-3">
										<FormLabel>Promo Code</FormLabel>
										<FormControl>
											<Input placeholder="Enter promo code if applicable" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</CardContent>
					</Card>

					{/* Analysis Card */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Icon icon="mdi:chart-line" size={20} />
								Product Analysis
							</CardTitle>
						</CardHeader>
						<CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<FormField
							control={form.control}
							name="pros"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Pros * (Select multiple)</FormLabel>
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
							control={form.control}
							name="cons"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Cons * (Select multiple)</FormLabel>
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
								control={form.control}
								name="otherNotes"
								render={({ field }) => (
									<FormItem className="md:col-span-2">
										<FormLabel>Other Notes/Concerns</FormLabel>
										<FormControl>
											<Textarea
												placeholder="Enter any additional notes or concerns..."
												className="min-h-[100px] resize-y"
												{...field}
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</CardContent>
					</Card>

					{/* ASIN Information Card */}
					<Card>
						<CardHeader>
							<div className="space-y-4">
								<div className="flex items-center justify-between">
									<CardTitle className="flex items-center gap-2">
										<Icon icon="mdi:package-variant" size={20} />
										ASIN Information ({asinCount})
									</CardTitle>
								</div>
							<Text variant="body2" className="text-muted-foreground">
								Add ASIN entries with size and quantity information.
							</Text>
								<div className="flex items-end gap-2">
									<div className="flex-1 max-w-[200px]">
										<FormLabel className="text-sm mb-2 block">Number of ASINs</FormLabel>
										<Input
											type="number"
											min="1"
											value={asinAmountInput}
											onChange={(e) => setAsinAmountInput(e.target.value)}
											placeholder="Enter amount"
											className="w-full"
										/>
									</div>
									<Button
										type="button"
										variant="default"
										onClick={handleAddAsins}
										className="flex items-center gap-2"
									>
										<Icon icon="mdi:plus" size={18} />
										Add ASINs
									</Button>
								</div>
							</div>
						</CardHeader>
						<CardContent>
							{asinCount === 0 ? (
								<div className="text-center py-12 text-muted-foreground">
									<Icon icon="mdi:package-variant-closed" size={48} className="mx-auto mb-4 opacity-50" />
									<Text variant="body1">No ASINs added yet. </Text>
									<Text variant="body2" className="mt-2">
										Enter the number of ASINs above and click "Add ASINs" to get started
									</Text>
								</div>
							) : (
							<div className="space-y-6">
								{Array.from({ length: asinCount }, (_, index) => (
									<div key={index}>
										{index > 0 && <Separator className="mb-6" />}
										<div className="space-y-4">
											<div className="flex items-center justify-between mb-4">
												<div className="flex items-center gap-2">
													<div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-semibold">
														{index + 1}
													</div>
													<Text variant="body1" className="font-semibold">
														ASIN {index + 1}
													</Text>
												</div>
												<Button
													type="button"
													variant="ghost"
													size="sm"
													onClick={() => handleDeleteAsin(index)}
													className="text-destructive hover:text-destructive hover:bg-destructive/10"
												>
													<Icon icon="mdi:delete" size={18} className="mr-1" />
													Delete
												</Button>
											</div>

											<div className="grid grid-cols-1 md:grid-cols-3 gap-4 pl-10">
												<FormField
													control={form.control}
													name={`asins.${index}.asin`}
													render={({ field }) => (
														<FormItem>
															<FormLabel>ASIN</FormLabel>
															<FormControl>
																<Input placeholder="B01EXAMPLE" {...field} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>

												<FormField
													control={form.control}
													name={`asins.${index}.size`}
													render={({ field }) => (
														<FormItem>
															<FormLabel>Size</FormLabel>
															<FormControl>
																<Input placeholder="e.g., Large, 12oz, XL" {...field} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>

												<FormField
													control={form.control}
													name={`asins.${index}.recommendedQuantity`}
													render={({ field }) => (
														<FormItem>
															<FormLabel>Recommended Quantity</FormLabel>
															<FormControl>
																<Input type="text" placeholder="0" {...field} />
															</FormControl>
															<FormMessage />
														</FormItem>
													)}
												/>
											</div>
										</div>
									</div>
								))}
							</div>
							)}
						</CardContent>
					</Card>

					{/* Submit Button */}
					<div className="flex items-center justify-end gap-4">
						<Button
							type="button"
							variant="outline"
							onClick={() => form.reset()}
							disabled={isSubmitting}
						>
							<Icon icon="mdi:refresh" className="mr-2" size={18} />
							Reset Form
						</Button>
						<Button type="submit" disabled={isSubmitting} className="min-w-[150px]">
							{isSubmitting ? (
								<>
									<Icon icon="mdi:loading" className="mr-2 animate-spin" size={18} />
									Submitting...
								</>
							) : (
								<>
									<Icon icon="mdi:send" className="mr-2" size={18} />
									Submit Lead
								</>
							)}
						</Button>
					</div>
				</form>
			</Form>
		</div>
	);
}
