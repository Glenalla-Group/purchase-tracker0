import { Icon } from "@/components/icon";
import { useSettings } from "@/store/settingStore";
import { Button } from "@/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/ui/dropdown-menu";
import { Input } from "@/ui/input";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import React, { type CSSProperties, useRef, useState } from "react";
import { useEvent } from "react-use";
import { ThemeMode } from "#/enum";
import KanbanTask from "./kanban-task";
import { type Column, type Task } from "./types";

type Props = {
	id: string;
	index: number;
	column: Column;
	tasks: Task[];
	createTask: (columnId: string, taskTitle: string) => Promise<void>;
	clearColumn: (columnId: string) => void;
	deleteColumn: (columnId: string) => void;
	renameColumn: (column: Column) => void;
	onUpdateTask?: (taskId: string, updates: Partial<Task>) => void;
	onDeleteTask?: (taskId: string) => void;
	onMoveTaskToColumn?: (taskId: string, newColumnId: string) => void;
	allColumns?: Column[];
	isDragging?: boolean;
};

export default function KanbanColumn({
	id,
	column,
	tasks,
	createTask,
	clearColumn,
	deleteColumn,
	renameColumn,
	onUpdateTask,
	onDeleteTask,
	onMoveTaskToColumn,
	allColumns = [],
	isDragging,
}: Props) {
	const { themeMode } = useSettings();
	const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });

	const style: CSSProperties = {
		transform: CSS.Transform.toString(transform),
		transition,
		height: "100%",
		padding: "16px",
		borderRadius: "16px",
		backgroundColor: themeMode === ThemeMode.Light ? "rgb(244, 246, 248)" : "rgba(145, 158, 171, 0.12)",
		opacity: isDragging ? 0.5 : 1,
	};

	const [renamingTask, setRenamingTask] = useState(false);
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const [clearDialogOpen, setClearDialogOpen] = useState(false);
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

	const handleClearConfirm = () => {
		if (tasks.length === 0) {
			// No tasks to clear, proceed directly
			clearColumn(column.id);
		} else {
			setClearDialogOpen(true);
		}
	};

	const handleClear = () => {
		clearColumn(column.id);
		setClearDialogOpen(false);
	};

	const handleDeleteConfirm = () => {
		if (tasks.length === 0) {
			// No tasks to delete, proceed directly
			deleteColumn(column.id);
		} else {
			setDeleteDialogOpen(true);
		}
	};

	const handleDelete = () => {
		deleteColumn(column.id);
		setDeleteDialogOpen(false);
	};

	const items = [
		{
			key: "1",
			label: (
				<div
					className="flex items-center text-gray"
					onClick={() => {
						setRenamingTask(true);
					}}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							setRenamingTask(true);
						}
					}}
				>
					<Icon icon="solar:pen-bold" />
					<span className="ml-2">Rename</span>
				</div>
			),
		},
		{
			key: "2",
			label: (
				<div
					className="flex items-center text-gray"
					onClick={handleClearConfirm}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							handleClearConfirm();
						}
					}}
				>
					<Icon icon="solar:eraser-bold" />
					<span className="ml-2">Clear</span>
				</div>
			),
		},
		{
			key: "3",
			label: (
				<div
					className="flex items-center text-warning"
					onClick={handleDeleteConfirm}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							handleDeleteConfirm();
						}
					}}
				>
					<Icon icon="solar:trash-bin-trash-bold" />
					<span className="ml-2">Delete</span>
				</div>
			),
		},
	];

	const [addingTask, setAddingTask] = useState(false);
	const addTaskInputRef = useRef<HTMLInputElement>(null);
	const handleClickOutside = async (event: MouseEvent) => {
		if (addTaskInputRef.current && !addTaskInputRef.current.contains(event.target as Node)) {
			const addTaskInputVal = addTaskInputRef.current.value;
			if (addTaskInputVal) {
				await createTask(column.id, addTaskInputVal);
				// Clear input after task is created
				if (addTaskInputRef.current) {
					addTaskInputRef.current.value = "";
				}
			}
			setAddingTask(false);
		}

		if (renameTaskInputRef.current && !renameTaskInputRef.current.contains(event.target as Node)) {
			const renameInputVal = renameTaskInputRef.current.value;
			if (renameInputVal) {
				renameColumn({
					...column,
					title: renameInputVal,
				});
			}
			setRenamingTask(false);
		}
	};
	useEvent("click", handleClickOutside);

	const renameTaskInputRef = useRef<HTMLInputElement>(null);
	
	const handleMenuItemClick = (e: React.MouseEvent) => {
		e.stopPropagation();
		setDropdownOpen(false);
	};
	return (
		<div ref={setNodeRef} style={style}>
			<header
				{...attributes}
				{...listeners}
				className="mb-4 flex select-none items-center justify-between text-base font-semibold"
			>
				{renamingTask ? <Input ref={renameTaskInputRef} autoFocus /> : column.title}
				<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
					<DropdownMenuTrigger asChild>
						<Button variant="ghost" size="icon" className="text-gray!">
							<Icon icon="dashicons:ellipsis" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						{items.map((item) => (
							<DropdownMenuItem key={item.key} onClick={handleMenuItemClick}>
								{item.label}
							</DropdownMenuItem>
						))}
					</DropdownMenuContent>
				</DropdownMenu>
			</header>

			<SortableContext items={tasks.map((task) => task.id)} strategy={verticalListSortingStrategy}>
				<div className="min-h-[10px]">
					{tasks.map((task) => (
						<KanbanTask 
							key={task.id} 
							id={task.id} 
							task={task}
							currentColumnId={id}
							columns={allColumns}
							onUpdate={onUpdateTask}
							onDelete={onDeleteTask}
							onMoveToColumn={onMoveTaskToColumn}
						/>
					))}
				</div>
			</SortableContext>

			<footer className="w-[248px]">
				{addingTask ? (
					<Input 
						ref={addTaskInputRef} 
						placeholder="Task Name" 
						autoFocus 
						onKeyDown={async (e) => {
							if (e.key === "Enter" && addTaskInputRef.current?.value.trim()) {
								e.preventDefault();
								e.stopPropagation();
								const taskTitle = addTaskInputRef.current.value.trim();
								await createTask(column.id, taskTitle);
								if (addTaskInputRef.current) {
									addTaskInputRef.current.value = "";
								}
								setAddingTask(false);
							} else if (e.key === "Escape") {
								e.preventDefault();
								e.stopPropagation();
								if (addTaskInputRef.current) {
									addTaskInputRef.current.value = "";
								}
								setAddingTask(false);
							}
						}}
					/>
				) : (
					<Button
						onClick={(e) => {
							e.stopPropagation();
							setAddingTask(true);
						}}
						className="flex! items-center justify-center text-xs! font-medium! w-full"
					>
						<Icon icon="carbon:add" size={20} />
						<span>Add Task</span>
					</Button>
				)}
			</footer>

			{/* Clear Confirmation Dialog */}
			<Dialog open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Clear Column?</DialogTitle>
						<DialogDescription>
							This will permanently delete all{" "}
							<span className="font-semibold text-foreground">{tasks.length}</span> task
							{tasks.length !== 1 ? "s" : ""} in the column{" "}
							<span className="font-semibold text-foreground">"{column.title}"</span>. This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setClearDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleClear} variant="destructive">
							Clear
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Delete Column?</DialogTitle>
						<DialogDescription>
							This will permanently delete the column{" "}
							<span className="font-semibold text-foreground">"{column.title}"</span> and all{" "}
							<span className="font-semibold text-foreground">{tasks.length}</span> task
							{tasks.length !== 1 ? "s" : ""} in it. This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleDelete} variant="destructive">
							Delete
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
