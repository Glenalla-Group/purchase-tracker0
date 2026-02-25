import apiClient from "../apiClient";

export interface User {
	id: number;
	username: string;
	email: string;
	role_id: number;
	role_name: string;
	is_active: boolean;
	oauth_provider?: string;
	created_at: string;
	last_login?: string;
}

export interface ListUsersResponse {
	users: User[];
	total: number;
	skip: number;
	limit: number;
}

export interface UpdateUserRoleReq {
	role_id: number;
}

export interface UpdateUserStatusReq {
	is_active: boolean;
}

export interface CreateUserReq {
	username: string;
	email: string;
	password: string;
	role_id: number;
	is_active: boolean;
}

export interface Role {
	id: number;
	name: string;
	description?: string;
}

export enum AccountApi {
	ListUsers = "/admin/users",
	GetUser = "/admin/users",
	UpdateUserRole = "/admin/users",
	UpdateUserStatus = "/admin/users",
	DeleteUser = "/admin/users",
	CreateUser = "/admin/users",
	ListRoles = "/admin/roles",
}

const listUsers = (params?: {
	skip?: number;
	limit?: number;
	search?: string;
	role_id?: number;
	is_active?: boolean;
}) => apiClient.get<ListUsersResponse>({ url: AccountApi.ListUsers, params });

const getUser = (userId: number) =>
	apiClient.get<User>({ url: `${AccountApi.GetUser}/${userId}` });

const updateUserRole = (userId: number, data: UpdateUserRoleReq) =>
	apiClient.put<User>({ url: `${AccountApi.UpdateUserRole}/${userId}/role`, data });

const updateUserStatus = (userId: number, data: UpdateUserStatusReq) =>
	apiClient.put<User>({ url: `${AccountApi.UpdateUserStatus}/${userId}/status`, data });

const deleteUser = (userId: number) =>
	apiClient.delete({ url: `${AccountApi.DeleteUser}/${userId}` });

const createUser = (data: CreateUserReq) =>
	apiClient.post<User>({ url: AccountApi.CreateUser, data });

const listRoles = () => apiClient.get<Role[]>({ url: AccountApi.ListRoles });

export default {
	listUsers,
	getUser,
	updateUserRole,
	updateUserStatus,
	deleteUser,
	createUser,
	listRoles,
};


