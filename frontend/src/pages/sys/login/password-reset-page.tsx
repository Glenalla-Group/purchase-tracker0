import userService from "@/api/services/userService";
import { Icon } from "@/components/icon";
import { Button } from "@/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/ui/form";
import { Input } from "@/ui/input";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

export default function PasswordResetPage() {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const [token, setToken] = useState<string | null>(null);
	const [resetSuccess, setResetSuccess] = useState(false);

	const form = useForm({
		defaultValues: {
			new_password: "",
			confirm_password: "",
		},
	});

	useEffect(() => {
		const tokenParam = searchParams.get("token");
		if (!tokenParam) {
			toast.error("Invalid reset link", {
				description: "The password reset link is invalid or has expired.",
			});
			navigate("/auth/login");
		} else {
			setToken(tokenParam);
		}
	}, [searchParams, navigate]);

	const resetPasswordMutation = useMutation({
		mutationFn: userService.resetPassword,
		onSuccess: () => {
			setResetSuccess(true);
			toast.success("Password reset successful!", {
				description: "You can now login with your new password.",
				closeButton: true,
			});
			// Redirect to login after 2 seconds
			setTimeout(() => {
				navigate("/auth/login");
			}, 2000);
		},
		onError: (error: any) => {
			toast.error("Password reset failed", {
				description: error.message || "The reset link may have expired. Please request a new one.",
				closeButton: true,
			});
		},
	});

	const onFinish = async (values: any) => {
		if (values.new_password !== values.confirm_password) {
			form.setError("confirm_password", {
				type: "manual",
				message: "Passwords do not match",
			});
			return;
		}

		if (!token) return;

		await resetPasswordMutation.mutateAsync({
			token,
			new_password: values.new_password,
		});
	};

	if (!token) {
		return null;
	}

	return (
		<div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
			<div className="w-full max-w-md">
				<div className="rounded-lg bg-white p-8 shadow-xl">
					<div className="mb-8 text-center">
						<Icon icon="local:ic-reset-password" size="100" className="mx-auto text-primary!" />
					</div>

					{resetSuccess ? (
						<div className="text-center">
							<div className="rounded-lg bg-green-50 p-6">
								<Icon icon="mdi:check-circle" size={64} className="mx-auto mb-4 text-green-600" />
								<h2 className="mb-2 text-2xl font-bold text-green-800">Password Reset Successful!</h2>
								<p className="text-sm text-green-700">
									Redirecting to login page...
								</p>
							</div>
						</div>
					) : (
						<>
							<div className="mb-6 text-center">
								<h1 className="text-2xl font-bold">Reset Your Password</h1>
								<p className="mt-2 text-sm text-muted-foreground">
									Enter your new password below
								</p>
							</div>

							<Form {...form}>
								<form onSubmit={form.handleSubmit(onFinish)} className="space-y-4">
									<FormField
										control={form.control}
										name="new_password"
										rules={{
											required: "Password is required",
											minLength: {
												value: 6,
												message: "Password must be at least 6 characters",
											},
										}}
										render={({ field }) => (
											<FormItem>
												<FormLabel>New Password</FormLabel>
												<FormControl>
													<Input type="password" placeholder="Enter new password" {...field} />
												</FormControl>
												<FormMessage />
											</FormItem>
										)}
									/>

									<FormField
										control={form.control}
										name="confirm_password"
										rules={{
											required: "Please confirm your password",
										}}
										render={({ field }) => (
											<FormItem>
												<FormLabel>Confirm Password</FormLabel>
												<FormControl>
													<Input type="password" placeholder="Confirm new password" {...field} />
												</FormControl>
												<FormMessage />
											</FormItem>
										)}
									/>

									<Button
										type="submit"
										className="w-full"
										disabled={resetPasswordMutation.isPending}
									>
										{resetPasswordMutation.isPending && <Loader2 className="mr-2 animate-spin" />}
										Reset Password
									</Button>

									<div className="text-center">
										<Button
											variant="link"
											onClick={() => navigate("/auth/login")}
											type="button"
										>
											Back to Login
										</Button>
									</div>
								</form>
							</Form>
						</>
					)}
				</div>
			</div>
		</div>
	);
}

