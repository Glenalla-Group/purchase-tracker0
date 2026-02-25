import { Icon } from "@/components/icon";
import type { NavProps } from "@/components/nav";
// import { Badge } from "@/ui/badge";

export const frontendNavData: NavProps["data"] = [
	{
		name: "sys.nav.dashboard",
		items: [
			// {
			// 	title: "sys.nav.workbench",
			// 	path: "/workbench",
			// 	icon: <Icon icon="local:ic-workbench" size="24" />,
			// },
			{
				title: "sys.nav.analysis",
				path: "/analysis",
				icon: <Icon icon="local:ic-analysis" size="24" />,
			},
			{
				title: "sys.nav.lead-submittal",
				path: "/lead-submittal",
				icon: <Icon icon="mdi:file-document-edit" size="24" />,
			},
			{
				title: "sys.nav.oa-sourcing",
				path: "/oa-sourcing",
				icon: <Icon icon="mdi:package-variant" size="24" />,
			},
			{
				title: "sys.nav.asin-bank",
				path: "/asin-bank",
				icon: <Icon icon="mdi:database" size="24" />,
			},
			{
				title: "sys.nav.retailers",
				path: "/retailers",
				icon: <Icon icon="mdi:store" size="24" />,
			},
			{
				title: "sys.nav.purchase-tracker",
				path: "/purchase-tracker",
				icon: <Icon icon="mdi:cart-check" size="24" />,
			},
			{
				title: "sys.nav.checkin",
				path: "/checkin",
				icon: <Icon icon="mdi:package-variant-closed-check" size="24" />,
			}
		],
	},
	{
		name: "Teams",
		items: [
			{
				title: "Calendar & PTO",
				path: "/teams/calendar-and-pto",
				icon: <Icon icon="mdi:calendar-clock" size="24" />,
			},
			{
				title: "Tasks",
				path: "/teams/tasks",
				icon: <Icon icon="mdi:clipboard-list" size="24" />,
			}
		],
	},
	{
		name: "sys.nav.user.index",
		items: [
			{
				title: "sys.nav.user.profile",
				path: "/management/user/profile",
				icon: <Icon icon="mdi:account-edit" size="24" />,
			},
			{
				title: "sys.nav.accounts",
				path: "/management/user/account",
				icon: <Icon icon="mdi:account-group" size="24" />,
				auth: ["admin"], // Only visible to admin users
			},
		],
	},
];
