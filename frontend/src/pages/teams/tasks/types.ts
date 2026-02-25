export enum TaskPriority {
	LOW = "Low",
	MEDIUM = "Medium",
	HIGH = "High",
}

export enum TaskTag {
	frontend = "FrontEnd",
	backend = "BackEnd",
	fullstack = "FullStack",
	DevOps = "DevOps",
	AI = "AI",
	DBA = "DBA",
	UI = "UI",
	UE = "UE",
	QA = "QA",
}

export type TaskComment = {
	id?: number;
	user_id?: number;
	username: string;
	avatar: string;
	content: string;
	time: Date;
};

export type Task = {
	id: string;
	title: string;
	priority: TaskPriority;
	assignee?: number[]; // user IDs array
	assignees?: Array<{ id: number; username: string }>; // full assignee objects
	tags?: string[];
	date?: Date | string;
	description?: string;
	comments?: TaskComment[];
	attachments?: string[];
};
export type Tasks = Record<string, Task>;

export type Column = {
	id: string;
	title: string;
	taskIds: string[];
};
export type Columns = Record<string, Column>;

export type DndDataType = {
	tasks: Tasks;
	columns: Columns;
	columnOrder: string[];
};
