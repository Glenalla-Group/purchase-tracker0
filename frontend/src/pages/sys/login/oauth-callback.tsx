import { useSignIn } from "@/store/userStore";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

export default function OAuthCallback() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const signIn = useSignIn();

	useEffect(() => {
		const accessToken = searchParams.get("accessToken");
		const refreshToken = searchParams.get("refreshToken");

		if (accessToken && refreshToken) {
			// Manually set tokens and redirect
			try {
				// We need to fetch user info with the token
				// For now, we'll redirect to home and let the app fetch user info
				localStorage.setItem("accessToken", accessToken);
				localStorage.setItem("refreshToken", refreshToken);
				
				toast.success("Login successful!", {
					description: "Welcome back!",
					closeButton: true,
				});

				// Redirect to dashboard
				navigate("/workbench", { replace: true });
			} catch (error) {
				toast.error("Authentication failed", {
					description: "Please try again.",
					closeButton: true,
				});
				navigate("/auth/login", { replace: true });
			}
		} else {
			toast.error("Authentication failed", {
				description: "Missing authentication tokens.",
				closeButton: true,
			});
			navigate("/auth/login", { replace: true });
		}
	}, [searchParams, navigate, signIn]);

	return (
		<div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
			<div className="text-center">
				<Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
				<p className="mt-4 text-lg font-medium">Completing authentication...</p>
				<p className="mt-2 text-sm text-muted-foreground">Please wait while we sign you in.</p>
			</div>
		</div>
	);
}

