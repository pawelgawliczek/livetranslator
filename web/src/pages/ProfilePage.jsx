import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
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
  const [activeTab, setActiveTab] = useState("settings");
  const [profile, setProfile] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [billing, setBilling] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  // Form states
  const [displayName, setDisplayName] = useState("");
  const [preferredLang, setPreferredLang] = useState("en");
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
        setPreferredLang(profileData.preferred_lang);
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
          display_name: displayName,
          preferred_lang: preferredLang
        })
      });

      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setMessage("Profile updated successfully!");
      } else {
        setError("Failed to update profile");
      }
    } catch (e) {
      setError("Failed to update profile");
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters");
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
      <div style={styles.container}>
        <div style={styles.loading}>Loading...</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={{ flex: 1 }}>
        <div style={styles.header}>
        <h1 style={styles.title}>Profile Settings</h1>
        <div style={styles.headerButtons}>
          <button onClick={() => navigate("/rooms")} style={styles.backButton}>
            ← Back to Rooms
          </button>
          <button onClick={onLogout} style={styles.logoutButton}>
            Sign Out
          </button>
        </div>
      </div>

      {message && <div style={styles.message}>{message}</div>}
      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.tabs}>
        <button
          onClick={() => setActiveTab("settings")}
          style={activeTab === "settings" ? styles.tabActive : styles.tab}
        >
          Settings
        </button>
        <button
          onClick={() => setActiveTab("account")}
          style={activeTab === "account" ? styles.tabActive : styles.tab}
        >
          Account
        </button>
        <button
          onClick={() => setActiveTab("subscription")}
          style={activeTab === "subscription" ? styles.tabActive : styles.tab}
        >
          Subscription
        </button>
        <button
          onClick={() => setActiveTab("billing")}
          style={activeTab === "billing" ? styles.tabActive : styles.tab}
        >
          Billing
        </button>
        <button
          onClick={() => setActiveTab("history")}
          style={activeTab === "history" ? styles.tabActive : styles.tab}
        >
          History
        </button>
      </div>

      <div style={styles.content}>
        {activeTab === "settings" && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Settings</h2>
            <form onSubmit={handleUpdateProfile} style={styles.form}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  style={styles.input}
                  placeholder="Your name"
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Preferred Language</label>
                <select
                  value={preferredLang}
                  onChange={(e) => setPreferredLang(e.target.value)}
                  style={styles.select}
                >
                  {LANGUAGES.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.name}
                    </option>
                  ))}
                </select>
                <div style={styles.helpText}>
                  This is your default language for translations
                </div>
              </div>

              <button type="submit" style={styles.button}>
                Save Changes
              </button>
            </form>
          </div>
        )}

        {activeTab === "account" && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Account</h2>

            <div style={styles.infoGroup}>
              <div style={styles.infoLabel}>Email</div>
              <div style={styles.infoValue}>{profile?.email}</div>
            </div>

            <div style={styles.infoGroup}>
              <div style={styles.infoLabel}>Account Type</div>
              <div style={styles.infoValue}>
                {profile?.google_id ? "Google OAuth" : "Email/Password"}
              </div>
            </div>

            <div style={styles.infoGroup}>
              <div style={styles.infoLabel}>Member Since</div>
              <div style={styles.infoValue}>
                {new Date(profile?.created_at).toLocaleDateString()}
              </div>
            </div>

            <div style={styles.divider}></div>

            <h3 style={styles.subsectionTitle}>Change Password</h3>
            <form onSubmit={handleChangePassword} style={styles.form}>
              {profile?.has_password && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Current Password</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    style={styles.input}
                    placeholder="Enter current password"
                  />
                </div>
              )}

              <div style={styles.formGroup}>
                <label style={styles.label}>New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  style={styles.input}
                  placeholder="Enter new password"
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  style={styles.input}
                  placeholder="Confirm new password"
                />
              </div>

              <button type="submit" style={styles.button}>
                Change Password
              </button>
            </form>
          </div>
        )}

        {activeTab === "subscription" && subscription && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Subscription</h2>

            <div style={styles.currentPlan}>
              <div style={styles.planBadge}>
                Current Plan: <strong>{subscription.plan.toUpperCase()}</strong>
              </div>
              <div style={styles.planStatus}>
                Status: <span style={{ color: subscription.status === "active" ? "#10b981" : "#ef4444" }}>
                  {subscription.status}
                </span>
              </div>
            </div>

            <div style={styles.plansGrid}>
              <div style={subscription.plan === "free" ? styles.planCardActive : styles.planCard}>
                <h3 style={styles.planName}>Free</h3>
                <div style={styles.planPrice}>$0/month</div>
                <ul style={styles.planFeatures}>
                  <li>1 hour per month</li>
                  <li>Basic translation</li>
                  <li>Community support</li>
                </ul>
                {subscription.plan !== "free" && (
                  <button
                    onClick={() => handleChangePlan("free")}
                    style={styles.planButton}
                  >
                    Downgrade
                  </button>
                )}
              </div>

              <div style={subscription.plan === "plus" ? styles.planCardActive : styles.planCard}>
                <h3 style={styles.planName}>Plus</h3>
                <div style={styles.planPrice}>$9.99/month</div>
                <ul style={styles.planFeatures}>
                  <li>Unlimited translation</li>
                  <li>Priority support</li>
                  <li>Advanced features</li>
                </ul>
                {subscription.plan !== "plus" && (
                  <button
                    onClick={() => handleChangePlan("plus")}
                    style={styles.planButton}
                  >
                    {subscription.plan === "free" ? "Upgrade" : "Switch"}
                  </button>
                )}
              </div>

              <div style={subscription.plan === "pro" ? styles.planCardActive : styles.planCard}>
                <h3 style={styles.planName}>Pro</h3>
                <div style={styles.planPrice}>$29.99/month</div>
                <ul style={styles.planFeatures}>
                  <li>Unlimited translation</li>
                  <li>24/7 support</li>
                  <li>Advanced features</li>
                  <li>API access</li>
                </ul>
                {subscription.plan !== "pro" && (
                  <button
                    onClick={() => handleChangePlan("pro")}
                    style={styles.planButton}
                  >
                    Upgrade
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "billing" && billing && (
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Billing & Usage</h2>

            <div style={styles.billingPeriod}>
              <div>
                <strong>Current Billing Period</strong>
              </div>
              <div style={styles.periodDates}>
                {new Date(billing.billing_period_start).toLocaleDateString()} - {new Date(billing.billing_period_end).toLocaleDateString()}
              </div>
            </div>

            <div style={styles.usageGrid}>
              <div style={styles.usageCard}>
                <div style={styles.usageLabel}>STT Minutes Used</div>
                <div style={styles.usageValue}>
                  {billing.total_stt_minutes.toFixed(2)}
                  {billing.quota_minutes && ` / ${billing.quota_minutes}`}
                </div>
                {billing.quota_remaining_minutes !== null && (
                  <div style={styles.usageSubtext}>
                    {billing.quota_remaining_minutes.toFixed(2)} minutes remaining
                  </div>
                )}
              </div>

              <div style={styles.usageCard}>
                <div style={styles.usageLabel}>STT Cost</div>
                <div style={styles.usageValue}>${billing.total_stt_cost_usd.toFixed(4)}</div>
              </div>

              <div style={styles.usageCard}>
                <div style={styles.usageLabel}>Translation Cost</div>
                <div style={styles.usageValue}>${billing.total_mt_cost_usd.toFixed(4)}</div>
              </div>

              <div style={styles.usageCard}>
                <div style={styles.usageLabel}>Total Cost</div>
                <div style={styles.usageValue}>${billing.total_cost_usd.toFixed(4)}</div>
              </div>
            </div>

            {billing.rooms && billing.rooms.length > 0 && (
              <>
                <h3 style={styles.subsectionTitle}>Room Usage</h3>
                <div style={styles.table}>
                  <table style={styles.tableElement}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Room Code</th>
                        <th style={styles.th}>STT Minutes</th>
                        <th style={styles.th}>STT Cost</th>
                        <th style={styles.th}>MT Cost</th>
                        <th style={styles.th}>Total Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billing.rooms.map((room) => (
                        <tr key={room.room_code}>
                          <td style={styles.td}>{room.room_code}</td>
                          <td style={styles.td}>{room.stt_minutes.toFixed(2)}</td>
                          <td style={styles.td}>${room.stt_cost_usd.toFixed(4)}</td>
                          <td style={styles.td}>${room.mt_cost_usd.toFixed(4)}</td>
                          <td style={styles.td}>${room.total_cost_usd.toFixed(4)}</td>
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
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Room History</h2>

            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Total Rooms</div>
                <div style={styles.statValue}>{history.total_rooms}</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Total Minutes</div>
                <div style={styles.statValue}>{history.total_stt_minutes.toFixed(2)}</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Total Cost</div>
                <div style={styles.statValue}>${history.total_cost_usd.toFixed(4)}</div>
              </div>
            </div>

            {history.rooms && history.rooms.length > 0 && (
              <div style={styles.table}>
                <table style={styles.tableElement}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Room Code</th>
                      <th style={styles.th}>Created</th>
                      <th style={styles.th}>Duration</th>
                      <th style={styles.th}>Minutes</th>
                      <th style={styles.th}>Cost</th>
                      <th style={styles.th}>Participants</th>
                      <th style={styles.th}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.rooms.map((room) => (
                      <tr key={room.room_code} style={room.archived ? styles.archivedRow : {}}>
                        <td style={styles.td}>
                          {room.room_code}
                          {room.archived && (
                            <span style={styles.archivedBadge}> ARCHIVED</span>
                          )}
                        </td>
                        <td style={styles.td}>{new Date(room.created_at).toLocaleDateString()}</td>
                        <td style={styles.td}>
                          {room.duration_minutes ? `${room.duration_minutes.toFixed(0)} min` : '-'}
                        </td>
                        <td style={styles.td}>{room.stt_minutes.toFixed(2)}</td>
                        <td style={styles.td}>${room.total_cost_usd.toFixed(4)}</td>
                        <td style={styles.td}>{room.participant_count}</td>
                        <td style={styles.td}>
                          {room.archived ? (
                            <button
                              disabled
                              style={styles.actionButtonDisabled}
                              title="Archived rooms cannot be viewed"
                            >
                              Archived
                            </button>
                          ) : (
                            <button
                              onClick={() => navigate(`/room/${room.room_code}`)}
                              style={styles.actionButton}
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
              <div style={styles.emptyState}>
                <p>No room history found</p>
                <button onClick={() => navigate("/rooms")} style={styles.button}>
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

const styles = {
  container: {
    minHeight: "100vh",
    background: "#0a0a0a",
    padding: "20px 20px 10px 20px",
    display: "flex",
    flexDirection: "column"
  },
  loading: {
    color: "white",
    fontSize: "20px",
    textAlign: "center",
    marginTop: "100px"
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "30px",
    flexWrap: "wrap",
    gap: "10px"
  },
  title: {
    color: "white",
    fontSize: "32px",
    fontWeight: "bold",
    margin: 0
  },
  headerButtons: {
    display: "flex",
    gap: "10px"
  },
  backButton: {
    padding: "10px 20px",
    background: "#6366f1",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500"
  },
  logoutButton: {
    padding: "10px 20px",
    background: "#ef4444",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500"
  },
  message: {
    background: "#10b981",
    color: "white",
    padding: "12px 20px",
    borderRadius: "8px",
    marginBottom: "20px"
  },
  error: {
    background: "#ef4444",
    color: "white",
    padding: "12px 20px",
    borderRadius: "8px",
    marginBottom: "20px"
  },
  tabs: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
    flexWrap: "wrap"
  },
  tab: {
    padding: "12px 24px",
    background: "rgba(255,255,255,0.2)",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500",
    transition: "all 0.2s"
  },
  tabActive: {
    padding: "12px 24px",
    background: "#1a1a1a",
    color: "#667eea",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    transition: "all 0.2s"
  },
  content: {
    background: "#1a1a1a",
    borderRadius: "12px",
    padding: "30px",
    minHeight: "400px"
  },
  section: {
    maxWidth: "900px",
    margin: "0 auto"
  },
  sectionTitle: {
    fontSize: "24px",
    fontWeight: "bold",
    marginBottom: "20px",
    color: "white"
  },
  subsectionTitle: {
    fontSize: "18px",
    fontWeight: "600",
    marginTop: "30px",
    marginBottom: "15px",
    color: "white"
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  label: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#374151"
  },
  input: {
    padding: "12px",
    border: "1px solid #444",
    borderRadius: "8px",
    fontSize: "14px",
    outline: "none",
    transition: "border-color 0.2s"
  },
  select: {
    padding: "12px",
    border: "1px solid #444",
    borderRadius: "8px",
    fontSize: "14px",
    outline: "none",
    transition: "border-color 0.2s",
    background: "white"
  },
  helpText: {
    fontSize: "12px",
    color: "#6b7280"
  },
  button: {
    padding: "12px 24px",
    background: "#667eea",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    alignSelf: "flex-start",
    transition: "background 0.2s"
  },
  infoGroup: {
    marginBottom: "15px",
    padding: "12px",
    background: "#2a2a2a",
    borderRadius: "8px"
  },
  infoLabel: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#6b7280",
    marginBottom: "4px"
  },
  infoValue: {
    fontSize: "14px",
    color: "white"
  },
  divider: {
    height: "1px",
    background: "#e5e7eb",
    margin: "30px 0"
  },
  currentPlan: {
    background: "#2a2a2a",
    padding: "20px",
    borderRadius: "8px",
    marginBottom: "30px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "10px"
  },
  planBadge: {
    fontSize: "18px",
    color: "white"
  },
  planStatus: {
    fontSize: "14px",
    color: "#6b7280"
  },
  plansGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "20px"
  },
  planCard: {
    border: "2px solid #e5e7eb",
    borderRadius: "12px",
    padding: "24px",
    background: "#1a1a1a",
    transition: "all 0.2s"
  },
  planCardActive: {
    border: "2px solid #667eea",
    borderRadius: "12px",
    padding: "24px",
    background: "#f5f3ff",
    transition: "all 0.2s"
  },
  planName: {
    fontSize: "20px",
    fontWeight: "bold",
    marginBottom: "10px",
    color: "white"
  },
  planPrice: {
    fontSize: "24px",
    fontWeight: "bold",
    color: "#667eea",
    marginBottom: "20px"
  },
  planFeatures: {
    listStyle: "none",
    padding: 0,
    margin: "0 0 20px 0",
    fontSize: "14px",
    color: "#6b7280"
  },
  planButton: {
    width: "100%",
    padding: "10px",
    background: "#667eea",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600"
  },
  billingPeriod: {
    background: "#2a2a2a",
    padding: "16px",
    borderRadius: "8px",
    marginBottom: "20px",
    textAlign: "center"
  },
  periodDates: {
    fontSize: "14px",
    color: "#6b7280",
    marginTop: "8px"
  },
  usageGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "20px",
    marginBottom: "30px"
  },
  usageCard: {
    background: "#2a2a2a",
    padding: "20px",
    borderRadius: "8px",
    textAlign: "center"
  },
  usageLabel: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#6b7280",
    marginBottom: "8px"
  },
  usageValue: {
    fontSize: "24px",
    fontWeight: "bold",
    color: "white"
  },
  usageSubtext: {
    fontSize: "12px",
    color: "#6b7280",
    marginTop: "4px"
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "20px",
    marginBottom: "30px"
  },
  statCard: {
    background: "#2a2a2a",
    padding: "20px",
    borderRadius: "8px",
    textAlign: "center"
  },
  statLabel: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#6b7280",
    marginBottom: "8px"
  },
  statValue: {
    fontSize: "28px",
    fontWeight: "bold",
    color: "#667eea"
  },
  table: {
    overflowX: "auto"
  },
  tableElement: {
    width: "100%",
    borderCollapse: "collapse"
  },
  th: {
    textAlign: "left",
    padding: "12px",
    background: "#2a2a2a",
    fontWeight: "600",
    fontSize: "12px",
    color: "#6b7280",
    borderBottom: "2px solid #e5e7eb"
  },
  td: {
    padding: "12px",
    borderBottom: "1px solid #e5e7eb",
    fontSize: "14px",
    color: "white"
  },
  actionButton: {
    padding: "6px 12px",
    background: "#667eea",
    color: "white",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: "500"
  },
  actionButtonDisabled: {
    padding: "6px 12px",
    background: "#4a4a4a",
    color: "#999",
    border: "none",
    borderRadius: "6px",
    cursor: "not-allowed",
    fontSize: "12px",
    fontWeight: "500"
  },
  archivedRow: {
    opacity: 0.7
  },
  archivedBadge: {
    fontSize: "10px",
    fontWeight: "bold",
    color: "#ef4444",
    marginLeft: "8px",
    padding: "2px 6px",
    background: "rgba(239, 68, 68, 0.1)",
    borderRadius: "4px"
  },
  statusBadgeActive: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#10b981",
    padding: "4px 8px",
    background: "rgba(16, 185, 129, 0.1)",
    borderRadius: "4px"
  },
  statusBadgeArchived: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#ef4444",
    padding: "4px 8px",
    background: "rgba(239, 68, 68, 0.1)",
    borderRadius: "4px"
  },
  emptyState: {
    textAlign: "center",
    padding: "40px",
    color: "#6b7280"
  }
};
