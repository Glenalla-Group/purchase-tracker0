import apiClient from "../apiClient";

// ==================== Types ====================

export interface TaskColumn {
	id: string;
	title: string;
	position: number;
	created_at: string;
	updated_at: string;
}

export interface Task {
	id: string;
	column_id: number;
	title: string;
	description?: string;
	priority: "Low" | "Medium" | "High";
	assignee_ids?: number[];
	assignees?: Array<{ id: number; username: string }>;
	tags?: string[];
	due_date?: string;
	attachments?: string[];
	position: number;
	created_at: string;
	updated_at: string;
}

export interface TaskComment {
	id: number;
	task_id: number;
	user_id: number;
	username?: string;
	content: string;
	created_at: string;
	updated_at: string;
}

export interface User {
	id: number;
	username: string;
	email: string;
}

export interface BoardData {
	tasks: Record<string, {
		id: string;
		title: string;
		priority: string;
		assignee: number[];
		tags: string[];
		date?: string;
		description?: string;
		attachments: string[];
	}>;
	columns: Record<string, {
		id: string;
		title: string;
		taskIds: string[];
	}>;
	columnOrder: string[];
}

export interface TaskCreateRequest {
	column_id: number;
	title: string;
	description?: string;
	priority?: "Low" | "Medium" | "High";
	assignee_ids?: number[];
	tags?: string[];
	due_date?: string;
	attachments?: string[];
	position?: number;
}

export interface TaskUpdateRequest {
	column_id?: number;
	title?: string;
	description?: string;
	priority?: "Low" | "Medium" | "High";
	assignee_ids?: number[];
	tags?: string[];
	due_date?: string;
	attachments?: string[];
	position?: number;
}

export interface ColumnCreateRequest {
	title: string;
	position?: number;
}

export interface ColumnUpdateRequest {
	title?: string;
	position?: number;
}

export interface CommentCreateRequest {
	task_id: number;
	user_id: number;
	content: string;
}

export interface CommentUpdateRequest {
	content: string;
}

// ==================== Service ====================

class TasksService {
	/**
	 * Get all users for assignee selection
	 */
	async getUsers(): Promise<User[]> {
		return apiClient.get<User[]>({
			url: "/api/v1/tasks/users",
		});
	}

	/**
	 * Get complete board data (for kanban view)
	 */
	async getBoardData(): Promise<BoardData> {
		return apiClient.get<BoardData>({
			url: "/api/v1/tasks/board/data",
		});
	}

	/**
	 * Get all columns
	 */
	async getColumns(): Promise<TaskColumn[]> {
		return apiClient.get<TaskColumn[]>({
			url: "/api/v1/tasks/columns",
		});
	}

	/**
	 * Create a new column
	 */
	async createColumn(data: ColumnCreateRequest): Promise<TaskColumn> {
		return apiClient.post<TaskColumn>({
			url: "/api/v1/tasks/columns",
			data,
		});
	}

	/**
	 * Update a column
	 */
	async updateColumn(columnId: number, data: ColumnUpdateRequest): Promise<TaskColumn> {
		return apiClient.put<TaskColumn>({
			url: `/api/v1/tasks/columns/${columnId}`,
			data,
		});
	}

	/**
	 * Delete a column
	 */
	async deleteColumn(columnId: number): Promise<void> {
		return apiClient.delete<void>({
			url: `/api/v1/tasks/columns/${columnId}`,
		});
	}

	/**
	 * Get all tasks
	 */
	async getTasks(columnId?: number): Promise<Task[]> {
		return apiClient.get<Task[]>({
			url: "/api/v1/tasks",
			params: columnId ? { column_id: columnId } : undefined,
		});
	}

	/**
	 * Get a single task by ID
	 */
	async getTask(taskId: number): Promise<Task> {
		return apiClient.get<Task>({
			url: `/api/v1/tasks/${taskId}`,
		});
	}

	/**
	 * Create a new task
	 */
	async createTask(data: TaskCreateRequest): Promise<Task> {
		return apiClient.post<Task>({
			url: "/api/v1/tasks",
			data,
		});
	}

	/**
	 * Update a task
	 */
	async updateTask(taskId: number, data: TaskUpdateRequest): Promise<Task> {
		return apiClient.put<Task>({
			url: `/api/v1/tasks/${taskId}`,
			data,
		});
	}

	/**
	 * Delete a task
	 */
	async deleteTask(taskId: number): Promise<void> {
		return apiClient.delete<void>({
			url: `/api/v1/tasks/${taskId}`,
		});
	}

	/**
	 * Get comments for a task
	 */
	async getTaskComments(taskId: number): Promise<TaskComment[]> {
		return apiClient.get<TaskComment[]>({
			url: `/api/v1/tasks/${taskId}/comments`,
		});
	}

	/**
	 * Create a comment
	 */
	async createComment(data: CommentCreateRequest): Promise<TaskComment> {
		return apiClient.post<TaskComment>({
			url: "/api/v1/tasks/comments",
			data,
		});
	}

	/**
	 * Update a comment
	 */
	async updateComment(commentId: number, data: CommentUpdateRequest): Promise<TaskComment> {
		return apiClient.put<TaskComment>({
			url: `/api/v1/tasks/comments/${commentId}`,
			data,
		});
	}

	/**
	 * Delete a comment
	 */
	async deleteComment(commentId: number): Promise<void> {
		return apiClient.delete<void>({
			url: `/api/v1/tasks/comments/${commentId}`,
		});
	}
}

export default new TasksService();

