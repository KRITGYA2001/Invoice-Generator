# Accounts App

## Purpose

Handles user registration, login, logout, profile editing, and password management. Provides the custom `User` model used throughout the project.

## Model: `User`

Custom model extending `AbstractBaseUser` + `PermissionsMixin`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | Auto-generated |
| `email` | EmailField (unique) | Used as `USERNAME_FIELD` for login |
| `first_name` | CharField(150) | Required |
| `last_name` | CharField(150) | Required |
| `phone` | CharField(20) | Optional |
| `is_active` | BooleanField | Default True |
| `is_staff` | BooleanField | Django admin access |
| `date_joined` | DateTimeField | Auto set on create |
| `updated_at` | DateTimeField | Auto updated |

`REQUIRED_FIELDS = ["first_name", "last_name"]`

Custom `UserManager` handles `create_user()` and `create_superuser()`.

## Authentication Flow

### Registration
1. User visits `/accounts/register/`
2. Fills: email, first_name, last_name, password, confirm_password
3. `RegisterView` validates:
   - Email uniqueness
   - Password strength: min 8 chars, at least one uppercase, at least one digit
4. Creates `User`, logs them in
5. Redirects to `/company/onboarding/` (company setup)

### Login
1. User visits `/accounts/login/`
2. Submits email + password
3. `LoginView` authenticates, creates session
4. Remember-me option extends session expiry
5. Redirects to `/` (dashboard)

### Logout
- POST to `/accounts/logout/` → clears session → redirects to `/accounts/login/`

## UI Views (`views_ui.py`)

| View | URL | Method | Description |
|---|---|---|---|
| `LoginView` | `/accounts/login/` | GET/POST | Email/password login form |
| `LogoutView` | `/accounts/logout/` | POST | Session logout |
| `RegisterView` | `/accounts/register/` | GET/POST | New account creation |
| `ProfileView` | `/accounts/profile/` | GET/POST | Edit name, phone |
| `ChangePasswordView` | `/accounts/change-password/` | GET/POST | Old → new password change |

## URL Namespace: `accounts_ui`

```
accounts_ui:login
accounts_ui:logout
accounts_ui:register
accounts_ui:profile
accounts_ui:change-password
```

## Key Helpers

- `_password_strength_error(password)` → returns error string or `None`
- `_company_onboarding_url()` → returns the onboarding redirect URL

## Notes for Agents

- There is no email verification step — registration is immediate.
- `request.user.company_profile` is the standard way to access the current user's company in all views. This will raise `RelatedObjectDoesNotExist` if the user hasn't completed onboarding — the `OnboardingCheckMixin` in `core` guards against this.
- `settings.AUTH_USER_MODEL = "accounts.User"` — always use `get_user_model()` when referencing the user model in other apps.
