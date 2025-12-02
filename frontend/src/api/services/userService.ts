import apiClient from "../apiClient";

import type { UserInfo, UserToken } from "#/entity";

export interface SignInReq {
	email: string;
	password: string;
}

export interface SignUpReq {
	username: string;
	email: string;
	password: string;
}
export type SignInRes = UserToken & { user: UserInfo };

export interface ForgotPasswordReq {
	email: string;
}

export interface ResetPasswordReq {
	token: string;
	new_password: string;
}

export enum UserApi {
	SignIn = "/auth/signin",
	SignUp = "/auth/signup",
	Logout = "/auth/logout",
	Refresh = "/auth/refresh",
	User = "/user",
	ForgotPassword = "/auth/forgot-password",
	ResetPassword = "/auth/reset-password",
	GoogleLogin = "/auth/google/login",
}

const signin = (data: SignInReq) => apiClient.post<SignInRes>({ url: UserApi.SignIn, data });
const signup = (data: SignUpReq) => apiClient.post<SignInRes>({ url: UserApi.SignUp, data });
const logout = () => apiClient.get({ url: UserApi.Logout });
const findById = (id: string) => apiClient.get<UserInfo[]>({ url: `${UserApi.User}/${id}` });
const forgotPassword = (data: ForgotPasswordReq) => apiClient.post({ url: UserApi.ForgotPassword, data });
const resetPassword = (data: ResetPasswordReq) => apiClient.post({ url: UserApi.ResetPassword, data });

export default {
	signin,
	signup,
	findById,
	logout,
	forgotPassword,
	resetPassword,
};
