import { GLOBAL_CONFIG } from "@/global-config";
import { t } from "@/locales/i18n";
import userStore from "@/store/userStore";
import axios, { type AxiosRequestConfig, type AxiosError, type AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { toast } from "sonner";
import type { Result } from "#/api";
import { ResultStatus } from "#/enum";

const axiosInstance = axios.create({
	baseURL: GLOBAL_CONFIG.apiBaseUrl,
	timeout: 50000,
	headers: { "Content-Type": "application/json;charset=utf-8" },
});

// Flag to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
	resolve: (value?: any) => void;
	reject: (error?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
	failedQueue.forEach((prom) => {
		if (error) {
			prom.reject(error);
		} else {
			prom.resolve(token);
		}
	});
	failedQueue = [];
};

const refreshToken = async (): Promise<string | null> => {
	const { userToken } = userStore.getState();
	if (!userToken?.refreshToken) {
		return null;
	}

	try {
		const response = await axios.post(
			`${GLOBAL_CONFIG.apiBaseUrl}/auth/refresh`,
			{},
			{
				headers: {
					Authorization: `Bearer ${userToken.refreshToken}`,
				},
			}
		);

		// Backend returns: { status: 200, message: "...", data: { accessToken: "...", refreshToken: "..." } }
		const responseData = response.data as any;
		if (responseData?.status === 200 && responseData?.data?.accessToken) {
			const newAccessToken = responseData.data.accessToken;
			const newRefreshToken = responseData.data.refreshToken || userToken.refreshToken;
			
			// Update tokens in store
			userStore.getState().actions.setUserToken({
				accessToken: newAccessToken,
				refreshToken: newRefreshToken,
			});
			
			return newAccessToken;
		}
		return null;
	} catch (error) {
		// Refresh failed, logout user
		userStore.getState().actions.clearUserInfoAndToken();
		window.location.href = "/auth/login";
		return null;
	}
};

axiosInstance.interceptors.request.use(
	(config: InternalAxiosRequestConfig) => {
		// Get the access token from the user store
		const { userToken } = userStore.getState();
		if (userToken?.accessToken) {
			config.headers.Authorization = `Bearer ${userToken.accessToken}`;
		}
		return config;
	},
	(error) => Promise.reject(error),
);

axiosInstance.interceptors.response.use(
	(res: AxiosResponse<Result<any>>) => {
		if (!res.data) throw new Error(t("sys.api.apiRequestFailed"));
		const { status, data, message } = res.data;
		// Accept both 200 (SUCCESS) and 201 (CREATED) as success status codes
		if (status === ResultStatus.SUCCESS || (status as number) === 201) {
			return data;
		}
		throw new Error(message || t("sys.api.apiRequestFailed"));
	},
	async (error: AxiosError<Result>) => {
		const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
		const { response, message } = error || {};
		
		// Don't try to refresh token for authentication endpoints (login, signup, etc.)
		const isAuthEndpoint = originalRequest?.url?.includes('/auth/signin') || 
		                       originalRequest?.url?.includes('/auth/signup') ||
		                       originalRequest?.url?.includes('/auth/refresh');
		
		// Handle 401 Unauthorized - try to refresh token (but not for auth endpoints)
		if (response?.status === 401 && originalRequest && !originalRequest._retry && !isAuthEndpoint) {
			if (isRefreshing) {
				// If already refreshing, queue this request
				return new Promise((resolve, reject) => {
					failedQueue.push({ resolve, reject });
				})
					.then((token) => {
						if (originalRequest.headers) {
							originalRequest.headers.Authorization = `Bearer ${token}`;
						}
						return axiosInstance(originalRequest);
					})
					.catch((err) => {
						return Promise.reject(err);
					});
			}

			originalRequest._retry = true;
			isRefreshing = true;

			try {
				const newToken = await refreshToken();
				if (newToken) {
					processQueue(null, newToken);
					if (originalRequest.headers) {
						originalRequest.headers.Authorization = `Bearer ${newToken}`;
					}
					return axiosInstance(originalRequest);
				} else {
					processQueue(new Error("Token refresh failed"), null);
					return Promise.reject(error);
				}
			} catch (refreshError) {
				processQueue(refreshError, null);
				return Promise.reject(refreshError);
			} finally {
				isRefreshing = false;
			}
		}
		
		// Handle FastAPI error responses
		let errMsg = message || t("sys.api.errorMessage");
		
		if (response?.data) {
			const data = response.data as any;
			
			// Handle FastAPI detail field (can be string or array)
			if (data.detail) {
				if (typeof data.detail === 'string') {
					errMsg = data.detail;
				} else if (Array.isArray(data.detail)) {
					// Handle Pydantic validation errors
					errMsg = data.detail.map((err: any) => err.msg || err.message).join(', ');
				}
			} else if (data.message) {
				errMsg = data.message;
			}
		}
		
		// Show error toast for all errors, except 401 when we're refreshing token (and it's not an auth endpoint)
		if (response?.status !== 401 || !originalRequest?._retry || isAuthEndpoint) {
			toast.error(errMsg, { position: "top-center", closeButton: true });
		}
		
		return Promise.reject(error);
	},
);

class APIClient {
	get<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return this.request<T>({ ...config, method: "GET" });
	}
	post<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return this.request<T>({ ...config, method: "POST" });
	}
	put<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return this.request<T>({ ...config, method: "PUT" });
	}
	patch<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return this.request<T>({ ...config, method: "PATCH" });
	}
	delete<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return this.request<T>({ ...config, method: "DELETE" });
	}
	request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
		return axiosInstance.request<any, T>(config);
	}
}

export default new APIClient();
