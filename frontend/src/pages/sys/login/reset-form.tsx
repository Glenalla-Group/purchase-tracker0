import userService from "@/api/services/userService";
import { Icon } from "@/components/icon";
import { Button } from "@/ui/button";
import { Form, FormControl, FormField, FormItem, FormMessage } from "@/ui/form";
import { Input } from "@/ui/input";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ReturnButton } from "./components/ReturnButton";
import { LoginStateEnum, useLoginStateContext } from "./providers/login-provider";

function ResetForm() {
	const { t } = useTranslation();
	const { loginState, backToLogin } = useLoginStateContext();
	const [emailSent, setEmailSent] = useState(false);

	const form = useForm({
		defaultValues: {
			email: "",
		},
	});

	const forgotPasswordMutation = useMutation({
		mutationFn: userService.forgotPassword,
		onSuccess: () => {
			setEmailSent(true);
			toast.success("Password reset email sent!", {
				description: "Please check your email for further instructions.",
				closeButton: true,
			});
		},
		onError: (error: any) => {
			toast.error("Failed to send reset email", {
				description: error.message || "Please try again later.",
				closeButton: true,
			});
		},
	});

	const onFinish = async (values: any) => {
		await forgotPasswordMutation.mutateAsync(values);
	};

	if (loginState !== LoginStateEnum.RESET_PASSWORD) return null;

	return (
		<>
			<div className="mb-8 text-center">
				<Icon icon="local:ic-reset-password" size="100" className="text-primary!" />
			</div>
			<Form {...form}>
				<form onSubmit={form.handleSubmit(onFinish)} className="space-y-4">
					<div className="flex flex-col items-center gap-2 text-center">
						<h1 className="text-2xl font-bold">{t("sys.login.forgetFormTitle")}</h1>
						<p className="text-balance text-sm text-muted-foreground">{t("sys.login.forgetFormSecondTitle")}</p>
					</div>

					{emailSent ? (
						<div className="rounded-lg bg-green-50 p-4 text-center">
							<Icon icon="mdi:email-check" size={48} className="mx-auto mb-2 text-green-600" />
							<p className="text-sm text-green-800">
								If an account exists with this email, a password reset link has been sent.
							</p>
							<p className="mt-2 text-xs text-green-700">
								Please check your inbox and spam folder.
							</p>
						</div>
					) : (
						<FormField
							control={form.control}
							name="email"
							rules={{ required: t("sys.login.emaildPlaceholder") }}
							render={({ field }) => (
								<FormItem>
									<FormControl>
										<Input type="email" placeholder={t("sys.login.email")} {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
					)}

					{!emailSent && (
						<Button type="submit" className="w-full" disabled={forgotPasswordMutation.isPending}>
							{forgotPasswordMutation.isPending && <Loader2 className="mr-2 animate-spin" />}
							{t("sys.login.sendEmailButton")}
						</Button>
					)}
					<ReturnButton onClick={backToLogin} />
				</form>
			</Form>
		</>
	);
}

export default ResetForm;
