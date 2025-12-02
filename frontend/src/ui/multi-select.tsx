import * as React from "react";
import { X } from "lucide-react";

import { Badge } from "@/ui/badge";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/ui/command";
import { cn } from "@/utils";

export interface MultiSelectOption {
	value: string;
	label: string;
}

interface MultiSelectProps {
	options: MultiSelectOption[];
	value?: string[];
	onValueChange?: (value: string[]) => void;
	placeholder?: string;
	searchPlaceholder?: string;
	emptyText?: string;
	disabled?: boolean;
	className?: string;
	maxHeight?: string;
}

export function MultiSelect({
	options,
	value = [],
	onValueChange,
	placeholder = "Select options...",
	// searchPlaceholder = "Search...",
	emptyText = "No option found.",
	disabled = false,
	className,
	maxHeight = "300px",
}: MultiSelectProps) {
	const [inputValue, setInputValue] = React.useState("");
	const [open, setOpen] = React.useState(false);
	const inputRef = React.useRef<HTMLInputElement>(null);
	const containerRef = React.useRef<HTMLDivElement>(null);
	
	// Close dropdown when clicking outside
	React.useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
				setOpen(false);
			}
		};
		
		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	const handleUnselect = (option: string) => {
		const newValue = value.filter((v) => v !== option);
		onValueChange?.(newValue);
	};

	const handleSelect = (option: string) => {
		const newValue = value.includes(option)
			? value.filter((v) => v !== option)
			: [...value, option];
		onValueChange?.(newValue);
		setInputValue("");
	};

	const selectedLabels = value
		.map((v) => options.find((opt) => opt.value === v)?.label)
		.filter(Boolean);
	
	const filteredOptions = inputValue.length > 0
		? options.filter((option) =>
				option.label.toLowerCase().includes(inputValue.toLowerCase())
		  )
		: options;

	return (
		<div ref={containerRef} className={cn("relative w-full", className)}>
			<Command className="overflow-visible bg-transparent">
				<div 
					className="group rounded-md border border-input px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
					onClick={() => {
						setOpen(true);
						inputRef.current?.focus();
					}}
				>
					<div className="flex flex-wrap gap-1">
						{selectedLabels.map((label, index) => (
							<Badge key={value[index]} variant="secondary" className="rounded-sm px-1 font-normal">
								{label}
								<button
									className="ml-1 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2"
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											handleUnselect(value[index]);
										}
									}}
									onMouseDown={(e) => {
										e.preventDefault();
										e.stopPropagation();
									}}
									onClick={() => handleUnselect(value[index])}
									disabled={disabled}
								>
									<X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
								</button>
							</Badge>
						))}
						<CommandInput
							ref={inputRef}
							value={inputValue}
							onValueChange={setInputValue}
							onFocus={() => setOpen(true)}
							placeholder={value.length === 0 ? placeholder : ""}
							className="ml-2 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
							disabled={disabled}
						/>
					</div>
				</div>
				{open && (
					<div className="absolute top-full left-0 z-50 mt-2 w-full rounded-md border bg-popover text-popover-foreground shadow-md outline-none animate-in">
						<CommandList style={{ maxHeight }}>
							<CommandEmpty>{emptyText}</CommandEmpty>
							<CommandGroup className="h-full overflow-auto">
								{filteredOptions.map((option) => (
									<CommandItem
										key={option.value}
										onSelect={() => handleSelect(option.value)}
										className="cursor-pointer"
									>
										<div
											className={cn(
												"mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
												value.includes(option.value)
													? "bg-primary text-primary-foreground"
													: "opacity-50 [&_svg]:invisible"
											)}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												strokeLinecap="round"
												strokeLinejoin="round"
												className="h-4 w-4"
											>
												<polyline points="20 6 9 17 4 12" />
											</svg>
										</div>
										{option.label}
									</CommandItem>
								))}
							</CommandGroup>
						</CommandList>
					</div>
				)}
			</Command>
		</div>
	);
}

