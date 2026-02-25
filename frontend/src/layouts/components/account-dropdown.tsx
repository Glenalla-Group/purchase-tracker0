import { useLoginStateContext } from "@/pages/sys/login/providers/login-provider";
import { useRouter } from "@/routes/hooks";
import { useUserActions, useUserInfo } from "@/store/userStore";
import { Button } from "@/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/ui/dropdown-menu";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

/**
 * Account Dropdown
 */
export default function AccountDropdown() {
	const { replace } = useRouter();
	const { username, email, avatar, roles } = useUserInfo();
	const { clearUserInfoAndToken } = useUserActions();
	const { backToLogin } = useLoginStateContext();
	const { t } = useTranslation();
	
	// Check if user is admin
	const isAdmin = roles?.some((role) => role.name === "admin") ?? false;
	
	const logout = () => {
		try {
			clearUserInfoAndToken();
			backToLogin();
		} catch (error) {
			console.log(error);
		} finally {
			replace("/auth/login");
		}
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" size="icon" className="rounded-full">
					<img className="h-6 w-6 rounded-full" src={avatar} alt="" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent className="w-64 min-w-64">
				<div className="flex items-center gap-2 p-2">
					<img className="h-10 w-10 rounded-full shrink-0" src={avatar} alt="" />
					<div className="flex flex-col items-start min-w-0 flex-1 overflow-hidden">
						<div className="text-text-primary text-sm font-medium truncate w-full">{username}</div>
						<div className="text-text-secondary text-xs truncate w-full" title={email}>{email}</div>
					</div>
				</div>
				<DropdownMenuSeparator />
				<DropdownMenuItem asChild>
					<NavLink to="/management/user/profile">{t("sys.nav.user.profile")}</NavLink>
				</DropdownMenuItem>
				{isAdmin && (
					<>
						<DropdownMenuItem asChild>
							<NavLink to="/management/user/account">{t("sys.nav.user.account")}</NavLink>
						</DropdownMenuItem>
					</>
				)}
				<DropdownMenuSeparator />
				<DropdownMenuItem className="font-bold text-warning" onClick={logout}>
					{t("sys.login.logout")}
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
