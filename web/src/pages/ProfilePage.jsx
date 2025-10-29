import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { loadLanguageFromProfile, getUserLanguage } from "../utils/languageSync";
import LanguageSelector from "../components/LanguageSelector";
import ThemeToggle from "../components/ThemeToggle";
import Footer from "../components/Footer";

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "pl", name: "Polish" },
  { code: "ar", name: "Arabic" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
  { code: "pt", name: "Portuguese" },
  { code: "ru", name: "Russian" },
  { code: "zh", name: "Chinese" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" }
];

export default function ProfilePage({ token, onLogout }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("settings");
  const [profile, setProfile] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [billing, setBilling] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  // Form states
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    fetchProfileData();
    // Load language from profile on mount
    loadLanguageFromProfile(token);
  }, [token]);

  async function fetchProfileData() {
    setLoading(true);
    try {
      // Fetch profile
      const profileRes = await fetch("/api/profile", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (profileRes.ok) {
        const profileData = await profileRes.json();
        setProfile(profileData);
        setDisplayName(profileData.display_name);
        setIsAdmin(profileData.is_admin || false);
        // Language is now handled by unified system, no need to set state
      }

      // Fetch subscription
      const subRes = await fetch("/api/subscription", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (subRes.ok) {
        const subData = await subRes.json();
        setSubscription(subData);
      }

      // Fetch billing/usage
      const billingRes = await fetch("/api/billing/usage", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (billingRes.ok) {
        const billingData = await billingRes.json();
        setBilling(billingData);
      }

      // Fetch history
      const historyRes = await fetch("/api/user/history?limit=10", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setHistory(historyData);
      }
    } catch (e) {
      console.error("Failed to fetch profile data:", e);
      setError("Failed to load profile data");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdateProfile(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      const res = await fetch("/api/profile", {
        method: "PATCH",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          display_name: displayName
          // Language is handled by unified system via LanguageSelector
        })
      });

      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setMessage(t('profile.profileUpdated'));
      } else {
        setError(t('profile.updateFailed'));
      }
    } catch (e) {
      setError(t('profile.updateFailed'));
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    if (newPassword !== confirmPassword) {
      setError(t('profile.passwordsDoNotMatch'));
      return;
    }

    if (newPassword.length < 6) {
      setError(t('profile.passwordTooShort'));
      return;
    }

    try {
      const res = await fetch("/api/profile/password", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          current_password: profile?.has_password ? currentPassword : null,
          new_password: newPassword
        })
      });

      if (res.ok) {
        setMessage("Password changed successfully!");
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to change password");
      }
    } catch (e) {
      setError("Failed to change password");
    }
  }

  async function handleChangePlan(newPlan) {
    setMessage("");
    setError("");

    try {
      const res = await fetch("/api/subscription", {
        method: "PATCH",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ plan: newPlan })
      });

      if (res.ok) {
        const data = await res.json();
        setSubscription(data);
        setMessage(`Plan changed to ${newPlan.toUpperCase()} successfully!`);
        // Refresh billing data
        fetchProfileData();
      } else {
        setError("Failed to change plan");
      }
    } catch (e) {
      setError("Failed to change plan");
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg p-4 flex flex-col">
        <div className="text-fg text-xl text-center mt-24">{t('common.loading')}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg p-4 flex flex-col">
      <div className="flex-1">
        <div className="flex justify-between items-start mb-6 flex-wrap gap-4">
          <h1 className="text-fg text-[clamp(1.5rem,5vw,2rem)] font-bold m-0">
            {t('profile.title')}
          </h1>
          <div className="flex gap-2 flex-wrap">
            {isAdmin && (
              <button
                onClick={() => navigate("/admin")}
                className="px-5 py-2.5 bg-amber-500 text-white border-none rounded-lg cursor-pointer text-sm font-medium
                           hover:bg-amber-600 transition-colors"
              >
                🛠️ Admin
              </button>
            )}
            <button
              onClick={() => navigate("/rooms")}
              className="px-5 py-2.5 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-medium
                         hover:bg-accent-dark transition-colors"
            >
              ← {t('profile.backToRooms')}
            </button>
            <button
              onClick={onLogout}
              className="px-5 py-2.5 bg-red-500 text-white border-none rounded-lg cursor-pointer text-sm font-medium
                         hover:bg-red-600 transition-colors"
            >
              {t('profile.signOut')}
            </button>
          </div>
        </div>

        {message && (
          <div className="bg-green-500 text-white px-5 py-3 rounded-lg mb-5">{message}</div>
        )}
        {error && (
          <div className="bg-red-500 text-white px-5 py-3 rounded-lg mb-5">{error}</div>
        )}

        <div className="flex gap-2 mb-4 flex-wrap overflow-x-auto">
          {['settings', 'account', 'subscription', 'billing', 'history'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 border-none rounded-lg cursor-pointer text-sm font-medium transition-all whitespace-nowrap flex-[0_0_auto]
                         ${activeTab === tab
                           ? 'bg-card text-accent font-semibold'
                           : 'bg-white/20 text-fg hover:bg-white/30'}`}
            >
              {t(tab === 'settings' ? 'profileTabs.settings' : `common.${tab}`)}
            </button>
          ))}
        </div>

        <div className="bg-card rounded-xl p-[clamp(1rem,4vw,2rem)] min-h-[400px]">
          {activeTab === "settings" && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-bold mb-5 text-fg">{t('profileTabs.settings')}</h2>
              <form onSubmit={handleUpdateProfile} className="flex flex-col gap-5">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-muted">{t('auth.displayName')}</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="px-3 py-3 border border-border rounded-lg text-sm outline-none transition-colors
                               bg-card text-fg focus:border-accent"
                    placeholder="Your name"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-muted">{t('profile.preferredLanguage')}</label>
                  <div className="mt-2">
                    <LanguageSelector token={token} />
                  </div>
                  <div className="text-xs text-muted">
                    {t('common.language')} controls both UI and translation language
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-muted">Theme</label>
                  <div className="mt-2">
                    <ThemeToggle />
                  </div>
                  <div className="text-xs text-muted">
                    Toggle between light and dark mode
                  </div>
                </div>

                <button
                  type="submit"
                  className="px-6 py-3 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                             self-start hover:bg-accent-dark transition-colors"
                >
                  {t('profile.saveChanges')}
                </button>
              </form>
            </div>
          )}

          {activeTab === "account" && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-bold mb-5 text-fg">{t('common.account')}</h2>

              <div className="mb-4 p-3 bg-bg-secondary rounded-lg">
                <div className="text-xs font-semibold text-muted mb-1">{t('auth.email')}</div>
                <div className="text-sm text-fg">{profile?.email}</div>
              </div>

              <div className="mb-4 p-3 bg-bg-secondary rounded-lg">
                <div className="text-xs font-semibold text-muted mb-1">{t('profile.accountType')}</div>
                <div className="text-sm text-fg">
                  {profile?.google_id ? t('profile.googleOAuth') : t('profile.emailPassword')}
                </div>
              </div>

              <div className="mb-4 p-3 bg-bg-secondary rounded-lg">
                <div className="text-xs font-semibold text-muted mb-1">{t('profile.memberSince')}</div>
                <div className="text-sm text-fg">
                  {new Date(profile?.created_at).toLocaleDateString()}
                </div>
              </div>

              <div className="mb-4 p-3 bg-bg-secondary rounded-lg">
                <div className="text-xs font-semibold text-muted mb-1">Created by</div>
                <div className="text-sm text-fg">
                  <a
                    href="https://pawelgawliczek.cloud/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:text-accent-dark no-underline"
                  >
                    Pawel Gawliczek @ 2025
                  </a>
                </div>
              </div>

              <div className="h-px bg-border my-8"></div>

              <h3 className="text-lg font-semibold mt-8 mb-4 text-fg">{t('profile.changePassword')}</h3>
              <form onSubmit={handleChangePassword} className="flex flex-col gap-5">
                {profile?.has_password && (
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-semibold text-muted">{t('profile.currentPassword')}</label>
                    <input
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="px-3 py-3 border border-border rounded-lg text-sm outline-none transition-colors
                                 bg-card text-fg focus:border-accent"
                      placeholder="Enter current password"
                    />
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-muted">{t('profile.newPassword')}</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="px-3 py-3 border border-border rounded-lg text-sm outline-none transition-colors
                               bg-card text-fg focus:border-accent"
                    placeholder="Enter new password"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold text-muted">{t('profile.confirmNewPassword')}</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="px-3 py-3 border border-border rounded-lg text-sm outline-none transition-colors
                               bg-card text-fg focus:border-accent"
                    placeholder="Confirm new password"
                  />
                </div>

                <button
                  type="submit"
                  className="px-6 py-3 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                             self-start hover:bg-accent-dark transition-colors"
                >
                  {t('profile.changePassword')}
                </button>
              </form>
            </div>
          )}

          {activeTab === "subscription" && subscription && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-bold mb-5 text-fg">Subscription</h2>

              <div className="bg-bg-secondary p-5 rounded-lg mb-8 flex justify-between items-center flex-wrap gap-2.5">
                <div className="text-lg text-fg">
                  Current Plan: <strong>{subscription.plan.toUpperCase()}</strong>
                </div>
                <div className="text-sm text-muted">
                  Status: <span className={subscription.status === "active" ? "text-green-500" : "text-red-500"}>
                    {subscription.status}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-5">
                <div className={`border-2 rounded-xl p-6 transition-all ${
                  subscription.plan === "free"
                    ? "border-accent bg-purple-50 dark:bg-purple-950/20"
                    : "border-border bg-card"
                }`}>
                  <h3 className="text-xl font-bold mb-2.5 text-fg">Free</h3>
                  <div className="text-2xl font-bold text-accent mb-5">$0/month</div>
                  <ul className="list-none p-0 m-0 mb-5 text-sm text-muted space-y-1">
                    <li>1 hour per month</li>
                    <li>Basic translation</li>
                    <li>Community support</li>
                  </ul>
                  {subscription.plan !== "free" && (
                    <button
                      onClick={() => handleChangePlan("free")}
                      className="w-full px-2.5 py-2.5 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                                 hover:bg-accent-dark transition-colors"
                    >
                      Downgrade
                    </button>
                  )}
                </div>

                <div className={`border-2 rounded-xl p-6 transition-all ${
                  subscription.plan === "plus"
                    ? "border-accent bg-purple-50 dark:bg-purple-950/20"
                    : "border-border bg-card"
                }`}>
                  <h3 className="text-xl font-bold mb-2.5 text-fg">Plus</h3>
                  <div className="text-2xl font-bold text-accent mb-5">$9.99/month</div>
                  <ul className="list-none p-0 m-0 mb-5 text-sm text-muted space-y-1">
                    <li>Unlimited translation</li>
                    <li>Priority support</li>
                    <li>Advanced features</li>
                  </ul>
                  {subscription.plan !== "plus" && (
                    <button
                      onClick={() => handleChangePlan("plus")}
                      className="w-full px-2.5 py-2.5 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                                 hover:bg-accent-dark transition-colors"
                    >
                      {subscription.plan === "free" ? "Upgrade" : "Switch"}
                    </button>
                  )}
                </div>

                <div className={`border-2 rounded-xl p-6 transition-all ${
                  subscription.plan === "pro"
                    ? "border-accent bg-purple-50 dark:bg-purple-950/20"
                    : "border-border bg-card"
                }`}>
                  <h3 className="text-xl font-bold mb-2.5 text-fg">Pro</h3>
                  <div className="text-2xl font-bold text-accent mb-5">$29.99/month</div>
                  <ul className="list-none p-0 m-0 mb-5 text-sm text-muted space-y-1">
                    <li>Unlimited translation</li>
                    <li>24/7 support</li>
                    <li>Advanced features</li>
                    <li>API access</li>
                  </ul>
                  {subscription.plan !== "pro" && (
                    <button
                      onClick={() => handleChangePlan("pro")}
                      className="w-full px-2.5 py-2.5 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                                 hover:bg-accent-dark transition-colors"
                    >
                      Upgrade
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "billing" && billing && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-bold mb-5 text-fg">Billing & Usage</h2>

              <div className="bg-bg-secondary p-4 rounded-lg mb-5 text-center">
                <div className="text-fg font-semibold">
                  Current Billing Period
                </div>
                <div className="text-sm text-muted mt-2">
                  {new Date(billing.billing_period_start).toLocaleDateString()} - {new Date(billing.billing_period_end).toLocaleDateString()}
                </div>
              </div>

              <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-5 mb-8">
                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">STT Minutes Used</div>
                  <div className="text-2xl font-bold text-fg">
                    {billing.total_stt_minutes.toFixed(2)}
                    {billing.quota_minutes && ` / ${billing.quota_minutes}`}
                  </div>
                  {billing.quota_remaining_minutes !== null && (
                    <div className="text-xs text-muted mt-1">
                      {billing.quota_remaining_minutes.toFixed(2)} minutes remaining
                    </div>
                  )}
                </div>

                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">STT Cost</div>
                  <div className="text-2xl font-bold text-fg">${billing.total_stt_cost_usd.toFixed(4)}</div>
                </div>

                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">Translation Cost</div>
                  <div className="text-2xl font-bold text-fg">${billing.total_mt_cost_usd.toFixed(4)}</div>
                </div>

                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">Total Cost</div>
                  <div className="text-2xl font-bold text-fg">${billing.total_cost_usd.toFixed(4)}</div>
                </div>
              </div>

              {billing.rooms && billing.rooms.length > 0 && (
                <>
                  <h3 className="text-lg font-semibold mt-8 mb-4 text-fg">Room Usage</h3>
                  <div className="overflow-x-auto w-full mt-4">
                    <table className="w-full border-collapse min-w-[600px]">
                      <thead>
                        <tr>
                          <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Room Code</th>
                          <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">STT Minutes</th>
                          <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">STT Cost</th>
                          <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">MT Cost</th>
                          <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Total Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {billing.rooms.map((room) => (
                          <tr key={room.room_code}>
                            <td className="p-3 border-b border-border text-sm text-fg">{room.room_code}</td>
                            <td className="p-3 border-b border-border text-sm text-fg">{room.stt_minutes.toFixed(2)}</td>
                            <td className="p-3 border-b border-border text-sm text-fg">${room.stt_cost_usd.toFixed(4)}</td>
                            <td className="p-3 border-b border-border text-sm text-fg">${room.mt_cost_usd.toFixed(4)}</td>
                            <td className="p-3 border-b border-border text-sm text-fg">${room.total_cost_usd.toFixed(4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === "history" && history && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-bold mb-5 text-fg">Room History</h2>

              <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-5 mb-8">
                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">Total Rooms</div>
                  <div className="text-3xl font-bold text-accent">{history.total_rooms}</div>
                </div>
                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">Total Minutes</div>
                  <div className="text-3xl font-bold text-accent">{history.total_stt_minutes.toFixed(2)}</div>
                </div>
                <div className="bg-bg-secondary p-5 rounded-lg text-center">
                  <div className="text-xs font-semibold text-muted mb-2">Total Cost</div>
                  <div className="text-3xl font-bold text-accent">${history.total_cost_usd.toFixed(4)}</div>
                </div>
              </div>

              {history.rooms && history.rooms.length > 0 && (
                <div className="overflow-x-auto w-full mt-4">
                  <table className="w-full border-collapse min-w-[600px]">
                    <thead>
                      <tr>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Room Code</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Created</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Duration</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Minutes</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Cost</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Participants</th>
                        <th className="text-left p-3 bg-bg-secondary font-semibold text-xs text-muted border-b-2 border-border whitespace-nowrap">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.rooms.map((room) => (
                        <tr key={room.room_code} className={room.archived ? "opacity-70" : ""}>
                          <td className="p-3 border-b border-border text-sm text-fg">
                            {room.room_code}
                            {room.archived && (
                              <span className="text-[10px] font-bold text-red-500 ml-2 px-1.5 py-0.5 bg-red-500/10 rounded">
                                ARCHIVED
                              </span>
                            )}
                          </td>
                          <td className="p-3 border-b border-border text-sm text-fg">
                            {new Date(room.created_at).toLocaleDateString()}
                          </td>
                          <td className="p-3 border-b border-border text-sm text-fg">
                            {room.duration_minutes ? `${room.duration_minutes.toFixed(0)} min` : '-'}
                          </td>
                          <td className="p-3 border-b border-border text-sm text-fg">{room.stt_minutes.toFixed(2)}</td>
                          <td className="p-3 border-b border-border text-sm text-fg">${room.total_cost_usd.toFixed(4)}</td>
                          <td className="p-3 border-b border-border text-sm text-fg">{room.participant_count}</td>
                          <td className="p-3 border-b border-border text-sm text-fg">
                            {room.archived ? (
                              <button
                                disabled
                                className="px-3 py-1.5 bg-muted/30 text-muted border-none rounded-md cursor-not-allowed text-xs font-medium"
                                title="Archived rooms cannot be viewed"
                              >
                                Archived
                              </button>
                            ) : (
                              <button
                                onClick={() => navigate(`/room/${room.room_code}`)}
                                className="px-3 py-1.5 bg-accent text-white border-none rounded-md cursor-pointer text-xs font-medium
                                           hover:bg-accent-dark transition-colors"
                              >
                                View
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {history.rooms && history.rooms.length === 0 && (
                <div className="text-center py-10 text-muted">
                  <p>No room history found</p>
                  <button
                    onClick={() => navigate("/rooms")}
                    className="px-6 py-3 bg-accent text-white border-none rounded-lg cursor-pointer text-sm font-semibold
                               mt-4 hover:bg-accent-dark transition-colors"
                  >
                    Create Your First Room
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}

