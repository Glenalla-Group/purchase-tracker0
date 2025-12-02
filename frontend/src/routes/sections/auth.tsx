import { Suspense, lazy } from "react";
import { Outlet } from "react-router";
import type { RouteObject } from "react-router";

const LoginPage = lazy(() => import("@/pages/sys/login"));
const PasswordResetPage = lazy(() => import("@/pages/sys/login/password-reset-page"));
const OAuthCallback = lazy(() => import("@/pages/sys/login/oauth-callback"));

const authCustom: RouteObject[] = [
	{
		path: "login",
		element: <LoginPage />,
	},
	{
		path: "reset-password",
		element: <PasswordResetPage />,
	},
	{
		path: "callback",
		element: <OAuthCallback />,
	},
];

export const authRoutes: RouteObject[] = [
	{
		path: "auth",
		element: (
			<Suspense>
				<Outlet />
			</Suspense>
		),
		children: [...authCustom],
	},
];
