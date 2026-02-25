import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { Input } from "@/ui/input";
import { Label } from "@/ui/label";
import { useState } from "react";
import { toast } from "sonner";
import userService from "@/api/services/userService";
import Icon from "@/components/icon/icon";
import { useUserInfo, useUserActions } from "@/store/userStore";

export default function Profile() {
	const userInfo = useUserInfo();
	const { setUserInfo } = useUserActions();
	const [loading, setLoading] = useState(false);
	const [formData, setFormData] = useState({
		username: userInfo.username || "",
		password: "",
		confirmPassword: "",
	});

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setLoading(true);

		// Validate password if provided
		if (formData.password) {
			if (formData.password.length < 6) {
				toast.error("Password must be at least 6 characters long");
				setLoading(false);
				return;
			}
			if (formData.password !== formData.confirmPassword) {
				toast.error("Passwords do not match");
				setLoading(false);
				return;
			}
		}

		// Validate username
		if (!formData.username || formData.username.trim().length < 3) {
			toast.error("Full name must be at least 3 characters long");
			setLoading(false);
			return;
		}

		try {
			const updateData: { username?: string; password?: string } = {};
			
			// Only include fields that have changed
			if (formData.username !== userInfo.username) {
				updateData.username = formData.username.trim();
			}
			
			if (formData.password) {
				updateData.password = formData.password;
			}

			// Don't send request if nothing changed
			if (Object.keys(updateData).length === 0) {
				toast.info("No changes to save");
				setLoading(false);
				return;
			}

			const response = await userService.updateProfile(updateData);
			
			// Update user info in store
			setUserInfo(response);
			
			toast.success("Profile updated successfully");
			
			// Clear password fields
			setFormData({
				...formData,
				password: "",
				confirmPassword: "",
			});
		} catch (error: any) {
			console.error("Failed to update profile:", error);
			const errorMessage = error?.response?.data?.detail || error?.message || "Failed to update profile";
			toast.error(errorMessage);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex flex-col gap-4 p-4">
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Icon icon="mdi:account-edit" size={24} />
						<span>Profile</span>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleSubmit} className="space-y-6">
						<div className="grid gap-4">
							<div className="grid gap-2">
								<Label htmlFor="email">Email</Label>
								<Input
									id="email"
									type="email"
									value={userInfo.email || ""}
									disabled
									className="bg-muted"
								/>
								<p className="text-sm text-muted-foreground">
									Email cannot be changed. Contact administrator if you need to update your email.
								</p>
							</div>

							<div className="grid gap-2">
								<Label htmlFor="username">Full Name *</Label>
								<Input
									id="username"
									value={formData.username}
									onChange={(e) => setFormData({ ...formData, username: e.target.value })}
									placeholder="Enter your full name"
									required
									minLength={3}
								/>
							</div>

							<div className="grid gap-2">
								<Label htmlFor="password">New Password</Label>
								<Input
									id="password"
									type="password"
									value={formData.password}
									onChange={(e) => setFormData({ ...formData, password: e.target.value })}
									placeholder="Leave blank to keep current password"
									minLength={6}
								/>
								<p className="text-sm text-muted-foreground">
									Leave blank if you don't want to change your password.
								</p>
							</div>

							{formData.password && (
								<div className="grid gap-2">
									<Label htmlFor="confirmPassword">Confirm New Password</Label>
									<Input
										id="confirmPassword"
										type="password"
										value={formData.confirmPassword}
										onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
										placeholder="Confirm new password"
										minLength={6}
									/>
								</div>
							)}
						</div>

						<div className="flex justify-end gap-2">
							<Button
								type="button"
								variant="outline"
								onClick={() => {
									setFormData({
										username: userInfo.username || "",
										password: "",
										confirmPassword: "",
									});
								}}
								disabled={loading}
							>
								Reset
							</Button>
							<Button type="submit" disabled={loading}>
								{loading ? (
									<>
										<Icon icon="mdi:loading" className="mr-2 animate-spin" size={18} />
										Saving...
									</>
								) : (
									<>
										<Icon icon="mdi:content-save" className="mr-2" size={18} />
										Save Changes
									</>
								)}
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}

