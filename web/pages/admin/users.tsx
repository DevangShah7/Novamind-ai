import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/router';
import { Search, Users as UsersIcon, Shield, Mail, X, Trash2, Pencil, RefreshCw, Plus, Loader2 } from 'lucide-react';
import { getUsers, createUser, updateUser, deleteUser } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import { User } from '../../types';
import AppShell from '../../components/AppShell';
import { Skeleton } from '../../components/ui/Skeleton';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Badge } from '../../components/ui/Badge';
import { toast } from '../../components/ui/Toaster';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog';
import { passwordIssues, PASSWORD_MIN_LENGTH } from '../../lib/validation';
import { StaggerChildren, StaggerItem } from '../../components/motion';

interface FormState {
  email: string;
  username: string;
  full_name: string;
  password: string;
  is_admin: boolean;
  is_active: boolean;
  is_verified: boolean;
}

const blankForm: FormState = {
  email: '',
  username: '',
  full_name: '',
  password: '',
  is_admin: false,
  is_active: true,
  is_verified: true,
};

/**
 * Users Management — the admin's view of every account in the system.
 *
 *   • Search filters live as the admin types (email / username / name)
 *   • "New user" creates an account that's already verified and
 *     immediately usable (admin path bypasses the email round-trip)
 *   • Per-row Edit updates the user (including a fresh password when
 *     supplied)
 *   • Per-row "Mark verified" unblocks a user who lost the email
 *   • Per-row Delete requires typing the user's email to confirm —
 *     mirrors GitHub's destructive-action guard
 *
 * The 422 / 4xx / 5xx errors are surfaced verbatim via
 * `extractErrorMessage` so an admin sees "Password must contain at
 * least one letter and one digit" rather than a generic alert.
 */
export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [mounted, setMounted] = useState(false);
  const [search, setSearch] = useState('');

  // Modal state — exactly one of {create, edit, delete} can be open.
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);

  const router = useRouter();

  useEffect(() => {
    setMounted(true);
    loadUsers();
  }, []);

  const loadUsers = async () => {
    if (!me) {
      router.replace('/login');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const usersData = await getUsers();
      setUsers(usersData);
    } catch (err) {
      const msg =
        'Failed to fetch users: ' + (err instanceof Error ? err.message : String(err));
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => {
      const hay = [u.email, u.username, u.full_name]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  }, [users, search]);

  if (!mounted) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <Skeleton className="mb-6 h-10 w-64" />
        <Skeleton className="mb-4 h-10 w-full rounded-xl" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  }

  if (!me) return null;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <UsersIcon className="h-5 w-5 text-primary" />
              <h1 className="text-2xl font-bold tracking-tight text-foreground">Users Management</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              {loading
                ? 'Loading…'
                : `${filtered.length}${search ? ` of ${users.length}` : ''} ${
                    filtered.length === 1 ? 'user' : 'users'
                  }`}
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            New user
          </Button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
            {error}
          </div>
        )}

        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>User list</CardTitle>
                <CardDescription>Create, edit, disable, or remove accounts.</CardDescription>
              </div>
              <div className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by email, name, username…"
                  className="pl-9"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-6">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-3 w-56" />
                    </div>
                  </div>
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                {search
                  ? `No users match "${search}".`
                  : 'No users found.'}
              </div>
            ) : (
              <StaggerChildren className="divide-y divide-border" gap={0.04}>
                {filtered.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    isMe={me.id === u.id}
                    onEdit={() => setEditing(u)}
                    onDelete={() => setDeleting(u)}
                    onMarkVerified={async () => {
                      try {
                        const updated = await updateUser(u.id, { is_verified: true });
                        setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, ...updated } : x)));
                        toast.success(`${u.email} is now verified.`);
                      } catch (err: any) {
                        toast.error(err?.message || 'Could not update user');
                      }
                    }}
                  />
                ))}
              </StaggerChildren>
            )}
          </CardContent>
        </Card>
      </div>

      <UserFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        mode="create"
        onSaved={async () => {
          setCreateOpen(false);
          await loadUsers();
        }}
      />

      <UserFormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        mode="edit"
        user={editing}
        onSaved={async (updated) => {
          setUsers((prev) => prev.map((x) => (x.id === updated.id ? { ...x, ...updated } : x)));
          setEditing(null);
        }}
      />

      <DeleteUserDialog
        user={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={(id) => {
          setUsers((prev) => prev.filter((x) => x.id !== id));
          setDeleting(null);
        }}
      />
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Row

function UserRow({
  user: u,
  isMe,
  onEdit,
  onDelete,
  onMarkVerified,
}: {
  user: User;
  isMe: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onMarkVerified: () => void;
}) {
  return (
    <StaggerItem>
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 transition-colors hover:bg-muted/30">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground">
            {(u.full_name || u.username || u.email || '?').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-sm font-semibold text-foreground">
                {u.full_name || u.username || u.email || `User #${u.id}`}
              </h3>
              {isMe && <Badge variant="outline">You</Badge>}
              {u.is_admin && (
                <Badge variant="default" className="gap-1">
                  <Shield className="h-3 w-3" />
                  Admin
                </Badge>
              )}
            </div>
            <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
              <Mail className="h-3 w-3" />
              {u.email || 'No email'}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant={u.is_active ? 'success' : 'secondary'}>
            {u.is_active ? 'Active' : 'Inactive'}
          </Badge>
          <Badge variant={u.is_verified ? 'success' : 'warning'}>
            {u.is_verified ? 'Verified' : 'Unverified'}
          </Badge>
          {!u.is_verified && (
            <Button size="sm" variant="ghost" onClick={onMarkVerified} title="Mark this user as verified">
              <RefreshCw className="h-3.5 w-3.5" />
              Mark verified
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onEdit}>
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
            disabled={isMe}
            title={isMe ? "You can't delete your own account here" : 'Delete this user'}
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>
    </StaggerItem>
  );
}

// ---------------------------------------------------------------------------
// Create / Edit dialog — single component, two modes. The form layout is
// identical; only the submit copy and which fields are required differ.

function UserFormDialog({
  open,
  onOpenChange,
  mode,
  user,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: 'create' | 'edit';
  user?: User | null;
  onSaved: (saved: User) => Promise<void> | void;
}) {
  const [form, setForm] = useState<FormState>(blankForm);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Reset the form every time the dialog opens so an "edit user A,
  // close, edit user B" sequence never shows A's stale data.
  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && user) {
      setForm({
        email: user.email ?? '',
        username: user.username ?? '',
        full_name: user.full_name ?? '',
        password: '',
        is_admin: !!user.is_admin,
        is_active: user.is_active,
        is_verified: user.is_verified,
      });
    } else {
      setForm(blankForm);
    }
    setFormError('');
  }, [open, mode, user]);

  // Client-side password rules — same as signup, so an admin can't
  // provision a weak account that the public flow would reject.
  // On edit, an empty password means "leave it unchanged", so the
  // rules only apply when the field is non-empty.
  const pwdIssues =
    form.password || mode === 'create'
      ? passwordIssues(form.password, form.email)
      : [];
  const pwdOk = mode === 'edit' ? form.password === '' || pwdIssues.length === 0 : pwdIssues.length === 0;
  const canSubmit =
    form.email.trim().length > 0 &&
    pwdOk &&
    (mode === 'edit' || form.password.length > 0) &&
    !submitting;

  const submit = async () => {
    setFormError('');
    setSubmitting(true);
    try {
      if (mode === 'create') {
        const created = await createUser({
          email: form.email,
          username: form.username || undefined,
          full_name: form.full_name || undefined,
          password: form.password,
          is_admin: form.is_admin,
        });
        toast.success(`Created ${created.email}`);
        await onSaved(created);
      } else if (user) {
        const payload: Record<string, any> = {
          email: form.email,
          username: form.username || null,
          full_name: form.full_name || null,
          is_active: form.is_active,
          is_verified: form.is_verified,
          is_admin: form.is_admin,
        };
        // Only send password if the admin typed one — an empty input
        // means "leave it unchanged", which is what they usually want
        // when they're just flipping a permission bit.
        if (form.password) payload.password = form.password;
        const updated = await updateUser(user.id, payload);
        toast.success(`Updated ${updated.email}`);
        await onSaved(updated);
      }
    } catch (err: any) {
      setFormError(err?.message || 'Could not save user');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === 'create' ? 'Create user' : 'Edit user'}</DialogTitle>
          <DialogDescription>
            {mode === 'create'
              ? 'Admin-created accounts are auto-verified — the user can sign in immediately.'
              : 'Leave the password blank to keep it unchanged.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <FieldRow
            label="Email"
            required
            input={
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                autoComplete="off"
              />
            }
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldRow
              label="Username"
              input={
                <Input
                  value={form.username}
                  onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  autoComplete="off"
                />
              }
            />
            <FieldRow
              label="Full name"
              input={
                <Input
                  value={form.full_name}
                  onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  autoComplete="off"
                />
              }
            />
          </div>
          <FieldRow
            label="Password"
            hint={
              mode === 'edit'
                ? `Leave blank to keep current. New password: ${PASSWORD_MIN_LENGTH}+ chars, letter + number.`
                : `At least ${PASSWORD_MIN_LENGTH} characters with a letter and a number.`
            }
            input={
              <Input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                autoComplete="new-password"
              />
            }
          />
          {pwdIssues.length > 0 && (
            <ul className="space-y-1 rounded-md border border-destructive/30 bg-destructive/5 p-2.5 text-xs text-destructive">
              {pwdIssues.map((issue) => (
                <li key={issue} className="flex items-center gap-1.5">
                  <X className="h-3 w-3" />
                  {issue}
                </li>
              ))}
            </ul>
          )}

          <div className="grid gap-2 sm:grid-cols-3">
            <ToggleRow
              label="Admin"
              description="Can access the admin panel"
              checked={form.is_admin}
              onChange={(v) => setForm((f) => ({ ...f, is_admin: v }))}
            />
            <ToggleRow
              label="Active"
              description="Can sign in"
              checked={form.is_active}
              onChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
            />
            <ToggleRow
              label="Verified"
              description="Skip email verification"
              checked={form.is_verified}
              onChange={(v) => setForm((f) => ({ ...f, is_verified: v }))}
            />
          </div>
        </div>

        {formError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
            {formError}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === 'create' ? 'Create user' : 'Save changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FieldRow({
  label,
  hint,
  required,
  input,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  input: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="flex items-center gap-1">
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {input}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2 rounded-md border border-border bg-background p-2.5 transition-colors hover:bg-muted/40">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring focus:ring-offset-2"
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-foreground">{label}</span>
        <span className="block text-xs text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation — typed-email guard. We don't reuse
// UserFormDialog because the only field here is a confirmation
// string, and a different title/description keeps the destructive
// intent unmistakable.

function DeleteUserDialog({
  user,
  onClose,
  onDeleted,
}: {
  user: User | null;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [confirmEmail, setConfirmEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    if (user) {
      setConfirmEmail('');
      setFormError('');
    }
  }, [user]);

  if (!user) return null;
  const canDelete = confirmEmail.trim() === (user.email || '').trim() && !submitting;

  const submit = async () => {
    setFormError('');
    setSubmitting(true);
    try {
      await deleteUser(user.id);
      toast.success(`Deleted ${user.email}`);
      onDeleted(user.id);
    } catch (err: any) {
      setFormError(err?.message || 'Could not delete user');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Delete user
          </DialogTitle>
          <DialogDescription>
            This will permanently remove <strong>{user.email}</strong> and all of
            their chats, messages, and API keys. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <Label>
            Type <span className="font-mono text-destructive">{user.email}</span> to confirm
          </Label>
          <Input
            value={confirmEmail}
            onChange={(e) => setConfirmEmail(e.target.value)}
            autoComplete="off"
            autoFocus
            placeholder={user.email || ''}
          />
        </div>

        {formError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
            {formError}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={submit}
            disabled={!canDelete}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Delete user
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
