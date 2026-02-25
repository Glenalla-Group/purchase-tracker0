import type { RouteObject } from "react-router";
import { Navigate } from "react-router";
import { Component } from "./utils";

export function getFrontendDashboardRoutes(): RouteObject[] {
	const frontendDashboardRoutes: RouteObject[] = [
		// Main application pages
		{ path: "workbench", element: Component("/pages/dashboard/workbench") },
		{ path: "analysis", element: Component("/pages/dashboard/analysis") },
		{ path: "lead-submittal", element: Component("/pages/dashboard/lead-submittal") },
		{ path: "oa-sourcing", element: Component("/pages/dashboard/oa-sourcing") },
		{ path: "oa-sourcing/:leadId", element: Component("/pages/dashboard/oa-sourcing") },
		{ path: "asin-bank", element: Component("/pages/dashboard/asin-bank") },
		{ path: "retailers", element: Component("/pages/dashboard/retailers") },
		{ path: "purchase-tracker", element: Component("/pages/dashboard/purchase-tracker") },
		{ path: "checkin", element: Component("/pages/dashboard/checkin") },
		
		// Teams pages
		{
			path: "teams",
			children: [
				{ path: "calendar-and-pto", element: Component("/pages/teams/calendar-and-pto") },
				{ path: "tasks", element: Component("/pages/teams/tasks") },
			],
		},
		
		// Management pages
		{
			path: "management",
			children: [
				{
					path: "user",
					children: [
						{ path: "profile", element: Component("/pages/management/user/profile") },
						{ path: "account", element: Component("/pages/management/user/account") },
					],
				},
			],
		},
		
		// Error pages (useful to keep)
		{
			path: "error",
			children: [
				{ index: true, element: <Navigate to="403" replace /> },
				{ path: "403", element: Component("/pages/sys/error/Page403") },
				{ path: "404", element: Component("/pages/sys/error/Page404") },
				{ path: "500", element: Component("/pages/sys/error/Page500") },
			],
		},
		
		// Removed unused demo/template routes:
		// - components (animate, scroll, multi-language, icon, upload, chart, toast)
		// - functions (clipboard, token-expired)
		// - menu_level (nested menu demos)
		// - link (iframe, external-link)
		// - permission (permission demos)
		// - calendar, kanban, blank (other demos)
	];
	
	// Debug: Log route registration
	console.log('[Routes] Frontend dashboard routes registered:', frontendDashboardRoutes.length, 'routes');
	console.log('[Routes] OA Sourcing routes:', frontendDashboardRoutes.filter(r => r.path?.includes('oa-sourcing')).map(r => r.path));
	
	return frontendDashboardRoutes;
}
