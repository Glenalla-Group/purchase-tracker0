import { Icon } from "@/components/icon";
import { themeVars } from "@/theme/theme.css";
import { Avatar, AvatarImage } from "@/ui/avatar";
import { Button } from "@/ui/button";
import { Calendar } from "@/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Input } from "@/ui/input";
import { Textarea } from "@/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/ui/toggle-group";
import { Text, Title } from "@/ui/typography";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/ui/dropdown-menu";
import dayjs from "dayjs";
import { useEffect, useState, useCallback } from "react";
import type React from "react";
import styled from "styled-components";
import { type Task, TaskPriority, type TaskComment } from "./types";
import tasksService, { type User, type TaskComment as ApiTaskComment } from "@/api/services/tasksService";
import { toast } from "sonner";
import { useUserInfo } from "@/store/userStore";

type Props = {
	task: Task;
	onUpdate?: (taskId: string, updates: Partial<Task>) => void;
	onSaveRef?: React.MutableRefObject<(() => Promise<void>) | null>;
	isEditMode?: boolean;
	onEditModeChangeRef?: React.MutableRefObject<((enabled: boolean) => void) | null>;
	onCommentAdded?: () => void;
};

const TaskDetail = ({ task, onUpdate, onSaveRef, isEditMode = false, onEditModeChangeRef, onCommentAdded }: Props) => {
	const userInfo = useUserInfo();
	const [users, setUsers] = useState<User[]>([]);
	const [title, setTitle] = useState(task.title);
	const [description, setDescription] = useState(task.description || "");
	const [priority, setPriority] = useState<TaskPriority>(task.priority);
	const [assigneeIds, setAssigneeIds] = useState<number[]>(task.assignee || []);
	const [tags, setTags] = useState<string[]>(task.tags || []);
	const [dueDate, setDueDate] = useState<Date | undefined>(
		task.date ? (typeof task.date === "string" ? new Date(task.date) : task.date) : undefined
	);
	const [comments, setComments] = useState<TaskComment[]>(task.comments || []);
	const [commentDialogOpen, setCommentDialogOpen] = useState(false);
	const [commentContent, setCommentContent] = useState("");
	const [isSubmittingComment, setIsSubmittingComment] = useState(false);
	const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
	const [editCommentContent, setEditCommentContent] = useState("");
	const [editCommentDialogOpen, setEditCommentDialogOpen] = useState(false);

	// Reset form when task changes
	useEffect(() => {
		setTitle(task.title);
		setDescription(task.description || "");
		setPriority(task.priority);
		setAssigneeIds(task.assignee || []);
		setTags(task.tags || []);
		setDueDate(task.date ? (typeof task.date === "string" ? new Date(task.date) : task.date) : undefined);
		setComments(task.comments || []);
	}, [task.id, task.title, task.description, task.priority, task.assignee, task.tags, task.date, task.comments]);

	useEffect(() => {
		const initialize = async () => {
			await loadUsers();
			await loadComments();
		};
		initialize();
	}, []);

	// Load comments when task changes
	useEffect(() => {
		if (users.length > 0) {
			loadComments();
		}
	}, [task.id]);

	// Reload comments when users are loaded (to get proper usernames)
	useEffect(() => {
		if (users.length > 0 && task.id) {
			loadComments();
		}
	}, [users.length]);

	const loadUsers = async () => {
		try {
			const userList = await tasksService.getUsers();
			setUsers(userList);
		} catch (error: any) {
			toast.error("Failed to load users: " + (error.message || "Unknown error"));
		}
	};

	const loadComments = useCallback(async () => {
		try {
			// Extract numeric ID from "task-{id}" format
			const taskIdStr = task.id.replace("task-", "");
			const taskId = parseInt(taskIdStr);
			if (isNaN(taskId)) {
				console.warn("Invalid task ID for loading comments:", task.id);
				return;
			}
			const apiComments = await tasksService.getTaskComments(taskId);
			// Map API comments to local format
			// Use current users state, or fetch if empty
			let userList = users;
			if (userList.length === 0) {
				userList = await tasksService.getUsers();
				setUsers(userList);
			}
			
			const mappedComments: TaskComment[] = apiComments.map((comment: ApiTaskComment) => {
				// Find username from users list or use the username from API if available
				const user = userList.find((u) => u.id === comment.user_id);
				const username = user?.username || comment.username || "Unknown";
				return {
					id: comment.id,
					user_id: comment.user_id,
					username,
					avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(username)}&background=random`,
					content: comment.content,
					time: new Date(comment.created_at),
				};
			});
			setComments(mappedComments);
		} catch (error: any) {
			console.error("Failed to load comments:", error);
			// Don't show error toast for comments, just log it
		}
	}, [task.id, users]);

	// Expose save function via ref
	useEffect(() => {
		const handleSave = async () => {
			if (onUpdate) {
				try {
					await onUpdate(task.id, {
						title: title || "",
						description: description || "",
						priority,
						assignee: assigneeIds || [],
						tags: tags || [],
						date: dueDate,
					});
					
					// Reload comments after saving task
					await loadComments();
					
					toast.success("Task updated successfully");
				} catch (error: any) {
					console.error("Save error:", error);
					toast.error("Failed to update task: " + (error.message || "Unknown error"));
					throw error; // Re-throw so parent can handle
				}
			} else {
				console.warn("onUpdate is not provided");
				toast.error("Update function not available");
			}
		};

		if (onSaveRef) {
			onSaveRef.current = handleSave;
		}
	}, [onSaveRef, onUpdate, task.id, title, description, priority, assigneeIds, tags, dueDate, loadComments]);

	// Expose edit mode toggle function via ref
	useEffect(() => {
		if (onEditModeChangeRef) {
			onEditModeChangeRef.current = () => {
				// This will be handled by parent component
			};
		}
	}, [onEditModeChangeRef]);

	const handleAddComment = () => {
		setCommentDialogOpen(true);
	};

	const handleSubmitComment = async () => {
		if (!commentContent.trim()) {
			toast.error("Please enter a comment");
			return;
		}

		const userId = userInfo?.id ? parseInt(userInfo.id) : null;
		if (!userId) {
			toast.error("Unable to identify user. Please log in again.");
			return;
		}

		// Extract numeric ID from "task-{id}" format
		const taskIdStr = task.id.replace("task-", "");
		const taskId = parseInt(taskIdStr);
		if (isNaN(taskId)) {
			toast.error("Invalid task ID");
			return;
		}

		setIsSubmittingComment(true);
		try {
			await tasksService.createComment({
				task_id: taskId,
				user_id: userId,
				content: commentContent.trim(),
			});

			// Clear the comment input and close dialog
			setCommentContent("");
			setCommentDialogOpen(false);
			
			// Reload comments from API to get the latest data (drawer stays open)
			await loadComments();
			
			toast.success("Comment added successfully");

			// Notify parent component to refresh comment count (without reloading board)
			if (onCommentAdded) {
				onCommentAdded();
			}
		} catch (error: any) {
			console.error("Failed to add comment:", error);
			toast.error("Failed to add comment: " + (error.message || "Unknown error"));
		} finally {
			setIsSubmittingComment(false);
		}
	};

	const handleEditComment = (comment: TaskComment) => {
		if (!comment.id) return;
		setEditingCommentId(comment.id);
		setEditCommentContent(comment.content);
		setEditCommentDialogOpen(true);
	};

	const handleSubmitEditComment = async () => {
		if (!editCommentContent.trim() || !editingCommentId) {
			toast.error("Please enter a comment");
			return;
		}

		setIsSubmittingComment(true);
		try {
			await tasksService.updateComment(editingCommentId, {
				content: editCommentContent.trim(),
			});

			// Clear the edit state and close dialog
			setEditCommentContent("");
			setEditingCommentId(null);
			setEditCommentDialogOpen(false);
			
			// Reload comments from API to get the latest data
			await loadComments();
			
			toast.success("Comment updated successfully");
		} catch (error: any) {
			console.error("Failed to update comment:", error);
			toast.error("Failed to update comment: " + (error.message || "Unknown error"));
		} finally {
			setIsSubmittingComment(false);
		}
	};

	const handleDeleteComment = async (commentId: number) => {
		if (!confirm("Are you sure you want to delete this comment?")) {
			return;
		}

		try {
			await tasksService.deleteComment(commentId);
			
			// Reload comments from API to get the latest data
			await loadComments();
			
			toast.success("Comment deleted successfully");

			// Notify parent component to refresh comment count
			if (onCommentAdded) {
				onCommentAdded();
			}
		} catch (error: any) {
			console.error("Failed to delete comment:", error);
			toast.error("Failed to delete comment: " + (error.message || "Unknown error"));
		}
	};

	const selectedAssignees = users.filter((u) => assigneeIds.includes(u.id));

	return (
		<>
			<Container>
				<div className="item-title">
					{isEditMode ? (
						<Input
							value={title}
							onChange={(e) => setTitle(e.target.value)}
							className="text-lg font-semibold w-full"
							placeholder="Task title"
						/>
					) : (
						<Title as="h4" className="m-0">{title}</Title>
					)}
				</div>

				<div className="item">
					<div className="label">Assignee</div>
					<div className="content assignee-content">
						{isEditMode && (
							<Select
								value={assigneeIds.length > 0 ? assigneeIds[0].toString() : ""}
								onValueChange={(value) => {
									const userId = parseInt(value);
									if (!assigneeIds.includes(userId)) {
										setAssigneeIds([...assigneeIds, userId]);
									}
								}}
							>
								<SelectTrigger className="w-full max-w-[280px]">
									<SelectValue placeholder="Select assignee" />
								</SelectTrigger>
								<SelectContent>
									{users.map((user) => (
										<SelectItem key={user.id} value={user.id.toString()}>
											{user.username}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						)}
						<div className="flex gap-2 flex-wrap items-center w-full">
							{selectedAssignees.map((assignee) => (
								<div key={assignee.id} className="flex items-center gap-2 flex-shrink-0">
									<Avatar>
										<AvatarImage
											src={`https://ui-avatars.com/api/?name=${encodeURIComponent(assignee.username)}&background=random`}
											alt={assignee.username}
										/>
									</Avatar>
									<span className="text-sm whitespace-nowrap">{assignee.username}</span>
									{isEditMode && (
										<Button
											variant="ghost"
											size="icon"
											className="h-6 w-6 flex-shrink-0"
											onClick={() => {
												setAssigneeIds(assigneeIds.filter((id) => id !== assignee.id));
											}}
										>
											<Icon icon="mdi:close" size={16} />
										</Button>
									)}
								</div>
							))}
							{selectedAssignees.length === 0 && !isEditMode && (
								<span className="text-sm text-gray-400">No assignees</span>
							)}
						</div>
					</div>
				</div>

				<div className="item">
					<div className="label">Due Date</div>
					<div className="content">
						{isEditMode ? (
							<Popover>
								<PopoverTrigger asChild>
									<Button variant={"outline"}>
										{dueDate ? dayjs(dueDate).format("DD/MM/YYYY") : <span>Pick a date</span>}
									</Button>
								</PopoverTrigger>
								<PopoverContent className="w-auto p-0">
									<Calendar
										mode="single"
										selected={dueDate}
										onSelect={setDueDate}
										initialFocus
									/>
								</PopoverContent>
							</Popover>
						) : (
							<div className="text-sm">{dueDate ? dayjs(dueDate).format("DD/MM/YYYY") : "No due date"}</div>
						)}
					</div>
				</div>

				<div className="item">
					<div className="label">Priority</div>
					<div className="content">
						{isEditMode ? (
							<ToggleGroup
								type="single"
								value={priority}
								onValueChange={(value) => {
									if (value) setPriority(value as TaskPriority);
								}}
							>
								<ToggleGroupItem value={TaskPriority.HIGH}>
									<Icon icon="local:ic-rise" size={20} color={themeVars.colors.palette.warning.default} />
								</ToggleGroupItem>
								<ToggleGroupItem value={TaskPriority.MEDIUM}>
									<Icon
										icon="local:ic-rise"
										size={20}
										color={themeVars.colors.palette.success.default}
										className="rotate-90"
									/>
								</ToggleGroupItem>
								<ToggleGroupItem value={TaskPriority.LOW}>
									<Icon
										icon="local:ic-rise"
										size={20}
										color={themeVars.colors.palette.info.default}
										className="rotate-180"
									/>
								</ToggleGroupItem>
							</ToggleGroup>
						) : (
							<div className="flex items-center">
								{priority === TaskPriority.HIGH && (
									<Icon icon="local:ic-rise" size={20} color={themeVars.colors.palette.warning.default} />
								)}
								{priority === TaskPriority.MEDIUM && (
									<Icon
										icon="local:ic-rise"
										size={20}
										color={themeVars.colors.palette.success.default}
										className="rotate-90"
									/>
								)}
								{priority === TaskPriority.LOW && (
									<Icon
										icon="local:ic-rise"
										size={20}
										color={themeVars.colors.palette.info.default}
										className="rotate-180"
									/>
								)}
								<span className="ml-2 text-sm">{priority}</span>
							</div>
						)}
					</div>
				</div>

				<div className="item">
					<div className="label">Description</div>
					<div className="content">
						{isEditMode ? (
							<Textarea
								value={description}
								onChange={(e) => setDescription(e.target.value)}
								placeholder="Add description..."
								className="w-full"
							/>
						) : (
							<div className="text-sm text-gray-600 whitespace-pre-wrap">{description || "No description"}</div>
						)}
					</div>
				</div>
			</Container>
			{/* comments */}
			<div className="comments-section px-4 pb-4">
				<div className="flex items-center justify-between pb-4">
					<Text variant="caption" color="secondary">
						Comments
					</Text>
					<Button size="sm" onClick={handleAddComment}>
						Add Comment
					</Button>
				</div>
				{comments?.map((comment, index) => {
					const currentUserId = userInfo?.id ? parseInt(userInfo.id) : null;
					const isOwnComment = comment.user_id && currentUserId && comment.user_id === currentUserId;
					
					return (
						<div 
							key={`${comment.id || comment.username}-${comment.time.getTime()}-${index}`} 
							className="flex gap-4 py-4 border-b border-gray-200 dark:border-gray-700 last:border-b-0 last:pb-0 first:pt-0"
						>
							<Avatar className="flex-shrink-0 h-8 w-8">
								<AvatarImage
									src={`https://ui-avatars.com/api/?name=${encodeURIComponent(comment.username)}&background=random`}
									alt={comment.username}
								/>
							</Avatar>
							<div className="flex grow flex-col flex-wrap gap-1 text-gray min-w-0">
								<div className="flex justify-between items-center gap-2">
									<Text variant="caption" color="secondary" className="font-medium">
										{comment.username}
									</Text>
									<div className="flex items-center gap-2">
										<Text variant="caption" color="secondary" className="text-xs whitespace-nowrap">
											{dayjs(comment.time).format("DD/MM/YYYY HH:mm")}
										</Text>
										{isOwnComment && comment.id && (
											<DropdownMenu>
												<DropdownMenuTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className="h-6 w-6 flex-shrink-0"
													>
														<Icon icon="mdi:dots-vertical" size={16} />
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end">
													<DropdownMenuItem onClick={() => handleEditComment(comment)}>
														<Icon icon="mdi:pencil" size={16} />
														<span>Edit comment</span>
													</DropdownMenuItem>
													<DropdownMenuItem 
														variant="destructive"
														onClick={() => comment.id && handleDeleteComment(comment.id)}
													>
														<Icon icon="mdi:delete" size={16} />
														<span>Delete</span>
													</DropdownMenuItem>
												</DropdownMenuContent>
											</DropdownMenu>
										)}
									</div>
								</div>
								<p className="text-sm text-gray-700 dark:text-gray-300 mt-1 break-words leading-relaxed">{comment.content}</p>
							</div>
						</div>
					);
				})}
				{comments.length === 0 && (
					<Text variant="caption" color="secondary" className="text-center py-4">
						No comments yet
					</Text>
				)}
			</div>

			{/* Comment Dialog */}
			<Dialog 
				open={commentDialogOpen} 
				onOpenChange={(open) => {
					setCommentDialogOpen(open);
					if (!open) {
						setCommentContent("");
					}
				}}
			>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Add Comment</DialogTitle>
					</DialogHeader>
					<div className="flex flex-col gap-4 py-4">
						<Textarea
							value={commentContent}
							onChange={(e) => setCommentContent(e.target.value)}
							placeholder="Write a comment..."
							rows={4}
							className="resize-none"
							onKeyDown={(e) => {
								// Allow submitting with Ctrl+Enter or Cmd+Enter
								if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && commentContent.trim() && !isSubmittingComment) {
									handleSubmitComment();
								}
							}}
						/>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setCommentDialogOpen(false);
								setCommentContent("");
							}}
							disabled={isSubmittingComment}
						>
							Cancel
						</Button>
						<Button onClick={handleSubmitComment} disabled={isSubmittingComment || !commentContent.trim()}>
							{isSubmittingComment ? "Submitting..." : "Add Comment"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Edit Comment Dialog */}
			<Dialog 
				open={editCommentDialogOpen} 
				onOpenChange={(open) => {
					setEditCommentDialogOpen(open);
					if (!open) {
						setEditCommentContent("");
						setEditingCommentId(null);
					}
				}}
			>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Edit Comment</DialogTitle>
					</DialogHeader>
					<div className="flex flex-col gap-4 py-4">
						<Textarea
							value={editCommentContent}
							onChange={(e) => setEditCommentContent(e.target.value)}
							placeholder="Write a comment..."
							rows={4}
							className="resize-none"
							onKeyDown={(e) => {
								// Allow submitting with Ctrl+Enter or Cmd+Enter
								if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && editCommentContent.trim() && !isSubmittingComment) {
									handleSubmitEditComment();
								}
							}}
						/>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => {
								setEditCommentDialogOpen(false);
								setEditCommentContent("");
								setEditingCommentId(null);
							}}
							disabled={isSubmittingComment}
						>
							Cancel
						</Button>
						<Button onClick={handleSubmitEditComment} disabled={isSubmittingComment || !editCommentContent.trim()}>
							{isSubmittingComment ? "Saving..." : "Save Changes"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</>
	);
}

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  width: 100%;
  box-sizing: border-box;
  
  .item-title {
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    margin-bottom: 8px;
    width: 100%;
    box-sizing: border-box;
  }
  
  .item {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    min-height: 32px;
    width: 100%;
    box-sizing: border-box;
    overflow: hidden;
  }
  
  .label {
    text-align: left;
    font-size: 0.75rem;
    font-weight: 600;
    width: 85px;
    flex-shrink: 0;
    color: ${themeVars.colors.text.secondary};
    padding-top: 6px;
    line-height: 1.5;
  }
  
  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 32px;
    align-items: flex-start;
    justify-content: center;
    min-width: 0; /* Allow flex item to shrink below content size */
    overflow: hidden; /* Prevent overflow */
  }
  
  .assignee-content {
    max-width: 100%;
    overflow: visible; /* Allow dropdown to show */
  }
  
  .comments-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 0 24px 24px 24px;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
    padding-top: 24px;
  }
`;

TaskDetail.displayName = "TaskDetail";

export default TaskDetail;
