import type { EventContentArg } from "@fullcalendar/core";
import { Icon } from "@/components/icon";

export default function CalendarEvent(eventInfo: EventContentArg) {
	const { timeText, event, backgroundColor } = eventInfo;
	const { extendedProps } = event;
	
	// Extract icon and text from title if it's a PTO event
	let displayContent = event.title;
	if (extendedProps?.type === "pto" && extendedProps?.statusIcon) {
		const statusIcon = extendedProps.statusIcon;
		const username = extendedProps.username || "User";
		const requestType = extendedProps.request_type?.toUpperCase() || "PTO";
		
		return (
			<div
				className="fc-event-main-wrapper"
				style={{
					color: backgroundColor,
				}}
			>
				<div className="fc-event-main-frame">
					{timeText && <div className="fc-event-time">{timeText}</div>}
					<div className="fc-event-title-container">
						<div className="fc-event-title fc-sticky flex items-center gap-1">
							<Icon icon={statusIcon} size={14} />
							<span>{username} - {requestType}</span>
						</div>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div
			className="fc-event-main-wrapper"
			style={{
				color: backgroundColor,
			}}
		>
			<div className="fc-event-main-frame">
				{timeText && <div className="fc-event-time">{timeText}</div>}
				<div className="fc-event-title-container">
					<div className="fc-event-title fc-sticky">{displayContent}</div>
				</div>
			</div>
		</div>
	);
}
