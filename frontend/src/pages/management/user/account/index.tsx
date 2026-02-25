import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select";
import { Badge } from "@/ui/badge";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import accountService, { type User, type Role } from "@/api/services/accountService";
import Icon from "@/components/icon/icon";
import { DataTable } from "@/components/data-table";
import type { ColumnDef, PaginationState } from "@tanstack/react-table";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/ui/alert-dialog";
import { Label } from "@/ui/label";
import { useUserInfo } from "@/store/userStore";

export default function AccountManagement() {
	const currentUser = useUserInfo();
	const [userData, setUserData] = useState<User[]>([]);
	const [roles, setRoles] = useState<Role[]>([]);
	const [loading, setLoading] = useState(false);
	const [total, setTotal] = useState(0);
	const [searchTerm, setSearchTerm] = useState("");
	const [filterRole, setFilterRole] = useState<string>("");
	const [filterStatus, setFilterStatus] = useState<string>("");
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: 10,
	});

	// Dialog states
	const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
	const [isEditRoleDialogOpen, setIsEditRoleDialogOpen] = useState(false);
	const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
	const [selectedUser, setSelectedUser] = useState<User | null>(null);

	// Form states
	const [newUser, setNewUser] = useState({
		username: "",
		email: "",
		password: "",
		role_id: 2, // Default to 'user' role
		is_active: true,
	});
	const [editRoleId, setEditRoleId] = useState<number>(2);

	// Load roles on mount
	useEffect(() => {
		loadRoles();
	}, []);

	// Load users when pagination or filters change
	useEffect(() => {
		loadUsers();
	}, [pagination, searchTerm, filterRole, filterStatus]);

	const loadRoles = async () => {
		try {
			const response = await accountService.listRoles();
			setRoles(response || []);
		} catch (error: any) {
			console.error("Failed to load roles:", error);
			toast.error(error.response?.data?.detail || "Failed to load roles");
		}
	};

	const loadUsers = async () => {
		setLoading(true);
		try {
			const params: any = {
				skip: pagination.pageIndex * pagination.pageSize,
				limit: pagination.pageSize,
			};

			if (searchTerm) params.search = searchTerm;
			if (filterRole) params.role_id = parseInt(filterRole);
			if (filterStatus !== "") params.is_active = filterStatus === "active";

			const response = await accountService.listUsers(params);

			setUserData(response.users || []);
			setTotal(response.total || 0);
		} catch (error: any) {
			console.error("Failed to load users:", error);
			toast.error(error.response?.data?.detail || "Failed to load users");
		} finally {
			setLoading(false);
		}
	};

	const handleCreateUser = async () => {
		if (!newUser.username || !newUser.email || !newUser.password) {
			toast.error("Please fill in all required fields");
			return;
		}

		try {
			await accountService.createUser(newUser);
			toast.success("User created successfully");
			setIsCreateDialogOpen(false);
			setNewUser({
				username: "",
				email: "",
				password: "",
				role_id: 2,
				is_active: true,
			});
			loadUsers();
		} catch (error: any) {
			console.error("Failed to create user:", error);
			const errorMessage = error?.response?.data?.detail || error?.message || "Failed to create user";
			toast.error(errorMessage);
		}
	};

	const handleUpdateRole = async () => {
		if (!selectedUser) return;

		try {
			await accountService.updateUserRole(selectedUser.id, { role_id: editRoleId });
			toast.success("User role updated successfully");
			setIsEditRoleDialogOpen(false);
			setSelectedUser(null);
			loadUsers();
		} catch (error: any) {
			console.error("Failed to update role:", error);
			toast.error(error.response?.data?.detail || "Failed to update role");
		}
	};

	const handleToggleStatus = async (user: User) => {
		try {
			await accountService.updateUserStatus(user.id, { is_active: !user.is_active });
			toast.success(`User ${!user.is_active ? "activated" : "deactivated"} successfully`);
			loadUsers();
		} catch (error: any) {
			console.error("Failed to update status:", error);
			toast.error(error.response?.data?.detail || "Failed to update status");
		}
	};

	const handleDeleteUser = async () => {
		if (!selectedUser) return;

		try {
			await accountService.deleteUser(selectedUser.id);
			toast.success("User deleted successfully");
			setIsDeleteDialogOpen(false);
			setSelectedUser(null);
			loadUsers();
		} catch (error: any) {
			console.error("Failed to delete user:", error);
			toast.error(error.response?.data?.detail || "Failed to delete user");
		}
	};

	const openEditRoleDialog = (user: User) => {
		setSelectedUser(user);
		setEditRoleId(user.role_id);
		setIsEditRoleDialogOpen(true);
	};

	const openDeleteDialog = (user: User) => {
		setSelectedUser(user);
		setIsDeleteDialogOpen(true);
	};

	// Calculate pageCount for pagination
	const pageCount = useMemo(() => {
		return Math.ceil(total / pagination.pageSize);
	}, [total, pagination.pageSize]);

	// Define table columns
	const columns = useMemo<ColumnDef<User>[]>(
		() => [
			{
				accessorKey: "id",
				header: "No",
				size: 40,
				minSize: 40,
				enableSorting: false,
				cell: ({ row }) => {
					const index = pagination.pageIndex * pagination.pageSize + row.index + 1;
					return <span className="font-medium">{index}</span>;
				},
			},
			{
				accessorKey: "username",
				header: "Full Name",
				size: 200,
				minSize: 150,
			},
			{
				accessorKey: "email",
				header: "Email",
				size: 280,
				minSize: 260,
			},
			{
				accessorKey: "role_name",
				header: "Role",
				size: 120,
				cell: ({ row }) => {
					const role = row.original.role_name;
					return (
						<Badge variant={role === "admin" ? "default" : "secondary"}>
							{role}
						</Badge>
					);
				},
			},
			{
				accessorKey: "is_active",
				header: "Status",
				size: 120,
				cell: ({ row }) => {
					const isActive = row.original.is_active;
					return (
						<Badge variant={isActive ? "success" : "destructive"}>
							{isActive ? "Active" : "Inactive"}
						</Badge>
					);
				},
			},
			{
				accessorKey: "oauth_provider",
				header: "Auth Method",
				size: 120,
				cell: ({ row }) => {
					const provider = row.original.oauth_provider;
					if (provider === "google") {
						return (
							<Badge variant="outline">
								<Icon icon="logos:google-icon" className="mr-1" size={14} />
								Google
							</Badge>
						);
					}
					return <Badge variant="outline">Email</Badge>;
				},
			},
			{
				accessorKey: "created_at",
				header: "Created",
				size: 120,
				minSize: 100,
				maxSize: 180,
				cell: ({ row }) => {
					if (!row.original.created_at) {
						return <span className="text-gray-400 italic text-sm">—</span>;
					}
					const date = new Date(row.original.created_at);
					const dateStr = date.toLocaleDateString('en-US', { 
						month: 'numeric', 
						day: 'numeric',
						year: 'numeric'
					});
					const timeStr = date.toLocaleTimeString('en-US', { 
						hour: '2-digit', 
						minute: '2-digit',
						hour12: true 
					});
					return (
						<div className="flex flex-col text-xs leading-tight">
							<span className="text-gray-700 dark:text-gray-300 font-medium">{dateStr}</span>
							<span className="text-gray-500 dark:text-gray-500">{timeStr}</span>
						</div>
					);
				},
			},
			{
				accessorKey: "last_login",
				header: "Last Login",
				size: 120,
				minSize: 100,
				maxSize: 180,
				cell: ({ row }) => {
					const lastLogin = row.original.last_login;
					if (!lastLogin) {
						return <span className="text-gray-400 italic text-sm">Never</span>;
					}
					const date = new Date(lastLogin);
					const dateStr = date.toLocaleDateString('en-US', { 
						month: 'numeric', 
						day: 'numeric',
						year: 'numeric'
					});
					const timeStr = date.toLocaleTimeString('en-US', { 
						hour: '2-digit', 
						minute: '2-digit',
						hour12: true 
					});
					return (
						<div className="flex flex-col text-xs leading-tight">
							<span className="text-gray-700 dark:text-gray-300 font-medium">{dateStr}</span>
							<span className="text-gray-500 dark:text-gray-500">{timeStr}</span>
						</div>
					);
				},
			},
			{
				id: "actions",
				header: "Actions",
				size: 200,
				minSize: 200,
				meta: {
					sticky: true,
				},
				cell: ({ row }) => {
					const user = row.original;
					const isCurrentUser = user.id === Number(currentUser?.id);

					return (
						<div className="flex gap-2">
							<Button
								variant="ghost"
								size="sm"
								onClick={() => openEditRoleDialog(user)}
								disabled={isCurrentUser}
								title={isCurrentUser ? "Cannot change your own role" : "Change role"}
							>
								<Icon icon="mdi:account-edit" size={18} />
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={() => handleToggleStatus(user)}
								disabled={isCurrentUser}
								title={
									isCurrentUser
										? "Cannot change your own status"
										: user.is_active
											? "Deactivate"
											: "Activate"
								}
							>
								<Icon
									icon={user.is_active ? "mdi:account-cancel" : "mdi:account-check"}
									size={18}
									className={user.is_active ? "text-orange-500" : "text-green-500"}
								/>
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={() => openDeleteDialog(user)}
								disabled={isCurrentUser}
								title={isCurrentUser ? "Cannot delete your own account" : "Delete user"}
							>
								<Icon icon="mdi:delete" size={18} className="text-red-500" />
							</Button>
						</div>
					);
				},
			},
		],
		[currentUser?.id, pagination],
	);

	return (
		<div className="flex flex-col gap-4 p-4">
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center justify-between">
						<div className="flex items-center gap-2">
							<Icon icon="mdi:account-group" size={24} />
							<span>Account Management</span>
						</div>
						<Button onClick={() => setIsCreateDialogOpen(true)}>
							<Icon icon="mdi:account-plus" size={18} className="mr-2" />
							Create User
						</Button>
					</CardTitle>
				</CardHeader>
				<CardContent>
					{/* Search and Filters */}
					<div className="mb-4 flex flex-wrap gap-4">
						<Input
							placeholder="Search by full name or email..."
							value={searchTerm}
							onChange={(e) => setSearchTerm(e.target.value)}
							className="w-64"
						/>
						<Select value={filterRole || "all"} onValueChange={(value) => setFilterRole(value === "all" ? "" : value)}>
							<SelectTrigger className="w-40">
								<SelectValue placeholder="All Roles" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="all">All Roles</SelectItem>
								{roles.map((role) => (
									<SelectItem key={role.id} value={role.id.toString()}>
										{role.name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
						<Select value={filterStatus || "all"} onValueChange={(value) => setFilterStatus(value === "all" ? "" : value)}>
							<SelectTrigger className="w-40">
								<SelectValue placeholder="All Status" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="all">All Status</SelectItem>
								<SelectItem value="active">Active</SelectItem>
								<SelectItem value="inactive">Inactive</SelectItem>
							</SelectContent>
						</Select>
						{(searchTerm || filterRole || filterStatus) && (
							<Button
								variant="outline"
								onClick={() => {
									setSearchTerm("");
									setFilterRole("");
									setFilterStatus("");
								}}
							>
								<Icon icon="mdi:filter-off" size={18} className="mr-2" />
								Clear Filters
							</Button>
						)}
					</div>

					{/* Users Table */}
					<DataTable
						columns={columns}
						data={userData}
						loading={loading}
						pageCount={pageCount}
						pageIndex={pagination.pageIndex}
						pageSize={pagination.pageSize}
						totalItems={total}
						onPaginationChange={setPagination}
						manualPagination={true}
					/>
				</CardContent>
			</Card>

			{/* Create User Dialog */}
			<Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>Create New User</DialogTitle>
						<DialogDescription>
							Create a new user account. They will be able to log in with the provided credentials.
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid gap-2">
							<Label htmlFor="username">Full Name *</Label>
							<Input
								id="username"
								value={newUser.username}
								onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
								placeholder="Enter full name"
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="email">Email *</Label>
							<Input
								id="email"
								type="email"
								value={newUser.email}
								onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
								placeholder="Enter email"
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="password">Password *</Label>
							<Input
								id="password"
								type="password"
								value={newUser.password}
								onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
								placeholder="Enter password"
							/>
						</div>
						<div className="grid gap-2">
							<Label htmlFor="role">Role</Label>
							<Select
								value={newUser.role_id.toString()}
								onValueChange={(value) => setNewUser({ ...newUser, role_id: parseInt(value) })}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{roles.map((role) => (
										<SelectItem key={role.id} value={role.id.toString()}>
											{role.name}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<div className="flex items-center gap-2">
							<input
								type="checkbox"
								id="is_active"
								checked={newUser.is_active}
								onChange={(e) => setNewUser({ ...newUser, is_active: e.target.checked })}
								className="h-4 w-4"
							/>
							<Label htmlFor="is_active" className="cursor-pointer">
								Active account
							</Label>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleCreateUser}>Create User</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Edit Role Dialog */}
			<Dialog open={isEditRoleDialogOpen} onOpenChange={setIsEditRoleDialogOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>Change User Role</DialogTitle>
						<DialogDescription>
							Update the role for <strong>{selectedUser?.username}</strong>
						</DialogDescription>
					</DialogHeader>
					<div className="grid gap-4 py-4">
						<div className="grid gap-2">
							<Label htmlFor="edit-role">Role</Label>
							<Select value={editRoleId.toString()} onValueChange={(value) => setEditRoleId(parseInt(value))}>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{roles.map((role) => (
										<SelectItem key={role.id} value={role.id.toString()}>
											{role.name}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
					</div>
					<DialogFooter>
						<Button variant="outline" onClick={() => setIsEditRoleDialogOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleUpdateRole}>Update Role</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete User Confirmation Dialog */}
			<AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Are you sure?</AlertDialogTitle>
						<AlertDialogDescription>
							This will permanently delete the user <strong>{selectedUser?.username}</strong>. This action
							cannot be undone.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleDeleteUser} className="bg-red-600 hover:bg-red-700">
							Delete
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}

