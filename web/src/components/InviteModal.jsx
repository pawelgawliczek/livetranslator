import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import Modal from "./ui/Modal";
import Button from "./ui/Button";

export default function InviteModal({ roomCode, onClose }) {
  const { t } = useTranslation();
  const [inviteData, setInviteData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [shareMethod, setShareMethod] = useState("qr"); // qr, link, email

  useEffect(() => {
    fetchInvite();
  }, [roomCode]);

  async function fetchInvite() {
    try {
      setLoading(true);
      const response = await fetch(`/api/invites/generate/${roomCode}`, {
        method: "POST"
      });

      if (!response.ok) {
        throw new Error("Failed to generate invite");
      }

      const data = await response.json();
      setInviteData(data);
    } catch (e) {
      console.error("Failed to fetch invite:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function copyLink() {
    if (!inviteData) return;
    navigator.clipboard.writeText(inviteData.invite_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function shareViaEmail() {
    if (!inviteData) return;
    const subject = encodeURIComponent(t('invite.emailSubject'));
    const body = encodeURIComponent(
      `${t('invite.emailBodyGreeting')}\n\n` +
      `${t('invite.emailBodyLink')} ${inviteData.invite_url}\n\n` +
      t('invite.emailBodyExpiry', { minutes: inviteData.expires_in_minutes })
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  function downloadQR() {
    if (!inviteData) return;
    const link = document.createElement("a");
    link.href = inviteData.qr_code;
    link.download = `livetranslator-${roomCode}-qr.png`;
    link.click();
  }

  if (loading) {
    return (
      <Modal isOpen={true} onClose={onClose} title={t('invite.generatingInvite')}>
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="w-12 h-12 border-4 border-border border-t-accent rounded-full animate-spin"></div>
        </div>
      </Modal>
    );
  }

  if (error) {
    return (
      <Modal isOpen={true} onClose={onClose} title={t('invite.error')}>
        <p className="text-red-500 text-center mb-6">{error}</p>
        <Button variant="primary" onClick={onClose} className="w-full">
          {t('common.close')}
        </Button>
      </Modal>
    );
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={t('invite.title')}>
      {/* Share method tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2 flex-wrap">
        <button
          className={`flex-1 min-w-[90px] px-2 py-3 bg-transparent border-none rounded-t-lg text-sm font-medium transition-all text-center ${
            shareMethod === "qr"
              ? "bg-bg-secondary text-accent border-b-2 border-accent"
              : "text-muted hover:text-fg"
          }`}
          onClick={() => setShareMethod("qr")}
        >
          {t('invite.qrCodeTab')}
        </button>
        <button
          className={`flex-1 min-w-[90px] px-2 py-3 bg-transparent border-none rounded-t-lg text-sm font-medium transition-all text-center ${
            shareMethod === "link"
              ? "bg-bg-secondary text-accent border-b-2 border-accent"
              : "text-muted hover:text-fg"
          }`}
          onClick={() => setShareMethod("link")}
        >
          {t('invite.linkTab')}
        </button>
        <button
          className={`flex-1 min-w-[90px] px-2 py-3 bg-transparent border-none rounded-t-lg text-sm font-medium transition-all text-center ${
            shareMethod === "email"
              ? "bg-bg-secondary text-accent border-b-2 border-accent"
              : "text-muted hover:text-fg"
          }`}
          onClick={() => setShareMethod("email")}
        >
          {t('invite.emailTab')}
        </button>
      </div>

      {/* QR Code view */}
      {shareMethod === "qr" && inviteData && (
        <div className="min-h-[300px]">
          <p className="text-muted text-center mb-6 leading-relaxed">
            {t('invite.qrInstructions')}
          </p>
          <div className="flex justify-center mb-6">
            <img
              src={inviteData.qr_code}
              alt="QR Code"
              className="w-[min(280px,70vw)] h-[min(280px,70vw)] rounded-lg border-2 border-border bg-white p-3"
            />
          </div>
          <Button variant="secondary" onClick={downloadQR} className="w-full">
            {t('invite.downloadQR')}
          </Button>
        </div>
      )}

      {/* Link view */}
      {shareMethod === "link" && inviteData && (
        <div className="min-h-[300px]">
          <p className="text-muted text-center mb-6 leading-relaxed">
            {t('invite.linkInstructions')}
          </p>
          <div className="mb-6">
            <input
              type="text"
              readOnly
              value={inviteData.invite_url}
              onClick={(e) => e.target.select()}
              className="w-full px-3.5 py-3 bg-bg-secondary border border-border rounded-lg text-accent text-sm font-mono"
            />
          </div>
          <Button variant="primary" onClick={copyLink} className="w-full">
            {copied ? "✓ Copied!" : t('rooms.copyCode')}
          </Button>
        </div>
      )}

      {/* Email view */}
      {shareMethod === "email" && inviteData && (
        <div className="min-h-[300px]">
          <p className="text-muted text-center mb-6 leading-relaxed">
            {t('invite.emailInstructions')}
          </p>
          <div className="bg-bg-secondary rounded-lg p-4 mb-6 border border-border">
            <div className="text-muted text-sm mb-3 font-semibold">
              {t('invite.preview')}
            </div>
            <div className="text-fg text-sm leading-relaxed">
              <p><strong>{t('invite.emailBodyGreeting')}</strong></p>
              <p>{t('invite.emailBodyLink')}<br/>
                <code className="bg-bg px-2 py-1 rounded text-xs text-accent break-all inline-block mt-1">
                  {inviteData.invite_url}
                </code>
              </p>
              <p className="text-xs text-muted">
                {t('invite.emailBodyExpiry', { minutes: inviteData.expires_in_minutes })}
              </p>
            </div>
          </div>
          <Button variant="primary" onClick={shareViaEmail} className="w-full">
            {t('invite.openEmail')}
          </Button>
        </div>
      )}

      {/* Room info */}
      <div className="bg-bg-secondary rounded-lg p-4 mt-6 border border-border">
        <div className="flex justify-between items-center py-2">
          <span className="text-muted text-sm">{t('invite.roomLabel')}</span>
          <code className="text-accent text-sm font-mono font-semibold">{roomCode}</code>
        </div>
        <div className="flex justify-between items-center py-2">
          <span className="text-muted text-sm">{t('invite.expiresLabel')}</span>
          <span className="text-accent text-sm font-mono font-semibold">
            {t('invite.expiresInMinutes', { minutes: inviteData?.expires_in_minutes || 30 })}
          </span>
        </div>
      </div>
    </Modal>
  );
}
