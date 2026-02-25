import { Icon } from "@/components/icon";
import { themeVars } from "@/theme/theme.css";
import { Avatar, AvatarImage } from "@/ui/avatar";
import { Button } from "@/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/ui/sheet";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { type CSSProperties, memo, useState, useRef, useEffect } from "react";
import styled from "styled-components";
import TaskDetail from "./task-detail";
import { type Task, TaskPriority, type Column } from "./types";
import tasksService from "@/api/services/tasksService";

type Props = {
	id: string;
	task: Task;
	currentColumnId?: string;
	columns?: Column[];
	isDragging?: boolean;
	onDelete?: (taskId: string) => void;
	onUpdate?: (taskId: string, updates: Partial<Task>) => void;
	onMoveToColumn?: (taskId: string, newColumnId: string) => void;
};

function KanbanTask({ id, task, currentColumnId, columns = [], isDragging, onDelete, onUpdate, onMoveToColumn }: Props) {
	const [drawerOpen, setDrawerOpen] = useState(false);
	const [isEditMode, setIsEditMode] = useState(false);
	const [commentCount, setCommentCount] = useState(task.comments?.length || 0);
	const saveHandlerRef = useRef<(() => Promise<void>) | null>(null);
	const toggleEditRef = useRef<((enabled: boolean) => void) | null>(null);
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

	const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });

	const style: CSSProperties = {
		transform: CSS.Transform.toString(transform),
		transition,
	};

	const { title, attachments = [], priority, assignees = [] } = task;

	// Load comment count when component mounts, task changes, or drawer opens
	useEffect(() => {
		const loadCommentCount = async () => {
			try {
				const taskIdStr = task.id.replace("task-", "");
				const taskId = parseInt(taskIdStr);
				if (!isNaN(taskId)) {
					const comments = await tasksService.getTaskComments(taskId);
					setCommentCount(comments.length);
				}
			} catch (error) {
				// Silently fail - use existing count
			}
		};

		loadCommentCount();
	}, [task.id, drawerOpen]);

	const handleDeleteConfirm = () => {
		setDeleteDialogOpen(true);
	};

	const handleDelete = async () => {
		if (onDelete) {
			await onDelete(id);
			setDeleteDialogOpen(false);
			setDrawerOpen(false);
		}
	};

	const handleEditToggle = async () => {
		if (isEditMode) {
			// Save mode - save the changes
			if (saveHandlerRef.current) {
				await saveHandlerRef.current();
				setIsEditMode(false);
				if (toggleEditRef.current) {
					toggleEditRef.current(false);
				}
			}
		} else {
			// Edit mode - enable editing
			setIsEditMode(true);
			if (toggleEditRef.current) {
				toggleEditRef.current(true);
			}
		}
	};

	return (
		<>
			<Container ref={setNodeRef} style={style} {...attributes} {...listeners} $isDragging={!!isDragging}>
				<div>
					{attachments && attachments.length > 0 && <img src={attachments[0]} alt="" className="mb-4 rounded-md" />}
					<div onClick={() => setDrawerOpen(true)}>
						<div className="flex justify-end">
							<TaskPrioritySvg taskPriority={priority} />
						</div>
						<div>{title}</div>
						<div className="mt-4 flex items-center justify-between">
							<div className="flex items-center text-base text-gray-600 gap-1">
								<Icon icon="uim:comment-dots" size={16} />
								<span className="text-xs font-medium">{commentCount}</span>
							</div>

							{assignees && assignees.length > 0 && (
								<div className="flex gap-2 -space-x-4">
									{assignees.slice(0, 3).map((assignee) => (
										<Avatar key={assignee.id} title={assignee.username}>
											<AvatarImage src={`https://ui-avatars.com/api/?name=${encodeURIComponent(assignee.username)}&background=random`} />
										</Avatar>
									))}
								</div>
							)}
						</div>
					</div>
				</div>
			</Container>

			<Sheet 
				open={drawerOpen} 
				modal={false} 
				onOpenChange={(open) => {
					setDrawerOpen(open);
					if (!open) {
						setIsEditMode(false); // Reset edit mode when drawer closes
					}
				}}
			>
				<SheetContent className="w-[420px] p-0 [&>button]:hidden pointer-events-auto flex flex-col h-full">
					<SheetHeader className="flex-shrink-0 pb-4 border-b px-6 pt-6">
						<SheetTitle className="sr-only">Task Details</SheetTitle>
						<div className="flex items-center justify-between">
							{columns.length > 0 && currentColumnId && (
								<div>
									<Select 
										value={currentColumnId} 
										onValueChange={(newColumnId) => {
											if (onMoveToColumn && newColumnId !== currentColumnId) {
												onMoveToColumn(id, newColumnId);
											}
										}}
									>
										<SelectTrigger size="default" className="w-[140px]">
											<SelectValue />
										</SelectTrigger>
										<SelectContent>
											{columns.map((column) => (
												<SelectItem key={column.id} value={column.id}>
													{column.title}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>
							)}
							<div className="flex text-gray gap-1">
								<Button 
									variant="ghost" 
									size="icon" 
									onClick={handleEditToggle} 
									title={isEditMode ? "Save changes" : "Edit task"}
								>
									<Icon 
										icon={isEditMode ? "solar:diskette-bold" : "solar:pen-bold"} 
										size={20} 
										className={isEditMode ? "text-success!" : ""} 
									/>
								</Button>
								<Button variant="ghost" size="icon" onClick={handleDeleteConfirm} title="Delete task">
									<Icon icon="solar:trash-bin-trash-bold" size={20} className="text-error!" />
								</Button>
							</div>
						</div>
					</SheetHeader>
					<div className="flex-1 overflow-y-auto">
						<TaskDetail 
							task={task} 
							onUpdate={onUpdate}
							onCommentAdded={async () => {
								// Reload comment count after comment is added (without closing drawer)
								try {
									const taskIdStr = task.id.replace("task-", "");
									const taskIdNum = parseInt(taskIdStr);
									if (!isNaN(taskIdNum)) {
										const comments = await tasksService.getTaskComments(taskIdNum);
										setCommentCount(comments.length);
									}
								} catch (error) {
									// Silently fail
								}
							}}
							onSaveRef={saveHandlerRef}
							isEditMode={isEditMode}
							onEditModeChangeRef={toggleEditRef}
						/>
					</div>
				</SheetContent>
			</Sheet>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Are you sure?</DialogTitle>
						<DialogDescription>
							This will permanently delete this task. This action cannot be undone.
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
		</>
	);
}

export default memo(KanbanTask);

type TaskPrioritySvgProps = {
	taskPriority: TaskPriority;
};
function TaskPrioritySvg({ taskPriority }: TaskPrioritySvgProps) {
	switch (taskPriority) {
		case TaskPriority.HIGH:
			return <Icon icon="local:ic-rise" size={20} color={themeVars.colors.palette.warning.default} className="" />;
		case TaskPriority.MEDIUM:
			return (
				<Icon icon="local:ic-rise" size={20} color={themeVars.colors.palette.success.default} className="rotate-90" />
			);
		case TaskPriority.LOW:
			return (
				<Icon icon="local:ic-rise" size={20} color={themeVars.colors.palette.info.default} className="rotate-180" />
			);
		default:
			break;
	}
}
const Container = styled.div<{ $isDragging: boolean }>`
	width: 248px;
	border-radius: 12px;
	padding: 16px;
	margin-bottom: 16px;
	font-weight: 400;
	font-size: 12px;
	background-color: ${themeVars.colors.background.default};
	backdrop-filter: ${(props) => (props.$isDragging ? "blur(6px)" : "")};

	&:hover {
		box-shadow: ${themeVars.shadows["3xl"]};
	}
`;
