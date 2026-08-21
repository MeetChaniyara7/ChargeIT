# VoltPulse EV Charging Platform — Authentication System

A modern, high-performance web application built with **React**, **Vite**, **TypeScript**, and **Tailwind CSS**, featuring a robust user authentication system powered by **Supabase Auth**.

This codebase is architected to isolate authentication (managed via Supabase Auth) from business domain data (stations, connectors, reservations), preparing it seamlessly for direct connection to a **local PostgreSQL database** (managed via **DBeaver**) in Phase 2.

---

## 🚀 Tech Stack

- **Frontend Framework:** React 19 + Vite 6
- **Language:** TypeScript (Strict)
- **Styling:** Tailwind CSS v4 + Glassmorphism Dark Theme
- **Icons:** Lucide React
- **Authentication:** Supabase Auth (Free Tier)
- **Database (Phase 2):** Local PostgreSQL (Managed via DBeaver)

---

## 📁 Project Structure

```text
src/
├── components/
│   ├── LoginForm.tsx       # Centered glassmorphic sign-in form with validation
│   ├── RegisterForm.tsx    # Full name, email, password registration form
│   ├── ProtectedRoute.tsx  # Guard wrapper for authenticated routes + session loading
│   └── Navbar.tsx         # Responsive header with profile indicator & logout
├── pages/
│   ├── Home.tsx            # Public landing page with system status & features
│   ├── Login.tsx           # Login page (redirects to dashboard if logged in)
│   ├── Register.tsx        # Registration page (redirects to dashboard if logged in)
│   └── Dashboard.tsx       # Protected dashboard with profile info & local DB readiness
├── context/
│   └── AuthContext.tsx     # Session state management, sign up, login, logout hooks
├── lib/
│   └── supabase.ts         # Safe Supabase client initialization
├── types/
│   └── auth.ts             # TypeScript definitions for auth models & forms
├── App.tsx                 # Main router & provider wrapper
└── main.tsx                # React root entry point
```

---

## 🔐 Supabase Auth Setup Guide

Follow these steps to set up your free Supabase authentication backend:

### Step 1: Create a Free Supabase Account & Project
1. Go to [https://supabase.com/](https://supabase.com/) and click **Sign Up** or **Sign In**.
2. Click **New Project**.
3. Fill in your project details:
   - **Name:** `ev-charging-auth` (or any name of your choice)
   - **Database Password:** Enter a strong password (store this safely).
   - **Region:** Select the region closest to you.
   - **Pricing Plan:** Free tier.
4. Click **Create new project** and wait 1-2 minutes for provisioning.

### Step 2: Enable Email Authentication
1. In your Supabase Dashboard left sidebar, navigate to **Authentication** -> **Providers**.
2. Locate **Email** under Native Providers and click to edit.
3. Ensure **Enable Email provider** is toggled **ON**.
4. (Optional for development) Disable **Confirm email** if you want users to log in immediately upon registration without email verification links.
5. Click **Save**.

### Step 3: Retrieve API Credentials
1. In your Supabase Dashboard, go to **Project Settings** (gear icon at bottom left) -> **API**.
2. Copy the following credentials:
   - **Project URL** (under Project API keys / Configuration)
   - **anon / public key** (under Project API keys)

### Step 4: Configure Environment Variables
1. Open the project root directory.
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with your copied Supabase keys:
   ```env
   VITE_SUPABASE_URL=https://your-actual-project-id.supabase.co
   VITE_SUPABASE_ANON_KEY=your-actual-anon-key-here
   ```

---

## 💻 Running the Application

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
```bash
npm run dev
```

The application will launch locally at `http://localhost:5173`.

### 3. Verify Build & Type Checking
```bash
npm run build
```

---

## 🛢️ Note on Database Architecture (Phase 2 Local PostgreSQL)

> **Important:** Supabase is used **ONLY** for Authentication (User registration, Login, Logout, JWT Sessions).
> 
> The database for main business operations (**Charging Stations**, **Connectors**, **Reservations**, and **Payments**) will be connected in the next phase using a **Local PostgreSQL Database** managed via **DBeaver**.
> 
> The current codebase maintains clean separation in `AuthContext.tsx` and `Dashboard.tsx` to allow adding your local PostgreSQL API endpoints / ORM without touching the authentication layer.
