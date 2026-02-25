import { down, useMediaQuery } from "@/hooks";
import { useSettings } from "@/store/settingStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import type { DateSelectArg, EventClickArg, EventInput } from "@fullcalendar/core";
import type { EventDragStopArg, EventResizeDoneArg } from "@fullcalendar/interaction";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import listPlugin from "@fullcalendar/list";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayjs from "dayjs";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import CalendarEvent from "./components/calendar-event";
import CalendarHeader, { type HandleMoveArg, type ViewType } from "./components/calendar-header";
import { StyledCalendar } from "./components/styles";
import ptoService, { type PTORequest, type Holiday } from "@/api/services/ptoService";
import apiClient from "@/api/apiClient";
import { toast } from "sonner";
import { useUserInfo } from "@/store/userStore";
import { useAuthCheck } from "@/components/auth/use-auth";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/ui/dialog";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/ui/select";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import { Textarea } from "@/ui/textarea";
import { DataTable } from "@/components/data-table";
import type { ColumnDef } from "@tanstack/react-table";
import { Icon } from "@/components/icon";
import { Title } from "@/ui/typography";

export default function CalendarAndPTO() {
	const fullCalendarRef = useRef<FullCalendar>(null);
	const [view, setView] = useState<ViewType>("dayGridMonth");
	const [date, setDate] = useState(() => dayjs().toDate()); // Default to today
	const [openPTOForm, setOpenPTOForm] = useState(false);
	const [openHolidayForm, setOpenHolidayForm] = useState(false);
	const [events, setEvents] = useState<EventInput[]>([]);
	const [ptoRequests, setPTORequests] = useState<PTORequest[]>([]);
	const [holidays, setHolidays] = useState<Holiday[]>([]);
	const [ptoStats, setPTOStats] = useState<any>(null);
	const [selectedCountry, setSelectedCountry] = useState<string>("BOTH");
	const [statsDateRange, setStatsDateRange] = useState({
		start_date: dayjs().startOf("year").format("YYYY-MM-DD"), // Start of current year
		end_date: dayjs().endOf("year").format("YYYY-MM-DD"), // End of current year
	});
	const [tableFilter, setTableFilter] = useState<"all" | "current-ooo" | "approved" | "pending">("current-ooo");
	const [tableDateRange, setTableDateRange] = useState({
		start_date: dayjs().startOf("week").format("YYYY-MM-DD"),
		end_date: dayjs().endOf("week").format("YYYY-MM-DD"),
	});
	const [holidayFormData, setHolidayFormData] = useState({
		name: "",
		date: dayjs().format("YYYY-MM-DD"),
		country: "BOTH",
		is_recurring: false,
		description: "",
	});
	const [editingPTO, setEditingPTO] = useState<PTORequest | null>(null);
	const [editingHoliday, setEditingHoliday] = useState<Holiday | null>(null);

	const { themeMode } = useSettings();
	const xsBreakPoint = useMediaQuery(down("xs"));
	const userInfo = useUserInfo();
	const userId = userInfo?.id ? parseInt(userInfo.id) : null;
	const { check: checkRole } = useAuthCheck("role");
	const isAdmin = checkRole("admin");
	const [allUsers, setAllUsers] = useState<Array<{ id: number; username: string; email: string }>>([]);
	
	// Initialize PTO form data after userId is available
	const [ptoFormData, setPTOFormData] = useState(() => ({
		user_id: 0,
		start_date: dayjs().format("YYYY-MM-DD"),
		end_date: dayjs().format("YYYY-MM-DD"),
		request_type: "pto" as "pto" | "sick" | "personal" | "holiday",
		reason: "",
		notes: "",
	}));

	// Update user_id when userId becomes available
	useEffect(() => {
		if (userId && !ptoFormData.user_id) {
			setPTOFormData(prev => ({ ...prev, user_id: userId }));
		}
	}, [userId]);

	useEffect(() => {
		if (xsBreakPoint) {
			setView("listWeek");
		}
	}, [xsBreakPoint]);

	// Load calendar events
	const loadCalendarEvents = async () => {
		if (!fullCalendarRef.current) return;

		try {
			const calendarApi = fullCalendarRef.current.getApi();
			const view = calendarApi.view;
			const start = view.activeStart;
			const end = view.activeEnd;

			// Load PTO requests
			const ptoResponse = await ptoService.getPTORequests({
				start_date: dayjs(start).format("YYYY-MM-DD"),
				end_date: dayjs(end).format("YYYY-MM-DD"),
			});

			// Load holidays - use a wider date range to ensure we capture all holidays
			// Load 1 year before and after to catch recurring holidays
			const holidayStartDate = dayjs(start).subtract(1, "year").format("YYYY-MM-DD");
			const holidayEndDate = dayjs(end).add(1, "year").format("YYYY-MM-DD");
			
			const holidayResponse = await ptoService.getCalendarEvents(
				holidayStartDate,
				holidayEndDate,
				selectedCountry === "BOTH" ? undefined : selectedCountry
			);

			// Also load full holiday list for editing (use calendar view range)
			const holidaysResponse = await ptoService.getHolidays({
				start_date: dayjs(start).format("YYYY-MM-DD"),
				end_date: dayjs(end).format("YYYY-MM-DD"),
				country: selectedCountry === "BOTH" ? undefined : selectedCountry,
			});
			setHolidays(holidaysResponse.items);

			// Format PTO requests as calendar events
			const ptoEvents: EventInput[] = ptoResponse.items.map((pto) => {
				// Only allow editing if:
				// - User is admin, OR
				// - PTO is not approved AND (user owns the PTO OR user is admin)
				const canEdit = isAdmin || (pto.status !== "approved" && (pto.user_id === userId || isAdmin));
				const statusIcon = getStatusIcon(pto.status);
				const username = pto.username || "User";
				return {
					id: `pto_${pto.id}`,
					title: `${username} - ${pto.request_type.toUpperCase()}`,
					start: pto.start_date,
					end: dayjs(pto.end_date).add(1, "day").format("YYYY-MM-DD"), // Add 1 day for end date
					allDay: true,
					editable: canEdit,
					durationEditable: canEdit,
					backgroundColor: getPTOColor(pto.status, pto.request_type),
					borderColor: getPTOColor(pto.status, pto.request_type),
					extendedProps: {
						type: "pto",
						ptoId: pto.id,
						user_id: pto.user_id,
						username: pto.username,
						request_type: pto.request_type,
						status: pto.status,
						statusIcon: statusIcon,
						reason: pto.reason,
						notes: pto.notes,
					},
				};
			});

			// Format holidays as calendar events
			const holidayEvents: EventInput[] = holidayResponse.events.map((holiday) => {
				const countryLabel = holiday.extendedProps?.country === "US" 
					? "🇺🇸 US" 
					: holiday.extendedProps?.country === "PH" 
						? "🇵🇭 PH" 
						: holiday.extendedProps?.country === "BOTH"
							? "🌍 BOTH"
							: "";
				const title = countryLabel ? `${countryLabel} ${holiday.title}` : holiday.title;
				return {
					id: holiday.id,
					title: title,
					start: holiday.start,
					end: holiday.end || dayjs(holiday.start).add(1, "day").format("YYYY-MM-DD"), // Ensure end date exists
					allDay: holiday.allDay !== undefined ? holiday.allDay : true,
					editable: isAdmin, // Only admins can edit holidays
					durationEditable: false, // Holidays are single-day events
					backgroundColor: holiday.backgroundColor || "#ff6b6b",
					borderColor: holiday.borderColor || "#ff5252",
					extendedProps: {
						...holiday.extendedProps,
						type: "holiday",
					},
				};
			});

			setEvents([...ptoEvents, ...holidayEvents]);
			setPTORequests(ptoResponse.items);
		} catch (error: any) {
			toast.error("Failed to load calendar events", {
				description: error.message || "An error occurred",
			});
		}
	};

	useEffect(() => {
		loadCalendarEvents();
	}, [date, view, selectedCountry]);

	// Load PTO requests for the table based on tableDateRange
	const loadTablePTORequests = async (merge = false) => {
		try {
			const ptoResponse = await ptoService.getPTORequests({
				start_date: tableDateRange.start_date,
				end_date: tableDateRange.end_date,
			});
			if (merge) {
				// Merge with existing PTO requests to avoid losing calendar data
				setPTORequests((prev) => {
					const existingIds = new Set(prev.map((p) => p.id));
					const newItems = ptoResponse.items.filter((item) => !existingIds.has(item.id));
					return [...prev, ...newItems];
				});
			} else {
				// Replace with new data
				setPTORequests(ptoResponse.items);
			}
		} catch (error: any) {
			toast.error("Failed to load PTO requests", {
				description: error.message || "An error occurred",
			});
		}
	};

	useEffect(() => {
		loadTablePTORequests();
	}, [tableDateRange.start_date, tableDateRange.end_date]);

	// Load PTO stats
	const loadPTOStats = async () => {
		if (!userId) return;

		try {
			const stats = await ptoService.getAllUsersPTOStats({
				start_date: statsDateRange.start_date,
				end_date: statsDateRange.end_date,
			});
			setPTOStats(stats);
		} catch (error: any) {
			console.error("Failed to load PTO stats:", error);
		}
	};

	useEffect(() => {
		loadPTOStats();
	}, [userId, statsDateRange.start_date, statsDateRange.end_date]);

	// Load all users for admin
	const loadAllUsers = async () => {
		if (!isAdmin) return;
		try {
			const response = await apiClient.get<{ status: number; data: { users: Array<{ id: number; username: string; email: string }> } }>({
				url: '/admin/users',
				params: { limit: 1000 },
			});
			const responseData = (response as any).data || response;
			const users = responseData.users || [];
			setAllUsers(users);
		} catch (error: any) {
			console.error("Failed to load users:", error);
		}
	};

	useEffect(() => {
		if (isAdmin) {
			loadAllUsers();
		}
	}, [isAdmin]);

	const getPTOColor = (status: string, type: string): string => {
		if (status === "approved") {
			switch (type) {
				case "pto":
					return "#00a76f";
				case "sick":
					return "#ff5630";
				case "personal":
					return "#8e33ff";
				case "holiday":
					return "#ffab00";
				default:
					return "#00a76f";
			}
		} else if (status === "pending") {
			return "#ffab00";
		} else if (status === "rejected") {
			return "#ff5630";
		}
		return "#8e33ff";
	};

	const getStatusIcon = (status: string): string => {
		switch (status) {
			case "approved":
				return "mdi:check-circle";
			case "pending":
				return "mdi:clock-outline";
			case "rejected":
				return "mdi:close-circle";
			case "cancelled":
				return "mdi:cancel";
			default:
				return "mdi:help-circle";
		}
	};

	/**
	 * calendar header events
	 */
	const handleMove = (action: HandleMoveArg) => {
		const calendarApi = fullCalendarRef.current?.getApi();
		if (!calendarApi) return;
		switch (action) {
			case "prev":
				calendarApi.prev();
				break;
			case "next":
				calendarApi.next();
				break;
			case "today":
				calendarApi.today();
				break;
			default:
				break;
		}
		setDate(calendarApi.getDate());
	};

	const handleViewTypeChange = (view: ViewType) => {
		setView(view);
	};

	useLayoutEffect(() => {
		const calendarApi = fullCalendarRef.current?.getApi();
		if (!calendarApi) return;
		setTimeout(() => {
			calendarApi.changeView(view);
		});
	}, [view]);

	// Ensure calendar navigates to today on initial load
	useEffect(() => {
		// Use setTimeout to ensure calendar is fully initialized
		const timer = setTimeout(() => {
			const calendarApi = fullCalendarRef.current?.getApi();
			if (calendarApi) {
				calendarApi.today();
				setDate(calendarApi.getDate());
			}
		}, 100);
		return () => clearTimeout(timer);
	}, []); // Run only on mount

	/**
	 * calendar grid events
	 */
	const handleDateSelect = (selectInfo: DateSelectArg) => {
		const calendarApi = selectInfo.view.calendar;
		calendarApi.unselect();
		setOpenPTOForm(true);
		setEditingPTO(null);
		setPTOFormData({
			user_id: userId || 0,
			start_date: dayjs(selectInfo.startStr).format("YYYY-MM-DD"),
			end_date: dayjs(selectInfo.endStr).subtract(1, "day").format("YYYY-MM-DD"),
			request_type: "pto",
			reason: "",
			notes: "",
		});
	};

	/**
	 * calendar event events
	 */
	const handleEventClick = (arg: EventClickArg) => {
		const { extendedProps, id } = arg.event;

		if (extendedProps.type === "pto") {
			const ptoId = extendedProps.ptoId;
			const pto = ptoRequests.find((p) => p.id === ptoId);
			if (pto) {
				// Check if user can edit this PTO (admin or own request)
				if (!isAdmin && pto.user_id !== userId) {
					toast.error("You can only edit your own PTO requests");
					return;
				}
				setEditingPTO(pto);
				setPTOFormData({
					user_id: pto.user_id,
					start_date: pto.start_date,
					end_date: pto.end_date,
					request_type: pto.request_type as any,
					reason: pto.reason || "",
					notes: pto.notes || "",
				});
				setOpenPTOForm(true);
			}
		} else if (extendedProps.type === "holiday") {
			if (!isAdmin) {
				toast.info("Only admins can edit holidays");
				return;
			}
			// Handle recurring holiday IDs: holiday_{id}_{year} or holiday_{id}
			const holidayIdStr = id.replace("holiday_", "");
			const holidayIdParts = holidayIdStr.split("_");
			const holidayId = parseInt(holidayIdParts[0]); // Get the base holiday ID
			const holiday = holidays.find((h) => h.id === holidayId);
			if (holiday) {
				setEditingHoliday(holiday);
				setHolidayFormData({
					name: holiday.name,
					date: holiday.date,
					country: holiday.country,
					is_recurring: holiday.is_recurring,
					description: holiday.description || "",
				});
				setOpenHolidayForm(true);
			}
		}
	};

	/**
	 * Handle event drag and drop
	 */
	const handleEventDrop = async (dropInfo: EventDragStopArg) => {
		const { event } = dropInfo;
		const { extendedProps } = event;

		// Handle PTO events
		if (extendedProps.type === "pto") {
			const ptoId = extendedProps.ptoId;
			const pto = ptoRequests.find((p) => p.id === ptoId);
			
			if (!pto) {
				toast.error("PTO request not found");
				loadCalendarEvents(); // Reload to revert
				return;
			}

			// Check permissions: non-admin users cannot move approved PTO requests
			if (!isAdmin && pto.status === "approved") {
				toast.error("Cannot move approved PTO requests");
				loadCalendarEvents(); // Reload to revert
				return;
			}

			// Check if user owns the PTO or is admin
			if (!isAdmin && pto.user_id !== userId) {
				toast.error("You can only move your own PTO requests");
				loadCalendarEvents(); // Reload to revert
				return;
			}

			try {
				const newStartDate = dayjs(event.startStr).format("YYYY-MM-DD");
				// Calculate end date based on original duration
				const originalStartDate = dayjs(pto.start_date);
				const originalEndDate = dayjs(pto.end_date);
				const durationDays = originalEndDate.diff(originalStartDate, "day");
				const newEndDate = dayjs(event.startStr).add(durationDays, "day").format("YYYY-MM-DD");

				await ptoService.updatePTORequest(ptoId, {
					start_date: newStartDate,
					end_date: newEndDate,
				});

				toast.success("PTO request updated successfully");
				loadCalendarEvents();
				loadPTOStats();
			} catch (error: any) {
				toast.error("Failed to update PTO request", {
					description: error.message || "An error occurred",
				});
				loadCalendarEvents(); // Reload to revert
			}
		} 
		// Handle holiday events (admin only)
		else if (extendedProps.type === "holiday") {
			if (!isAdmin) {
				toast.error("Only admins can move holidays");
				loadCalendarEvents(); // Reload to revert
				return;
			}

			// Get holiday ID from extendedProps first (most reliable), then parse from event ID
			let holidayId: number | null = null;
			
			if (extendedProps.holiday_id) {
				holidayId = extendedProps.holiday_id;
			} else {
				// Fallback: Handle recurring holiday IDs: holiday_{id}_{year} or holiday_{id}
				const holidayIdStr = event.id.replace("holiday_", "");
				const holidayIdParts = holidayIdStr.split("_");
				holidayId = parseInt(holidayIdParts[0]); // Get the base holiday ID
			}
			
			if (!holidayId || isNaN(holidayId)) {
				toast.error("Invalid holiday ID");
				loadCalendarEvents(); // Reload to revert
				return;
			}

			// For recurring holidays, we need to handle them differently
			// If it's a recurring holiday instance, we should update the base holiday's date
			// But for non-recurring holidays, we can update directly
			const isRecurring = extendedProps.is_recurring === true;
			
			if (isRecurring) {
				// For recurring holidays, updating the date changes when it occurs each year
				// This is a significant change - we'll update the base holiday date
				try {
					const newDate = dayjs(event.startStr).format("YYYY-MM-DD");
					await ptoService.updateHoliday(holidayId, {
						date: newDate,
					});

					toast.success("Recurring holiday updated successfully");
					loadCalendarEvents();
				} catch (error: any) {
					toast.error("Failed to update recurring holiday", {
						description: error.message || "An error occurred",
					});
					loadCalendarEvents(); // Reload to revert
				}
			} else {
				// For non-recurring holidays, update the date directly
				try {
					const newDate = dayjs(event.startStr).format("YYYY-MM-DD");
					await ptoService.updateHoliday(holidayId, {
						date: newDate,
					});

					toast.success("Holiday updated successfully");
					loadCalendarEvents();
				} catch (error: any) {
					toast.error("Failed to update holiday", {
						description: error.message || "An error occurred",
					});
					loadCalendarEvents(); // Reload to revert
				}
			}
		}
	};

	/**
	 * Handle event resize (duration change)
	 */
	const handleEventResize = async (resizeInfo: EventResizeDoneArg) => {
		const { event } = resizeInfo;
		const { extendedProps } = event;

		// Only handle PTO events (holidays are single-day events, no resize needed)
		if (extendedProps.type !== "pto") {
			return;
		}

		const ptoId = extendedProps.ptoId;
		const pto = ptoRequests.find((p) => p.id === ptoId);
		
		if (!pto) {
			toast.error("PTO request not found");
			loadCalendarEvents(); // Reload to revert
			return;
		}

		// Check permissions: non-admin users cannot resize approved PTO requests
		if (!isAdmin && pto.status === "approved") {
			toast.error("Cannot modify approved PTO requests");
			loadCalendarEvents(); // Reload to revert
			return;
		}

		// Check if user owns the PTO or is admin
		if (!isAdmin && pto.user_id !== userId) {
			toast.error("You can only modify your own PTO requests");
			loadCalendarEvents(); // Reload to revert
			return;
		}

		try {
			const newStartDate = dayjs(event.startStr).format("YYYY-MM-DD");
			const newEndDate = dayjs(event.endStr).subtract(1, "day").format("YYYY-MM-DD"); // Subtract 1 day because FullCalendar adds 1 day to end date

			await ptoService.updatePTORequest(ptoId, {
				start_date: newStartDate,
				end_date: newEndDate,
			});

			toast.success("PTO request updated successfully");
			loadCalendarEvents();
			loadPTOStats();
		} catch (error: any) {
			toast.error("Failed to update PTO request", {
				description: error.message || "An error occurred",
			});
			loadCalendarEvents(); // Reload to revert
		}
	};

	const handlePTOSubmit = async () => {
		const targetUserId = ptoFormData.user_id || userId;
		if (!targetUserId) {
			toast.error("User not found");
			return;
		}

		// Non-admin users can only create/edit their own PTO
		if (!isAdmin && targetUserId !== userId) {
			toast.error("You can only create PTO requests for yourself");
			return;
		}

		// Check if editing someone else's PTO (admin only)
		if (editingPTO && editingPTO.user_id !== targetUserId && !isAdmin) {
			toast.error("You can only edit your own PTO requests");
			return;
		}

		try {
			if (editingPTO) {
				const updateData: any = {
					start_date: ptoFormData.start_date,
					end_date: ptoFormData.end_date,
					request_type: ptoFormData.request_type,
					reason: ptoFormData.reason,
					notes: ptoFormData.notes,
				};
				
				// If admin changed the status, include it and set approved_by
				if (isAdmin && editingPTO.status !== ptoRequests.find(p => p.id === editingPTO.id)?.status) {
					updateData.status = editingPTO.status;
					if (editingPTO.status === "approved" || editingPTO.status === "rejected") {
						updateData.approved_by_id = userId || undefined;
					}
				}
				
				await ptoService.updatePTORequest(editingPTO.id, updateData);
				toast.success("PTO request updated successfully");
			} else {
				await ptoService.createPTORequest({
					user_id: targetUserId,
					start_date: ptoFormData.start_date,
					end_date: ptoFormData.end_date,
					request_type: ptoFormData.request_type,
					reason: ptoFormData.reason,
					notes: ptoFormData.notes,
				});
				toast.success("PTO request created successfully");
			}
			setOpenPTOForm(false);
			setEditingPTO(null);
			loadCalendarEvents();
			loadPTOStats();
		} catch (error: any) {
			toast.error("Failed to save PTO request", {
				description: error.message || "An error occurred",
			});
		}
	};

	const handleApprovePTO = async (ptoId: number) => {
		if (!isAdmin) {
			toast.error("Only admins can approve PTO requests");
			return;
		}

		try {
			await ptoService.updatePTORequest(ptoId, {
				status: "approved",
				approved_by_id: userId || undefined,
			});
			toast.success("PTO request approved");
			loadCalendarEvents();
			loadPTOStats();
		} catch (error: any) {
			toast.error("Failed to approve PTO request", {
				description: error.message || "An error occurred",
			});
		}
	};

	const handleRejectPTO = async (ptoId: number) => {
		if (!isAdmin) {
			toast.error("Only admins can reject PTO requests");
			return;
		}

		try {
			await ptoService.updatePTORequest(ptoId, {
				status: "rejected",
				approved_by_id: userId || undefined,
			});
			toast.success("PTO request rejected");
			loadCalendarEvents();
			loadPTOStats();
		} catch (error: any) {
			toast.error("Failed to reject PTO request", {
				description: error.message || "An error occurred",
			});
		}
	};

	const handleHolidaySubmit = async () => {
		try {
			if (editingHoliday) {
				await ptoService.updateHoliday(editingHoliday.id, {
					name: holidayFormData.name,
					date: holidayFormData.date,
					country: holidayFormData.country,
					is_recurring: holidayFormData.is_recurring,
					description: holidayFormData.description,
				});
				toast.success("Holiday updated successfully");
			} else {
				await ptoService.createHoliday({
					name: holidayFormData.name,
					date: holidayFormData.date,
					country: holidayFormData.country,
					is_recurring: holidayFormData.is_recurring,
					description: holidayFormData.description,
				});
				toast.success("Holiday created successfully");
			}
			setOpenHolidayForm(false);
			setEditingHoliday(null);
			loadCalendarEvents();
		} catch (error: any) {
			toast.error("Failed to save holiday", {
				description: error.message || "An error occurred",
			});
		}
	};

	const handleDeletePTO = async (ptoId: number) => {
		const pto = ptoRequests.find((p) => p.id === ptoId);
		if (!pto) return;

		// Check if user can delete this PTO (admin or own request)
		if (!isAdmin && pto.user_id !== userId) {
			toast.error("You can only delete your own PTO requests");
			return;
		}

		try {
			await ptoService.deletePTORequest(ptoId);
			toast.success("PTO request deleted successfully");
			setOpenPTOForm(false);
			setEditingPTO(null);
			loadCalendarEvents();
			loadPTOStats();
		} catch (error: any) {
			toast.error("Failed to delete PTO request", {
				description: error.message || "An error occurred",
			});
		}
	};

	const handleDeleteHoliday = async (holidayId: number) => {
		try {
			await ptoService.deleteHoliday(holidayId);
			toast.success("Holiday deleted successfully");
			setOpenHolidayForm(false);
			setEditingHoliday(null);
			loadCalendarEvents();
		} catch (error: any) {
			toast.error("Failed to delete holiday", {
				description: error.message || "An error occurred",
			});
		}
	};

	// Filter PTO requests based on selected filter and date range
	const filteredPTORequests = ptoRequests.filter((pto) => {
		const today = dayjs().startOf("day");
		const startDate = dayjs(pto.start_date).startOf("day");
		const endDate = dayjs(pto.end_date).startOf("day");
		const isCurrentlyOOO = pto.status === "approved" && (today.isAfter(startDate) || today.isSame(startDate)) && (today.isBefore(endDate) || today.isSame(endDate));

		// Apply date range filter - check if PTO request overlaps with the date range
		const tableStartDate = dayjs(tableDateRange.start_date).startOf("day");
		const tableEndDate = dayjs(tableDateRange.end_date).startOf("day");
		// PTO overlaps with date range if: startDate <= tableEndDate AND endDate >= tableStartDate
		const isInDateRange = (startDate.isBefore(tableEndDate) || startDate.isSame(tableEndDate)) && 
		                       (endDate.isAfter(tableStartDate) || endDate.isSame(tableStartDate));

		if (!isInDateRange) {
			return false;
		}

		// Apply status filter
		if (tableFilter === "current-ooo") {
			return isCurrentlyOOO;
		} else if (tableFilter === "approved") {
			return pto.status === "approved";
		} else if (tableFilter === "pending") {
			return pto.status === "pending";
		}
		return true; // "all"
	});

	const ptoColumns: ColumnDef<PTORequest>[] = [
		{
			accessorKey: "username",
			header: "User",
			size: 150,
			cell: ({ row }) => (
				<div className="font-semibold">{row.original.username || `User #${row.original.user_id}`}</div>
			),
		},
		{
			accessorKey: "start_date",
			header: "Start Date",
			size: 120,
			cell: ({ row }) => (
				<div>
					<div className="font-medium">{dayjs(row.original.start_date).format("MMM DD, YYYY")}</div>
					<div className="text-xs text-muted-foreground">{dayjs(row.original.start_date).format("dddd")}</div>
				</div>
			),
		},
		{
			accessorKey: "end_date",
			header: "End Date",
			size: 120,
			cell: ({ row }) => (
				<div>
					<div className="font-medium">{dayjs(row.original.end_date).format("MMM DD, YYYY")}</div>
					<div className="text-xs text-muted-foreground">{dayjs(row.original.end_date).format("dddd")}</div>
				</div>
			),
		},
		{
			accessorKey: "total_days",
			header: "Days",
			size: 80,
			cell: ({ row }) => (
				<Badge variant="outline" className="font-semibold">
					{row.original.total_days} {row.original.total_days === 1 ? "day" : "days"}
				</Badge>
			),
		},
		{
			accessorKey: "request_type",
			header: "Type",
			size: 100,
			cell: ({ row }) => {
				const type = row.original.request_type;
				const colors: Record<string, string> = {
					pto: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
					sick: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
					personal: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
					holiday: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
				};
				return (
					<Badge className={colors[type] || ""}>
						{type.toUpperCase()}
					</Badge>
				);
			},
		},
		{
			accessorKey: "status",
			header: "Status",
			size: 120,
			cell: ({ row }) => {
				const status = row.original.status;
				const variant =
					status === "approved"
						? "default"
						: status === "pending"
							? "secondary"
							: "destructive";
				return <Badge variant={variant}>{status.toUpperCase()}</Badge>;
			},
		},
		{
			accessorKey: "reason",
			header: "Reason",
			size: 200,
			cell: ({ row }) => (
				<div className="text-sm text-muted-foreground truncate max-w-[200px]">
					{row.original.reason || "-"}
				</div>
			),
		},
		{
			accessorKey: "actions",
			header: "Actions",
			size: 150,
			cell: ({ row }) => {
				const pto = row.original;
				if (!isAdmin) return null;
				
				if (pto.status === "pending") {
					return (
						<div className="flex gap-2">
							<Button
								size="sm"
								variant="default"
								onClick={() => handleApprovePTO(pto.id)}
								className="h-7 text-xs"
							>
								<Icon icon="mdi:check" size={14} className="mr-1" />
								Approve
							</Button>
							<Button
								size="sm"
								variant="destructive"
								onClick={() => handleRejectPTO(pto.id)}
								className="h-7 text-xs"
							>
								<Icon icon="mdi:close" size={14} className="mr-1" />
								Reject
							</Button>
						</div>
					);
				}
				return null;
			},
		}
	];

	return (
		<div className="flex flex-col gap-6">
			{/* Header */}
			<div className="flex flex-col gap-2">
				<Title as="h2" className="text-2xl">
					Calendar & PTO
				</Title>
				<p className="text-muted-foreground">
					Manage team calendar, PTO requests, and holidays
				</p>
			</div>

			{/* PTO Stats */}
			<Card>
				<CardHeader>
					<div className="flex flex-col gap-4">
						<CardTitle>PTO Statistics</CardTitle>
						<div className="flex flex-col lg:flex-row items-start lg:items-center gap-4">
							<div className="flex items-center gap-2 flex-wrap">
								<Label className="text-sm whitespace-nowrap">Period:</Label>
								<Input
									type="date"
									value={statsDateRange.start_date}
									onChange={(e) =>
										setStatsDateRange({ ...statsDateRange, start_date: e.target.value })
									}
									className="w-[140px]"
								/>
								<span className="text-muted-foreground">to</span>
								<Input
									type="date"
									value={statsDateRange.end_date}
									onChange={(e) =>
										setStatsDateRange({ ...statsDateRange, end_date: e.target.value })
									}
									className="w-[140px]"
								/>
							</div>
							<div className="flex gap-1 flex-wrap">
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setStatsDateRange({
											start_date: dayjs().startOf("week").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("week").format("YYYY-MM-DD"),
										})
									}
								>
									This Week
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setStatsDateRange({
											start_date: dayjs().startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									This Month
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setStatsDateRange({
											start_date: dayjs().subtract(1, "month").startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().subtract(1, "month").endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									Last Month
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setStatsDateRange({
											start_date: dayjs().startOf("year").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("year").format("YYYY-MM-DD"),
										})
									}
								>
									This Year
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setStatsDateRange({
											start_date: dayjs().subtract(3, "month").startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									Last 3 Months
								</Button>
							</div>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					{ptoStats && ptoStats.users && ptoStats.users.length > 0 ? (
						<>
							{/* Summary Totals */}
							<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
								<div className="p-4 border rounded-lg bg-blue-50 dark:bg-blue-950/20">
									<div className="text-sm text-muted-foreground mb-1">Total PTO Days</div>
									<div className="text-2xl font-bold">
										{ptoStats.users.reduce((sum: number, user: any) => sum + (user.total_pto_days || 0), 0)}
									</div>
								</div>
								<div className="p-4 border rounded-lg bg-yellow-50 dark:bg-yellow-950/20">
									<div className="text-sm text-muted-foreground mb-1">Pending Requests</div>
									<div className="text-2xl font-bold">
										{ptoStats.users.reduce((sum: number, user: any) => sum + (user.pending_requests || 0), 0)}
									</div>
								</div>
								<div className="p-4 border rounded-lg bg-green-50 dark:bg-green-950/20">
									<div className="text-sm text-muted-foreground mb-1">Approved Requests</div>
									<div className="text-2xl font-bold">
										{ptoStats.users.reduce((sum: number, user: any) => sum + (user.approved_requests || 0), 0)}
									</div>
								</div>
								<div className="p-4 border rounded-lg bg-red-50 dark:bg-red-950/20">
									<div className="text-sm text-muted-foreground mb-1">Rejected Requests</div>
									<div className="text-2xl font-bold">
										{ptoStats.users.reduce((sum: number, user: any) => sum + (user.rejected_requests || 0), 0)}
									</div>
								</div>
							</div>

							{/* Period Info */}
							<div className="mb-4 text-sm text-muted-foreground">
								Showing statistics from{" "}
								<span className="font-medium">
									{dayjs(statsDateRange.start_date).format("MMM DD, YYYY")}
								</span>{" "}
								to{" "}
								<span className="font-medium">
									{dayjs(statsDateRange.end_date).format("MMM DD, YYYY")}
								</span>
							</div>

							{/* User Stats Grid */}
							<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
								{ptoStats.users.map((user: any) => (
									<div key={user.user_id} className="flex flex-col gap-3 p-4 border rounded-lg hover:shadow-md transition-shadow">
										<div className="flex items-center justify-between">
											<div className="font-semibold text-lg">{user.username}</div>
											<Badge variant="outline" className="text-xs">
												{user.approved_requests || 0} approved
											</Badge>
										</div>
										<div className="grid grid-cols-2 gap-2 text-sm">
											<div className="flex flex-col">
												<span className="text-muted-foreground">Total PTO Days</span>
												<span className="font-semibold text-lg text-blue-600 dark:text-blue-400">
													{user.total_pto_days || 0}
												</span>
											</div>
											<div className="flex flex-col">
												<span className="text-muted-foreground">Pending</span>
												<span className="font-semibold text-lg text-yellow-600 dark:text-yellow-400">
													{user.pending_requests || 0}
												</span>
											</div>
											<div className="flex flex-col">
												<span className="text-muted-foreground">Approved</span>
												<span className="font-semibold text-lg text-green-600 dark:text-green-400">
													{user.approved_requests || 0}
												</span>
											</div>
											<div className="flex flex-col">
												<span className="text-muted-foreground">Rejected</span>
												<span className="font-semibold text-lg text-red-600 dark:text-red-400">
													{user.rejected_requests || 0}
												</span>
											</div>
										</div>
									</div>
								))}
							</div>
						</>
					) : (
						<div className="text-center py-8 text-muted-foreground">
							<Icon icon="mdi:chart-line" size={48} className="mx-auto mb-2 opacity-50" />
							<p>No PTO statistics available for the selected period</p>
						</div>
					)}
				</CardContent>
			</Card>

			{/* Calendar */}
			<Card className="h-full w-full">
				<CardContent className="h-full w-full pt-6">
					<div className="flex justify-between items-center mb-4">
						<div className="flex gap-2">
							<Select value={selectedCountry} onValueChange={setSelectedCountry}>
								<SelectTrigger className="w-[180px]">
									<SelectValue placeholder="Select country" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="BOTH">All Countries</SelectItem>
									<SelectItem value="US">US Holidays</SelectItem>
									<SelectItem value="PH">PH Holidays</SelectItem>
								</SelectContent>
							</Select>
							{isAdmin && (
								<Button onClick={() => setOpenHolidayForm(true)} variant="outline">
									<Icon icon="mdi:calendar-plus" size={20} className="mr-2" />
									Add Holiday
								</Button>
							)}
						</div>
					</div>
					<StyledCalendar $themeMode={themeMode}>
						<CalendarHeader
							now={date}
							view={view}
							onMove={handleMove}
							onCreate={() => {
								setOpenPTOForm(true);
								setEditingPTO(null);
								setPTOFormData({
									user_id: userId || 0,
									start_date: dayjs().format("YYYY-MM-DD"),
									end_date: dayjs().format("YYYY-MM-DD"),
									request_type: "pto",
									reason: "",
									notes: "",
								});
							}}
							onViewTypeChange={handleViewTypeChange}
						/>
						<FullCalendar
							ref={fullCalendarRef}
							plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin, listPlugin]}
							initialDate={dayjs().toDate()}
							initialView={xsBreakPoint ? "listWeek" : view}
							events={events}
							eventContent={CalendarEvent}
							editable={true}
							selectable
							selectMirror
							dayMaxEvents
							headerToolbar={false}
							select={handleDateSelect}
							eventClick={handleEventClick}
							eventDrop={handleEventDrop}
							eventResize={handleEventResize}
							datesSet={(arg) => {
								// Use the calendar's current date instead of arg.start
								// arg.start is the start of the visible range, which can be wrong
								// (e.g., in month view it might be a few days before the 1st)
								const calendarApi = arg.view.calendar;
								setDate(calendarApi.getDate());
							}}
						/>
					</StyledCalendar>
				</CardContent>
			</Card>

			{/* PTO Requests Table */}
			<Card>
				<CardHeader>
					<div className="flex flex-col gap-4">
						<div className="flex items-center justify-between">
							<CardTitle>
								{tableFilter === "current-ooo" 
									? "Currently Out of Office" 
									: tableFilter === "approved" 
										? "Approved PTO Requests" 
										: tableFilter === "pending"
											? "Pending Approval"
											: "All PTO Requests"}
							</CardTitle>
							<div className="flex gap-2">
								<Button
									variant="outline"
									size="sm"
									onClick={async () => {
										await Promise.all([
											loadTablePTORequests(true), // Merge to keep calendar data
											loadCalendarEvents(),
											loadPTOStats(),
										]);
										toast.success("Table refreshed");
									}}
									title="Refresh table data"
								>
									<Icon icon="mdi:refresh" size={16} className="mr-1" />
									Refresh
								</Button>
								<Button
									variant={tableFilter === "current-ooo" ? "default" : "outline"}
									size="sm"
									onClick={() => setTableFilter("current-ooo")}
								>
									<Icon icon="mdi:account-off" size={16} className="mr-1" />
									Current OOO
								</Button>
								{isAdmin && (
									<Button
										variant={tableFilter === "pending" ? "default" : "outline"}
										size="sm"
										onClick={() => setTableFilter("pending")}
									>
										<Icon icon="mdi:clock-outline" size={16} className="mr-1" />
										Pending
									</Button>
								)}
								<Button
									variant={tableFilter === "approved" ? "default" : "outline"}
									size="sm"
									onClick={() => setTableFilter("approved")}
								>
									<Icon icon="mdi:check-circle" size={16} className="mr-1" />
									Approved
								</Button>
								<Button
									variant={tableFilter === "all" ? "default" : "outline"}
									size="sm"
									onClick={() => setTableFilter("all")}
								>
									<Icon icon="mdi:format-list-bulleted" size={16} className="mr-1" />
									All
								</Button>
							</div>
						</div>
						<div className="flex flex-col lg:flex-row items-start lg:items-center gap-4">
							<div className="flex items-center gap-2 flex-wrap">
								<Label className="text-sm whitespace-nowrap">Date Range:</Label>
								<Input
									type="date"
									value={tableDateRange.start_date}
									onChange={(e) =>
										setTableDateRange({ ...tableDateRange, start_date: e.target.value })
									}
									className="w-[140px]"
								/>
								<span className="text-muted-foreground">to</span>
								<Input
									type="date"
									value={tableDateRange.end_date}
									onChange={(e) =>
										setTableDateRange({ ...tableDateRange, end_date: e.target.value })
									}
									className="w-[140px]"
								/>
							</div>
							<div className="flex gap-1 flex-wrap">
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setTableDateRange({
											start_date: dayjs().startOf("week").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("week").format("YYYY-MM-DD"),
										})
									}
								>
									This Week
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setTableDateRange({
											start_date: dayjs().startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									This Month
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setTableDateRange({
											start_date: dayjs().subtract(1, "month").startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().subtract(1, "month").endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									Last Month
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setTableDateRange({
											start_date: dayjs().startOf("year").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("year").format("YYYY-MM-DD"),
										})
									}
								>
									This Year
								</Button>
								<Button
									variant="outline"
									size="sm"
									onClick={() =>
										setTableDateRange({
											start_date: dayjs().subtract(3, "month").startOf("month").format("YYYY-MM-DD"),
											end_date: dayjs().endOf("month").format("YYYY-MM-DD"),
										})
									}
								>
									Last 3 Months
								</Button>
							</div>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					{filteredPTORequests.length === 0 ? (
						<div className="text-center py-8 text-muted-foreground">
							{tableFilter === "current-ooo" ? (
								<>
									<Icon icon="mdi:account-check" size={48} className="mx-auto mb-2 opacity-50" />
									<p>No one is currently out of office</p>
								</>
							) : (
								<p>No PTO requests found</p>
							)}
						</div>
					) : (
						<>
							<div className="mb-4 text-sm text-muted-foreground">
								Showing {filteredPTORequests.length} {filteredPTORequests.length === 1 ? "request" : "requests"}
							</div>
							<DataTable columns={ptoColumns} data={filteredPTORequests} />
						</>
					)}
				</CardContent>
			</Card>

			{/* PTO Form Dialog */}
			<Dialog open={openPTOForm} onOpenChange={setOpenPTOForm}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle>
							{editingPTO ? "Edit PTO Request" : "New PTO Request"}
						</DialogTitle>
						<DialogDescription>
							{editingPTO
								? "Update your PTO request details"
								: "Submit a new PTO request"}
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4">
						{isAdmin && (
							<div>
								<Label>User</Label>
								<Select
									value={ptoFormData.user_id?.toString() || ""}
									onValueChange={(value) =>
										setPTOFormData({ ...ptoFormData, user_id: parseInt(value) })
									}
									disabled={!!editingPTO && !isAdmin}
								>
									<SelectTrigger>
										<SelectValue placeholder="Select user" />
									</SelectTrigger>
									<SelectContent>
										{allUsers.map((user) => (
											<SelectItem key={user.id} value={user.id.toString()}>
												{user.username} ({user.email})
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
						)}
						<div className="grid grid-cols-2 gap-4">
							<div>
								<Label>Start Date</Label>
								<Input
									type="date"
									value={ptoFormData.start_date}
									onChange={(e) =>
										setPTOFormData({ ...ptoFormData, start_date: e.target.value })
									}
								/>
							</div>
							<div>
								<Label>End Date</Label>
								<Input
									type="date"
									value={ptoFormData.end_date}
									onChange={(e) =>
										setPTOFormData({ ...ptoFormData, end_date: e.target.value })
									}
								/>
							</div>
						</div>
						<div>
							<Label>Request Type</Label>
							<Select
								value={ptoFormData.request_type}
								onValueChange={(value: any) =>
									setPTOFormData({ ...ptoFormData, request_type: value })
								}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="pto">PTO</SelectItem>
									<SelectItem value="sick">Sick Leave</SelectItem>
									<SelectItem value="personal">Personal</SelectItem>
									<SelectItem value="holiday">Holiday</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div>
							<Label>Reason</Label>
							<Textarea
								value={ptoFormData.reason}
								onChange={(e) =>
									setPTOFormData({ ...ptoFormData, reason: e.target.value })
								}
								placeholder="Enter reason for PTO request"
							/>
						</div>
						<div>
							<Label>Notes</Label>
							<Textarea
								value={ptoFormData.notes}
								onChange={(e) =>
									setPTOFormData({ ...ptoFormData, notes: e.target.value })
								}
								placeholder="Additional notes (optional)"
							/>
						</div>
						{isAdmin && editingPTO && (
							<div>
								<Label>Status</Label>
								<Select
									value={editingPTO.status}
									onValueChange={(value: any) => {
										// Update the editing PTO status
										setEditingPTO({ ...editingPTO, status: value });
									}}
								>
									<SelectTrigger>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="pending">Pending</SelectItem>
										<SelectItem value="approved">Approved</SelectItem>
										<SelectItem value="rejected">Rejected</SelectItem>
										<SelectItem value="cancelled">Cancelled</SelectItem>
									</SelectContent>
								</Select>
							</div>
						)}
					</div>
					<DialogFooter>
						{editingPTO && (isAdmin || editingPTO.user_id === userId) && (
							<Button
								variant="destructive"
								onClick={() => handleDeletePTO(editingPTO.id)}
							>
								Delete
							</Button>
						)}
						<Button variant="outline" onClick={() => setOpenPTOForm(false)}>
							Cancel
						</Button>
						<Button onClick={handlePTOSubmit}>
							{editingPTO ? "Update" : "Request"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Holiday Form Dialog */}
			<Dialog open={openHolidayForm} onOpenChange={setOpenHolidayForm}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>
							{editingHoliday ? "Edit Holiday" : "New Holiday"}
						</DialogTitle>
						<DialogDescription>
							{editingHoliday
								? "Update holiday details"
								: "Add a new company holiday"}
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4">
						<div>
							<Label>Holiday Name</Label>
							<Input
								value={holidayFormData.name}
								onChange={(e) =>
									setHolidayFormData({ ...holidayFormData, name: e.target.value })
								}
								placeholder="e.g., New Year's Day"
							/>
						</div>
						<div>
							<Label>Date</Label>
							<Input
								type="date"
								value={holidayFormData.date}
								onChange={(e) =>
									setHolidayFormData({ ...holidayFormData, date: e.target.value })
								}
							/>
						</div>
						<div>
							<Label>Country</Label>
							<Select
								value={holidayFormData.country}
								onValueChange={(value) =>
									setHolidayFormData({ ...holidayFormData, country: value })
								}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="BOTH">Both (US & PH)</SelectItem>
									<SelectItem value="US">US Only</SelectItem>
									<SelectItem value="PH">PH Only</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div className="flex items-center space-x-2">
							<input
								type="checkbox"
								id="recurring"
								checked={holidayFormData.is_recurring}
								onChange={(e) =>
									setHolidayFormData({
										...holidayFormData,
										is_recurring: e.target.checked,
									})
								}
							/>
							<Label htmlFor="recurring">Recurring (Yearly)</Label>
						</div>
						<div>
							<Label>Description</Label>
							<Textarea
								value={holidayFormData.description}
								onChange={(e) =>
									setHolidayFormData({
										...holidayFormData,
										description: e.target.value,
									})
								}
								placeholder="Holiday description (optional)"
							/>
						</div>
					</div>
					<DialogFooter>
						{editingHoliday && isAdmin && (
							<Button
								variant="destructive"
								onClick={() => handleDeleteHoliday(editingHoliday.id)}
							>
								Delete
							</Button>
						)}
						<Button variant="outline" onClick={() => setOpenHolidayForm(false)}>
							Cancel
						</Button>
						{isAdmin && (
							<Button onClick={handleHolidaySubmit}>Save</Button>
						)}
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

