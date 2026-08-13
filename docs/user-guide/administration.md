# Managing accounts

The only page in this guide that is not about genealogy data. It covers the one
administrative tool in the set, which needs an owner or admin account to do
anything at all.

`manage_users` is the one administrative tool in the set. It exists because
opening a tree to a family means creating accounts one web form at a time, and
a batch of thirty is a tedious afternoon:

```
manage_users(action="list")
manage_users(action="get", name="jdupont")
manage_users(action="create",
             users=[{"name": "jdupont",
                     "email": "j.dupont@example.org",
                     "full_name": "Jeanne Dupont",
                     "role": "contributor"}])
```

`action` is `list`, `get` or `create`; `get` needs a `name`, and `create` needs
`users`, up to fifty per call. Each entry needs `name` and `email`; `full_name`
is optional and `role` defaults to `member`. The four roles it will grant are
`guest`, `member`, `contributor` and `editor` - owner and admin are refused by
design, so this tool cannot escalate anyone to its own level. The account in
your `.env` must itself be owner or admin, or every action returns a permission
error.

There is no update, no delete and no password reset: correcting a role or
retiring an account is Gramps Web UI work. The password generated for each new
account is printed in the tool result, which means it lands in the session
transcript - treat those as first-login credentials and have people change
them.

[User management](../user-management.md) covers the roles, the batch behaviour
and the failure modes in full.
