# README #

This README would normally document whatever steps are necessary to get your application up and running.

### What is this repository for? ###

* Quick summary
* Version
* [Learn Markdown](https://bitbucket.org/tutorials/markdowndemo)

### How do I get set up? ###

* Summary of set up
* Configuration
* Dependencies
* Database configuration
* How to run tests
* Deployment instructions

### Contribution guidelines ###

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact

### User and session access

Authorization uses the authenticated user's current database role (`users.role_id`
joined to `user_roles`). USER can read only their own sessions. ADMIN and
SUPER_ADMIN can read other users' sessions. User listing and role changes require
SUPER_ADMIN. Missing or unknown roles grant no administrative access. Role changes
take effect on the next request, including for existing access tokens.

Set `ACCESS_TOKEN_SECRET` in each deployment to a persistent random secret of at
least 32 characters, shared by all workers. Do not commit it. It is separate from
`SECRET_KEY`, which verifies upstream login tokens. Token login now requires a
SECRET_KEY of at least 32 characters; coordinate that key with the upstream issuer.
Password login continues to use the existing external authentication service.

After login, send the returned `access_token` on every users/sessions request:
`Authorization: Bearer <access_token>`. Tokens expire after eight hours. Existing
clients must log in again and forward this header; user IDs alone no longer grant
access. The bundled login/chat UI forwards the token automatically. It clears the
browser token on logout; copied tokens remain valid until expiration (server-side
revocation is not implemented).

- `GET /sessions/`: paginated own sessions by default. `user_id` may specify the
  caller's own ID. Only ADMIN/SUPER_ADMIN callers can specify another user's ID or use
  `all_users=true` (do not combine these). Date/name filters and pagination apply
  inside the authorized scope, including the total count.
- `GET /sessions`: retains the legacy list response, scoped to the caller or an
  explicitly selected user for ADMIN/SUPER_ADMIN callers.
- `GET /sessions/{session_id}`: ordinary callers can only read their own sessions;
  missing or other-owner sessions return 404. ADMIN/SUPER_ADMIN callers may inspect any
  session. Optional `user_id` narrows that lookup.
- `GET /sessions/get_all/sessions/`: legacy all-session listing requires ADMIN or SUPER_ADMIN.
- `GET /sessions/saved/{user_id}`: own sessions, or another user's for ADMIN/SUPER_ADMIN callers.
- `GET /users` and `PUT /users/{user_id}/role`: SUPER_ADMIN only. The legacy
  `admin_user_id` parameter is optional; if sent, it must match the token's user ID.
- `POST /login/create`: requires SUPER_ADMIN because it accepts role assignments.
- Session creation checks the requested owner. Session deletion, save toggles,
  and message feedback require ownership; administrative read access does not grant
  permission to modify other users' conversations.

These changes protect the users/session routes; they are not an authentication
audit of unrelated chat, course, feedback, or login-management routes. No database
migration or data rewrite is needed.

Run isolated authorization tests (no database or external API calls):

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_access_control.py -q
```
