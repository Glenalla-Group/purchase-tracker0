-- Final migration script to create Tasks, Task Columns, and Task Comments tables
-- Database: AWS PostgreSQL
-- This is the consolidated migration that includes all task-related schema changes

-- Create task_columns table (Kanban board columns)
CREATE TABLE IF NOT EXISTS task_columns (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

COMMENT ON TABLE task_columns IS 'Stores kanban board columns (e.g., "To Do", "In Progress", "Done")';
COMMENT ON COLUMN task_columns.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN task_columns.title IS 'Column title/name';
COMMENT ON COLUMN task_columns.position IS 'Order/position of column in the board';
COMMENT ON COLUMN task_columns.created_at IS 'Timestamp when column was created';
COMMENT ON COLUMN task_columns.updated_at IS 'Timestamp when column was last updated';

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    column_id INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
    assignee_ids TEXT,  -- JSON array of user IDs: "[1, 2, 3]"
    tags TEXT,  -- JSON array of tags: '["FrontEnd", "BackEnd"]'
    due_date DATE,
    attachments TEXT,  -- JSON array of attachment URLs
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_task_column FOREIGN KEY (column_id) REFERENCES task_columns(id) ON DELETE CASCADE,
    CONSTRAINT chk_task_priority CHECK (priority IN ('Low', 'Medium', 'High'))
);

COMMENT ON TABLE tasks IS 'Stores individual tasks in the kanban board';
COMMENT ON COLUMN tasks.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN tasks.column_id IS 'Foreign key to task_columns table';
COMMENT ON COLUMN tasks.title IS 'Task title';
COMMENT ON COLUMN tasks.description IS 'Task description/details';
COMMENT ON COLUMN tasks.priority IS 'Task priority: Low, Medium, High';
COMMENT ON COLUMN tasks.assignee_ids IS 'JSON array of user IDs assigned to the task';
COMMENT ON COLUMN tasks.tags IS 'JSON array of tags';
COMMENT ON COLUMN tasks.due_date IS 'Task due date';
COMMENT ON COLUMN tasks.attachments IS 'JSON array of attachment URLs';
COMMENT ON COLUMN tasks.position IS 'Position/order of task within column';
COMMENT ON COLUMN tasks.created_at IS 'Timestamp when task was created';
COMMENT ON COLUMN tasks.updated_at IS 'Timestamp when task was last updated';

-- Create task_comments table
CREATE TABLE IF NOT EXISTS task_comments (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_comment_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_comment_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMENT ON TABLE task_comments IS 'Stores comments on tasks';
COMMENT ON COLUMN task_comments.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN task_comments.task_id IS 'Foreign key to tasks table';
COMMENT ON COLUMN task_comments.user_id IS 'Foreign key to users table (comment author)';
COMMENT ON COLUMN task_comments.content IS 'Comment content/text';
COMMENT ON COLUMN task_comments.created_at IS 'Timestamp when comment was created';
COMMENT ON COLUMN task_comments.updated_at IS 'Timestamp when comment was last updated';

-- Create indexes for task_columns
CREATE INDEX IF NOT EXISTS idx_task_columns_position ON task_columns(position);

-- Create indexes for tasks
CREATE INDEX IF NOT EXISTS idx_tasks_column_id ON tasks(column_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_position ON tasks(column_id, position);

-- Create indexes for task_comments
CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_user_id ON task_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_created_at ON task_comments(created_at);

-- Create triggers to automatically update updated_at (drop first if exists)
DROP TRIGGER IF EXISTS update_task_columns_updated_at ON task_columns;
CREATE TRIGGER update_task_columns_updated_at
    BEFORE UPDATE ON task_columns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_task_comments_updated_at ON task_comments;
CREATE TRIGGER update_task_comments_updated_at
    BEFORE UPDATE ON task_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default columns (if they don't exist)
-- Note: This will only insert if no columns exist yet
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM task_columns) THEN
        INSERT INTO task_columns (title, position) VALUES
            ('To Do', 0),
            ('In Progress', 1),
            ('Done', 2);
    END IF;
END $$;

