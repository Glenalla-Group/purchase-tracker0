import type { NavItemDataProps } from "@/components/nav/types";
import { GLOBAL_CONFIG } from "@/global-config";
import { useUserPermissions, useUserRoles } from "@/store/userStore";
import { checkAny } from "@/utils";
import { useMemo } from "react";
import { backendNavData } from "./nav-data-backend";
import { frontendNavData } from "./nav-data-frontend";

const navData = GLOBAL_CONFIG.routerMode === "backend" ? backendNavData : frontendNavData;

/**
 * 递归处理导航数据，过滤掉没有权限的项目
 * @param items 导航项目数组
 * @param permissions 权限列表
 * @param roles 角色列表
 * @returns 过滤后的导航项目数组
 */
const filterItems = (items: NavItemDataProps[], permissions: string[], roles: string[] = []) => {
	return items.filter((item) => {
		// 检查当前项目是否有权限或角色
		let hasPermission = true;
		if (item.auth) {
			// Check if any auth requirement matches permissions or roles
			hasPermission = checkAny(item.auth, [...permissions, ...roles]);
		}

		// 如果有子项目，递归处理
		if (item.children?.length) {
			const filteredChildren = filterItems(item.children, permissions, roles);
			// 如果子项目都被过滤掉了，则过滤掉当前项目
			if (filteredChildren.length === 0) {
				return false;
			}
			// 更新子项目
			item.children = filteredChildren;
		}

		return hasPermission;
	});
};

/**
 *
 * 根据权限和角色过滤导航数据
 * @param permissions 权限列表
 * @param roles 角色列表
 * @returns 过滤后的导航数据
 */
const filterNavData = (permissions: string[], roles: string[] = []) => {
	return navData
		.map((group) => {
			// 过滤组内的项目
			const filteredItems = filterItems(group.items, permissions, roles);

			// 如果组内没有项目了，返回 null
			if (filteredItems.length === 0) {
				return null;
			}

			// 返回过滤后的组
			return {
				...group,
				items: filteredItems,
			};
		})
		.filter((group): group is NonNullable<typeof group> => group !== null); // 过滤掉空组
};

/**
 * Hook to get filtered navigation data based on user permissions and roles
 * @returns Filtered navigation data
 */
export const useFilteredNavData = () => {
	const permissions = useUserPermissions();
	const roles = useUserRoles();
	const permissionCodes = useMemo(() => permissions.map((p) => p.code || p.name), [permissions]);
	const roleNames = useMemo(() => roles.map((r) => r.name), [roles]);
	const filteredNavData = useMemo(() => filterNavData(permissionCodes, roleNames), [permissionCodes, roleNames]);
	return filteredNavData;
};
