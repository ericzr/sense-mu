"use client";

import {
  AlertCircle,
  Check,
  Clipboard,
  Clock3,
  Link2,
  LoaderCircle,
  ShieldCheck,
  UserMinus,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  catalogApi,
  type CurrentIdentity,
  type Workspace,
  type WorkspaceAccessEvent,
  type WorkspaceInvitation,
  type WorkspaceInvitationSecret,
  type WorkspaceMember,
} from "../../lib/catalog-api";

const roleLabels: Record<string, string> = {
  owner: "所有者",
  admin: "管理员",
  member: "成员",
  viewer: "查看者",
};

const invitationStatusLabels: Record<string, string> = {
  pending: "待接受",
  accepted: "已接受",
  revoked: "已撤销",
  expired: "已过期",
};

const eventLabels: Record<string, string> = {
  "invitation.created": "创建了成员邀请",
  "invitation.accepted": "接受了成员邀请",
  "invitation.revoked": "撤销了成员邀请",
  "membership.role_changed": "调整了成员角色",
  "membership.suspended": "停用了成员身份",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function memberName(member: WorkspaceMember): string {
  return member.display_name || member.email || "未命名成员";
}

export function WorkspaceSettings() {
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [identity, setIdentity] = useState<CurrentIdentity | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [events, setEvents] = useState<WorkspaceAccessEvent[]>([]);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member" | "viewer">(
    "member",
  );
  const [visibleInvitation, setVisibleInvitation] =
    useState<WorkspaceInvitationSecret | null>(null);
  const [incomingToken, setIncomingToken] = useState<string | null>(null);

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === workspaceId) ?? null,
    [workspaces, workspaceId],
  );
  const canManage =
    selectedWorkspace?.role === "owner" || selectedWorkspace?.role === "admin";

  async function loadCollaboration(nextWorkspaceId: string) {
    const [nextMembers, nextInvitations, nextEvents] = await Promise.all([
      catalogApi.listWorkspaceMembers(nextWorkspaceId),
      catalogApi.listWorkspaceInvitations(nextWorkspaceId),
      catalogApi.listWorkspaceAccessEvents(nextWorkspaceId),
    ]);
    setMembers(nextMembers);
    setInvitations(nextInvitations);
    setEvents(nextEvents);
  }

  useEffect(() => {
    const hash = window.location.hash;
    if (hash.startsWith("#invite=")) {
      setIncomingToken(decodeURIComponent(hash.slice("#invite=".length)));
    }
    void Promise.all([catalogApi.getCurrentIdentity(), catalogApi.listWorkspaces()])
      .then(async ([nextIdentity, nextWorkspaces]) => {
        setIdentity(nextIdentity);
        setWorkspaces(nextWorkspaces);
        const selected =
          nextWorkspaces.find(
            (workspace) => workspace.role === "owner" || workspace.role === "admin",
          )?.id ?? nextWorkspaces[0]?.id ?? "";
        setWorkspaceId(selected);
        const selectedRole = nextWorkspaces.find(
          (workspace) => workspace.id === selected,
        )?.role;
        if (selected && (selectedRole === "owner" || selectedRole === "admin")) {
          await loadCollaboration(selected);
        }
      })
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : "工作区设置加载失败"),
      )
      .finally(() => setLoading(false));
  }, []);

  async function changeWorkspace(nextWorkspaceId: string) {
    setWorkspaceId(nextWorkspaceId);
    setVisibleInvitation(null);
    setNotice(null);
    setError(null);
    const workspace = workspaces.find((item) => item.id === nextWorkspaceId);
    if (workspace?.role !== "owner" && workspace?.role !== "admin") {
      setMembers([]);
      setInvitations([]);
      setEvents([]);
      return;
    }
    setLoading(true);
    try {
      await loadCollaboration(nextWorkspaceId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作区设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function createInvitation(event: FormEvent) {
    event.preventDefault();
    if (!workspaceId) return;
    setBusyId("invite");
    setError(null);
    setNotice(null);
    setVisibleInvitation(null);
    try {
      const invitation = await catalogApi.createWorkspaceInvitation(workspaceId, {
        email,
        role: inviteRole,
      });
      setVisibleInvitation(invitation);
      setEmail("");
      await loadCollaboration(workspaceId);
      setNotice("邀请已创建。链接只显示这一次，请立即复制并安全发送。 ");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "邀请创建失败");
    } finally {
      setBusyId(null);
    }
  }

  async function copyInvitation() {
    if (!visibleInvitation) return;
    try {
      await navigator.clipboard.writeText(visibleInvitation.acceptance_url);
      setNotice("邀请链接已复制");
    } catch {
      setError("无法自动复制，请手动复制邀请链接");
    }
  }

  async function acceptInvitation() {
    if (!incomingToken) return;
    setBusyId("accept");
    setError(null);
    try {
      await catalogApi.acceptWorkspaceInvitation(incomingToken);
      const [nextIdentity, nextWorkspaces] = await Promise.all([
        catalogApi.getCurrentIdentity(),
        catalogApi.listWorkspaces(),
      ]);
      setIdentity(nextIdentity);
      setWorkspaces(nextWorkspaces);
      setIncomingToken(null);
      window.history.replaceState(null, "", "/settings");
      setNotice("邀请已接受，工作区权限已经生效");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "邀请接受失败");
    } finally {
      setBusyId(null);
    }
  }

  async function updateRole(
    member: WorkspaceMember,
    role: "admin" | "member" | "viewer",
  ) {
    if (!workspaceId || role === member.role) return;
    setBusyId(member.id);
    setError(null);
    try {
      await catalogApi.updateWorkspaceMemberRole(workspaceId, member.id, role);
      await loadCollaboration(workspaceId);
      setNotice(`${memberName(member)} 的角色已更新`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "成员角色更新失败");
    } finally {
      setBusyId(null);
    }
  }

  async function suspendMember(member: WorkspaceMember) {
    if (!workspaceId || !window.confirm(`确认停用 ${memberName(member)} 的工作区权限？`)) {
      return;
    }
    setBusyId(member.id);
    setError(null);
    try {
      await catalogApi.suspendWorkspaceMember(workspaceId, member.id);
      await loadCollaboration(workspaceId);
      setNotice(`${memberName(member)} 的工作区权限已停用`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "成员停用失败");
    } finally {
      setBusyId(null);
    }
  }

  async function revokeInvitation(invitation: WorkspaceInvitation) {
    if (!workspaceId) return;
    setBusyId(invitation.id);
    setError(null);
    try {
      await catalogApi.revokeWorkspaceInvitation(workspaceId, invitation.id);
      await loadCollaboration(workspaceId);
      setNotice(`发往 ${invitation.email} 的邀请已撤销`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "邀请撤销失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="settings-main">
      <section className="settings-heading">
        <div>
          <span className="eyebrow">工作区治理</span>
          <h1>成员与权限</h1>
          <p>只保留邀请、角色和审计三项必要能力。</p>
        </div>
        <label className="settings-workspace-select">
          <span>当前工作区</span>
          <select
            value={workspaceId}
            onChange={(event) => void changeWorkspace(event.target.value)}
          >
            {workspaces.map((workspace) => (
              <option value={workspace.id} key={workspace.id}>
                {workspace.name} · {roleLabels[workspace.role]}
              </option>
            ))}
          </select>
        </label>
      </section>

      {incomingToken ? (
        <section className="settings-invite-accept" aria-label="接受工作区邀请">
          <span className="settings-icon soft-blue"><Link2 size={19} /></span>
          <div>
            <strong>你收到一份工作区邀请</strong>
            <p>将以 {identity?.email ?? "当前登录邮箱"} 验证并加入对应工作区。</p>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={busyId === "accept"}
            onClick={() => void acceptInvitation()}
          >
            {busyId === "accept" ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}
            接受邀请
          </button>
        </section>
      ) : null}

      {error ? (
        <div className="settings-message is-error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button type="button" aria-label="关闭错误提示" onClick={() => setError(null)}>
            <X size={15} />
          </button>
        </div>
      ) : null}
      {notice ? (
        <div className="settings-message" role="status">
          <Check size={16} />
          <span>{notice}</span>
          <button type="button" aria-label="关闭状态提示" onClick={() => setNotice(null)}>
            <X size={15} />
          </button>
        </div>
      ) : null}

      {loading ? (
        <section className="settings-loading">
          <LoaderCircle className="spin" size={20} />
          <span>正在读取成员与权限记录</span>
        </section>
      ) : !workspaceId ? (
        <section className="settings-empty">请先创建一个工作区。</section>
      ) : !canManage ? (
        <section className="settings-empty">
          <ShieldCheck size={24} />
          <strong>当前角色无需管理成员</strong>
          <span>成员和查看者可以使用工作区资源，但不能读取成员目录与权限审计。</span>
        </section>
      ) : (
        <div className="settings-grid">
          <section className="settings-panel settings-members-panel">
            <header>
              <div>
                <span className="settings-section-icon"><Users size={18} /></span>
                <div>
                  <h2>成员</h2>
                  <p>{members.filter((member) => member.status === "active").length} 位有效成员</p>
                </div>
              </div>
            </header>
            <div className="settings-member-list">
              {members.map((member) => {
                const protectedMember = member.role === "owner" || member.is_current_user;
                const canEditAdmin = selectedWorkspace?.role === "owner";
                const canEdit =
                  member.status === "active" &&
                  !protectedMember &&
                  (member.role !== "admin" || canEditAdmin);
                return (
                  <article className="settings-member-row" key={member.id}>
                    <span className="settings-avatar">
                      {memberName(member).slice(0, 2).toUpperCase()}
                    </span>
                    <div className="settings-member-copy">
                      <strong>{memberName(member)}</strong>
                      <span>{member.email ?? "未提供邮箱"}</span>
                    </div>
                    {canEdit ? (
                      <select
                        aria-label={`调整 ${memberName(member)} 的角色`}
                        value={member.role}
                        disabled={busyId === member.id}
                        onChange={(event) =>
                          void updateRole(
                            member,
                            event.target.value as "admin" | "member" | "viewer",
                          )
                        }
                      >
                        {selectedWorkspace?.role === "owner" ? <option value="admin">管理员</option> : null}
                        <option value="member">成员</option>
                        <option value="viewer">查看者</option>
                      </select>
                    ) : (
                      <span className={`settings-role-pill${member.status !== "active" ? " is-muted" : ""}`}>
                        {member.status === "active" ? roleLabels[member.role] : "已停用"}
                      </span>
                    )}
                    {canEdit ? (
                      <button
                        className="settings-icon-button"
                        type="button"
                        aria-label={`停用 ${memberName(member)}`}
                        title="停用成员"
                        disabled={busyId === member.id}
                        onClick={() => void suspendMember(member)}
                      >
                        <UserMinus size={16} />
                      </button>
                    ) : (
                      <span className="settings-member-note">
                        {member.is_current_user ? "当前账号" : member.role === "owner" ? "受保护" : ""}
                      </span>
                    )}
                  </article>
                );
              })}
            </div>
          </section>

          <aside className="settings-panel settings-invite-panel">
            <header>
              <span className="settings-section-icon soft-purple"><UserPlus size={18} /></span>
              <div>
                <h2>邀请成员</h2>
                <p>链接有效期为 7 天</p>
              </div>
            </header>
            <form className="settings-invite-form" onSubmit={(event) => void createInvitation(event)}>
              <label>
                <span>邮箱</span>
                <input
                  type="email"
                  value={email}
                  required
                  placeholder="name@company.com"
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label>
                <span>角色</span>
                <select
                  value={inviteRole}
                  onChange={(event) => setInviteRole(event.target.value as "admin" | "member" | "viewer")}
                >
                  {selectedWorkspace?.role === "owner" ? <option value="admin">管理员</option> : null}
                  <option value="member">成员</option>
                  <option value="viewer">查看者</option>
                </select>
              </label>
              <button className="primary-button" type="submit" disabled={busyId === "invite"}>
                {busyId === "invite" ? <LoaderCircle className="spin" size={16} /> : <UserPlus size={16} />}
                创建邀请
              </button>
            </form>
            {visibleInvitation ? (
              <div className="settings-secret">
                <div>
                  <strong>仅显示一次</strong>
                  <span>服务器只保存密钥摘要，刷新后无法找回。</span>
                </div>
                <code>{visibleInvitation.acceptance_url}</code>
                <button className="secondary-button" type="button" onClick={() => void copyInvitation()}>
                  <Clipboard size={15} />
                  复制邀请链接
                </button>
              </div>
            ) : null}
          </aside>

          <section className="settings-panel settings-invitations-panel">
            <header>
              <div>
                <span className="settings-section-icon soft-sand"><Clock3 size={18} /></span>
                <div>
                  <h2>邀请记录</h2>
                  <p>历史链接不会再次显示</p>
                </div>
              </div>
            </header>
            <div className="settings-invitation-list">
              {invitations.length ? invitations.map((invitation) => (
                <article key={invitation.id}>
                  <div>
                    <strong>{invitation.email}</strong>
                    <span>{roleLabels[invitation.role]} · {formatDate(invitation.created_at)}</span>
                  </div>
                  <span className={`settings-role-pill${invitation.status !== "pending" ? " is-muted" : ""}`}>
                    {invitationStatusLabels[invitation.status]}
                  </span>
                  {invitation.status === "pending" ? (
                    <button
                      className="settings-text-button"
                      type="button"
                      disabled={busyId === invitation.id}
                      onClick={() => void revokeInvitation(invitation)}
                    >
                      撤销
                    </button>
                  ) : null}
                </article>
              )) : <p className="settings-list-empty">暂无邀请记录</p>}
            </div>
          </section>

          <section className="settings-panel settings-audit-panel">
            <header>
              <div>
                <span className="settings-section-icon soft-green"><ShieldCheck size={18} /></span>
                <div>
                  <h2>权限审计</h2>
                  <p>不可变更的最近操作记录</p>
                </div>
              </div>
            </header>
            <div className="settings-audit-list">
              {events.length ? events.map((event) => (
                <article key={event.id}>
                  <span className="settings-audit-dot" aria-hidden="true" />
                  <div>
                    <strong>{event.actor_name}</strong>
                    <p>
                      {eventLabels[event.event_type] ?? event.event_type}
                      {event.target_name ? ` · ${event.target_name}` : event.details.email ? ` · ${event.details.email}` : ""}
                    </p>
                  </div>
                  <time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time>
                </article>
              )) : <p className="settings-list-empty">暂无权限变更记录</p>}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
