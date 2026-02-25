import { Icon } from "@/components/icon";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { ScrollArea, ScrollBar } from "@/ui/scroll-area";
import {
	DndContext,
	type DragEndEvent,
	DragOverlay,
	type DragStartEvent,
	PointerSensor,
	useSensor,
	useSensors,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { useEffect, useRef, useState } from "react";
import { useEvent } from "react-use";
import { toast } from "sonner";
import KanbanColumn from "./kanban-column";
import KanbanTask from "./kanban-task";
import { initialData } from "./task-utils";
import type { Column, DndDataType, Task } from "./types";
import { TaskPriority } from "./types";
import tasksService from "@/api/services/tasksService";
export default function Kanban() {
	const [state, setState] = useState<DndDataType>(initialData);
	const [activeId, setActiveId] = useState<string | null>(null);
	const [activeType, setActiveType] = useState<"column" | "task" | null>(null);
	const [addingColumn, setAddingColumn] = useState(false);
	const [loading, setLoading] = useState(true);
	const inputRef = useRef<HTMLInputElement>(null);

	const sensors = useSensors(
		useSensor(PointerSensor, {
			activationConstraint: {
				distance: 8,
			},
		}),
	);

	// Load board data from API
	useEffect(() => {
		loadBoardData();
	}, []);

		const loadBoardData = async () => {
		try {
			setLoading(true);
			const boardData = await tasksService.getBoardData();
			
			// Transform API data to frontend format
			// API returns tasks with string priority, convert to TaskPriority enum
			const transformedTasks: Record<string, Task> = {};
			for (const [key, task] of Object.entries(boardData.tasks)) {
				transformedTasks[key] = {
					...task,
					priority: task.priority as TaskPriority,
				};
			}
			
			const transformedData: DndDataType = {
				tasks: transformedTasks,
				columns: boardData.columns,
				columnOrder: boardData.columnOrder,
			};
			
			setState(transformedData);
		} catch (error: any) {
			toast.error("Failed to load tasks: " + (error.message || "Unknown error"));
			console.error("Error loading board data:", error);
		} finally {
			setLoading(false);
		}
	};

	const handleDragStart = (event: DragStartEvent) => {
		const { active } = event;
		setActiveId(active.id as string);
		setActiveType(active.id.toString().startsWith("task-") ? "task" : "column");
	};

	const handleDragEnd = async (event: DragEndEvent) => {
		const { active, over } = event;

		if (!over) {
			setActiveId(null);
			setActiveType(null);
			return;
		}

		if (active.id !== over.id) {
			if (activeType === "column") {
				// Handle column drag
				const oldIndex = state.columnOrder.indexOf(active.id as string);
				const newIndex = state.columnOrder.indexOf(over.id as string);

				const newColumnOrder = arrayMove(state.columnOrder, oldIndex, newIndex);
				
				// Update state optimistically first for smooth animation
				setState({
					...state,
					columnOrder: newColumnOrder,
				});
				
				// Clear activeId immediately to allow transition animation
				setActiveId(null);
				setActiveType(null);
				
				// Update positions in backend
				const columnId = parseInt((active.id as string).replace("column-", ""));
				const newPosition = newIndex;
				
				try {
					await tasksService.updateColumn(columnId, { position: newPosition });
				} catch (error: any) {
					toast.error("Failed to update column position: " + (error.message || "Unknown error"));
					loadBoardData(); // Reload on error
				}
			} else {
				// Handle task drag
				const activeColumn = Object.values(state.columns).find((col) => col.taskIds.includes(active.id as string));
				const overColumn = Object.values(state.columns).find(
					(col) => col.taskIds.includes(over.id as string) || col.id === over.id,
				);

				if (!activeColumn || !overColumn) {
					setActiveId(null);
					setActiveType(null);
					return;
				}

				const taskId = parseInt((active.id as string).replace("task-", ""));
				const newColumnId = parseInt(overColumn.id.replace("column-", ""));

				if (activeColumn === overColumn) {
					// Same column - reorder
					const newTaskIds = arrayMove(
						activeColumn.taskIds,
						activeColumn.taskIds.indexOf(active.id as string),
						activeColumn.taskIds.indexOf(over.id as string),
					);

					const newPosition = newTaskIds.indexOf(active.id as string);
					
					// Update state optimistically first for smooth animation
					setState({
						...state,
						columns: {
							...state.columns,
							[activeColumn.id]: {
								...activeColumn,
								taskIds: newTaskIds,
							},
						},
					});
					
					// Clear activeId immediately to allow transition animation
					setActiveId(null);
					setActiveType(null);
					
					try {
						await tasksService.updateTask(taskId, { position: newPosition });
					} catch (error: any) {
						toast.error("Failed to update task position: " + (error.message || "Unknown error"));
						loadBoardData();
					}
				} else {
					// Different column - move task
					const sourceTaskIds = activeColumn.taskIds.filter((id) => id !== active.id);
					const destinationTaskIds = [...overColumn.taskIds];
					const overTaskIndex = overColumn.taskIds.indexOf(over.id as string);

					destinationTaskIds.splice(
						overTaskIndex >= 0 ? overTaskIndex : destinationTaskIds.length,
						0,
						active.id as string,
					);

					const newPosition = destinationTaskIds.indexOf(active.id as string);
					
					// Update state optimistically first for smooth animation
					setState({
						...state,
						columns: {
							...state.columns,
							[activeColumn.id]: {
								...activeColumn,
								taskIds: sourceTaskIds,
							},
							[overColumn.id]: {
								...overColumn,
								taskIds: destinationTaskIds,
							},
						},
					});
					
					// Clear activeId immediately to allow transition animation
					setActiveId(null);
					setActiveType(null);
					
					try {
						await tasksService.updateTask(taskId, { column_id: newColumnId, position: newPosition });
					} catch (error: any) {
						toast.error("Failed to move task: " + (error.message || "Unknown error"));
						loadBoardData();
					}
				}
			}
		} else {
			// No change in position, just clear activeId
			setActiveId(null);
			setActiveType(null);
		}
	};

	const handleClickOutside = (event: MouseEvent) => {
		if (inputRef.current && !inputRef.current.contains(event.target as Node)) {
			const inputVal = inputRef.current.value;
			if (inputVal) {
				createColumn(inputVal);
			}
			setAddingColumn(false);
		}
	};
	useEvent("click", handleClickOutside);

	const createColumn = async (title: string) => {
		try {
			const newColumn = await tasksService.createColumn({ title });
			
			// Transform API column to frontend format
			// API may return id as number or string, ensure it's formatted as "column-{id}"
			const columnIdStr = String(newColumn.id);
			const columnId = columnIdStr.startsWith("column-") ? columnIdStr : `column-${columnIdStr}`;
			const newColumnData: Column = {
				id: columnId,
				title: newColumn.title,
				taskIds: [],
			};
			
			// Update state optimistically
			setState((prevState) => ({
				...prevState,
				columns: {
					...prevState.columns,
					[columnId]: newColumnData,
				},
				columnOrder: [...prevState.columnOrder, columnId],
			}));
		} catch (error: any) {
			toast.error("Failed to create column: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const createTask = async (columnId: string, taskTitle: string) => {
		try {
			const columnIdNum = parseInt(columnId.replace("column-", ""));
			const newTask = await tasksService.createTask({
				column_id: columnIdNum,
				title: taskTitle,
				priority: "Medium",
			});
			
			// Transform API task to frontend format
			// API may return id as number or string, ensure it's formatted as "task-{id}"
			const taskIdStr = String(newTask.id);
			const taskId = taskIdStr.startsWith("task-") ? taskIdStr : `task-${taskIdStr}`;
			const newTaskData: Task = {
				id: taskId,
				title: newTask.title,
				priority: newTask.priority as TaskPriority,
				assignee: newTask.assignee_ids || [],
				assignees: newTask.assignees || [],
				tags: newTask.tags || [],
				date: newTask.due_date,
				description: newTask.description,
				attachments: newTask.attachments || [],
			};
			
			// Update state optimistically
			setState((prevState) => {
				const column = prevState.columns[columnId];
				if (!column) {
					// Column doesn't exist, return previous state (will reload on error)
					return prevState;
				}
				
				return {
					...prevState,
					tasks: {
						...prevState.tasks,
						[taskId]: newTaskData,
					},
					columns: {
						...prevState.columns,
						[columnId]: {
							...column,
							taskIds: [...column.taskIds, taskId],
						},
					},
				};
			});
		} catch (error: any) {
			toast.error("Failed to create task: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const deleteColumn = async (columnId: string) => {
		try {
			const columnIdNum = parseInt(columnId.replace("column-", ""));
			const column = state.columns[columnId];
			
			// Update state optimistically
			setState((prevState) => {
				const newColumns = { ...prevState.columns };
				const newTasks = { ...prevState.tasks };
				
				// Remove all tasks in this column
				if (column) {
					column.taskIds.forEach((taskId) => {
						delete newTasks[taskId];
					});
				}
				
				// Remove the column
				delete newColumns[columnId];
				
				// Remove from columnOrder
				const newColumnOrder = prevState.columnOrder.filter((id) => id !== columnId);
				
				return {
					...prevState,
					columns: newColumns,
					tasks: newTasks,
					columnOrder: newColumnOrder,
				};
			});
			
			// Then delete in backend
			await tasksService.deleteColumn(columnIdNum);
		} catch (error: any) {
			toast.error("Failed to delete column: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const clearColumn = async (columnId: string) => {
		try {
			const column = state.columns[columnId];
			
			if (!column) {
				toast.error("Column not found");
				return;
			}
			
			// Update state optimistically
			setState((prevState) => {
				const newTasks = { ...prevState.tasks };
				const taskIdsToDelete = column.taskIds;
				
				// Remove all tasks in this column
				taskIdsToDelete.forEach((taskId) => {
					delete newTasks[taskId];
				});
				
				// Clear taskIds from the column
				const newColumns = {
					...prevState.columns,
					[columnId]: {
						...prevState.columns[columnId],
						taskIds: [],
					},
				};
				
				return {
					...prevState,
					tasks: newTasks,
					columns: newColumns,
				};
			});
			
			// Then delete all tasks in the column in backend
			for (const taskId of column.taskIds) {
				const taskIdNum = parseInt(taskId.replace("task-", ""));
				await tasksService.deleteTask(taskIdNum);
			}
		} catch (error: any) {
			toast.error("Failed to clear column: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const renameColumn = async (column: Column) => {
		try {
			const columnId = parseInt(column.id.replace("column-", ""));
			
			// Update state optimistically
			setState((prevState) => ({
				...prevState,
				columns: {
					...prevState.columns,
					[column.id]: {
						...prevState.columns[column.id],
						title: column.title,
					},
				},
			}));
			
			// Then update in backend
			await tasksService.updateColumn(columnId, { title: column.title });
		} catch (error: any) {
			toast.error("Failed to rename column: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const deleteTask = async (taskId: string) => {
		try {
			const taskIdNum = parseInt(taskId.replace("task-", ""));
			
			// Find which column contains this task
			const columnId = Object.keys(state.columns).find((colId) =>
				state.columns[colId].taskIds.includes(taskId)
			);
			
			// Update state optimistically
			setState((prevState) => {
				const newTasks = { ...prevState.tasks };
				delete newTasks[taskId];
				
				if (columnId && prevState.columns[columnId]) {
					const newColumns = {
						...prevState.columns,
						[columnId]: {
							...prevState.columns[columnId],
							taskIds: prevState.columns[columnId].taskIds.filter((id) => id !== taskId),
						},
					};
					
					return {
						...prevState,
						tasks: newTasks,
						columns: newColumns,
					};
				}
				
				return {
					...prevState,
					tasks: newTasks,
				};
			});
			
			// Then delete in backend
			await tasksService.deleteTask(taskIdNum);
		} catch (error: any) {
			toast.error("Failed to delete task: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const moveTaskToColumn = async (taskId: string, newColumnId: string) => {
		try {
			const taskIdNum = parseInt(taskId.replace("task-", ""));
			const newColumnIdNum = parseInt(newColumnId.replace("column-", ""));
			
			// Find current column
			const currentColumnId = Object.keys(state.columns).find((colId) =>
				state.columns[colId].taskIds.includes(taskId)
			);
			
			if (!currentColumnId || currentColumnId === newColumnId) {
				return;
			}
			
			const currentColumn = state.columns[currentColumnId];
			const newColumn = state.columns[newColumnId];
			
			// Update state optimistically
			setState((prevState) => {
				const sourceTaskIds = currentColumn.taskIds.filter((id) => id !== taskId);
				const destinationTaskIds = [...newColumn.taskIds, taskId];
				
				return {
					...prevState,
					columns: {
						...prevState.columns,
						[currentColumnId]: {
							...currentColumn,
							taskIds: sourceTaskIds,
						},
						[newColumnId]: {
							...newColumn,
							taskIds: destinationTaskIds,
						},
					},
				};
			});
			
			// Then update in backend
			const newPosition = state.columns[newColumnId].taskIds.length;
			await tasksService.updateTask(taskIdNum, { column_id: newColumnIdNum, position: newPosition });
		} catch (error: any) {
			toast.error("Failed to move task: " + (error.message || "Unknown error"));
			// Reload on error to get correct state
			await loadBoardData();
		}
	};

	const updateTask = async (taskId: string, updates: Partial<Task>) => {
		try {
			const taskIdNum = parseInt(taskId.replace("task-", ""));
			
			// Prepare update payload - ensure all fields are included
			const updatePayload: any = {};
			
			if (updates.title !== undefined) {
				updatePayload.title = updates.title;
			}
			if (updates.description !== undefined) {
				updatePayload.description = updates.description || null;
			}
			if (updates.priority !== undefined) {
				updatePayload.priority = updates.priority;
			}
			if (updates.assignee !== undefined) {
				updatePayload.assignee_ids = updates.assignee || [];
			}
			if (updates.tags !== undefined) {
				updatePayload.tags = updates.tags || [];
			}
			if (updates.date !== undefined) {
				updatePayload.due_date = updates.date 
					? (typeof updates.date === "string" 
						? updates.date 
						: updates.date.toISOString().split("T")[0])
					: null;
			}
			if (updates.attachments !== undefined) {
				updatePayload.attachments = updates.attachments || [];
			}
			
			// Update local state optimistically first
			if (state.tasks[taskId]) {
				const currentTask = state.tasks[taskId];
				setState({
					...state,
					tasks: {
						...state.tasks,
						[taskId]: {
							...currentTask,
							...updates,
							// Ensure date is properly formatted
							date: updates.date !== undefined 
								? (typeof updates.date === "string" ? updates.date : updates.date)
								: currentTask.date,
						},
					},
				});
			}
			
			// Then update in backend
			await tasksService.updateTask(taskIdNum, updatePayload);
			// Don't reload board data - keep drawer open and use optimistic update
		} catch (error: any) {
			// On error, reload board data to get correct state
			await loadBoardData();
			toast.error("Failed to update task: " + (error.message || "Unknown error"));
			throw error; // Re-throw so caller knows it failed
		}
	};

	if (loading) {
		return (
			<div className="flex h-full items-center justify-center">
				<div>Loading tasks...</div>
			</div>
		);
	}

	return (
		<ScrollArea type="hover">
			<div className="flex w-full">
				<DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
					<div className="flex h-full items-start gap-6 p-1">
						<SortableContext items={state.columnOrder} strategy={horizontalListSortingStrategy}>
							{state.columnOrder.map((columnId, index) => {
								const column = state.columns[columnId];
								const tasks = column.taskIds.map((taskId) => state.tasks[taskId]).filter(Boolean);

								return (
									<KanbanColumn
										key={columnId}
										id={columnId}
										index={index}
										column={column}
										tasks={tasks}
										createTask={createTask}
										clearColumn={clearColumn}
										deleteColumn={deleteColumn}
										renameColumn={renameColumn}
										onUpdateTask={updateTask}
										onDeleteTask={deleteTask}
										onMoveTaskToColumn={moveTaskToColumn}
										allColumns={Object.values(state.columns)}
									/>
								);
							})}
						</SortableContext>

						<DragOverlay>
							{activeId && activeType === "column" ? (
								<KanbanColumn
									id={activeId}
									index={state.columnOrder.indexOf(activeId)}
									column={state.columns[activeId]}
									tasks={state.columns[activeId].taskIds.map((id) => state.tasks[id]).filter(Boolean)}
									createTask={createTask}
									clearColumn={clearColumn}
									deleteColumn={deleteColumn}
									renameColumn={renameColumn}
									onUpdateTask={updateTask}
									onDeleteTask={deleteTask}
									onMoveTaskToColumn={moveTaskToColumn}
									allColumns={Object.values(state.columns)}
									isDragging
								/>
							) : null}
							{activeId && activeType === "task" ? (
								<KanbanTask
									id={activeId}
									task={state.tasks[activeId]}
									isDragging
									onDelete={deleteTask}
									onUpdate={updateTask}
								/>
							) : null}
						</DragOverlay>
					</div>
				</DndContext>

				<div className="ml-[1.6rem] mt-[0.25rem] min-w-[280px]">
					{addingColumn ? (
						<Input ref={inputRef} placeholder="Column Name" autoFocus />
					) : (
						<Button
							variant="outline"
							onClick={(e) => {
								e.stopPropagation();
								setAddingColumn(true);
							}}
							className="inline-flex! w-full! items-center justify-center text-xs! font-semibold!"
						>
							<Icon icon="carbon:add" size={20} />
							<div>Add Column</div>
						</Button>
					)}
				</div>
			</div>
			<ScrollBar orientation="horizontal" />
		</ScrollArea>
	);
}
