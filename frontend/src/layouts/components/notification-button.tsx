import { Icon } from "@/components/icon";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import emailManualReviewService from "@/api/services/emailManualReviewService";

export default function NotificationButton() {
	const { data } = useQuery({
		queryKey: ["email-manual-review-count"],
		queryFn: () => emailManualReviewService.getPendingCount(),
		refetchInterval: 60_000, // refetch every 60s
	});

	const count = data?.pending_count ?? 0;

	return (
		<Link to="/teams/notification">
			<Button variant="ghost" size="icon" className="rounded-full relative">
				<Icon icon="solar:bell-bing-bold-duotone" size={24} />
				{count > 0 && (
					<Badge
						variant="destructive"
						shape="circle"
						className="absolute -right-2 -top-2 min-w-5 h-5 flex items-center justify-center p-0 text-xs"
					>
						{count > 99 ? "99+" : count}
					</Badge>
				)}
			</Button>
		</Link>
	);
}
