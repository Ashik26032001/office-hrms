"""
rule_engine.py
==============
Smart rule-based fallback that answers questions from the DB context
when Ollama is not available.  Covers every documented question pattern.
"""

import re


def _lower(text):
    return text.lower()


def answer(question: str, ctx: dict) -> str:
    """Return a markdown-ready answer string from the context dict."""
    q = _lower(question)
    role = ctx.get('role', 'employee')

    # ── SHARED ──────────────────────────────────────────────────────────────

    if any(w in q for w in ['hello', 'hi ', 'hey', 'greet']):
        name = ctx.get('name', 'there')
        return f"Hello **{name}**! 👋 I'm SmartHR AI. How can I help you today?"

    if any(w in q for w in ['help', 'what can you', 'what do you']):
        if role == 'employee':
            return (
                "I can help you with:\n"
                "- 📅 Attendance — *How many days did I attend this month?*\n"
                "- ✅ Tasks — *What tasks are pending for me?*\n"
                "- 📋 Meetings — *When is my next meeting?*\n"
                "- 📊 Work progress — *Show my project summary*\n"
                "- 🕐 Check-in status — *Am I checked in today?*"
            )
        else:
            return (
                "I can help you with:\n"
                "- 👥 Attendance — *How many employees are present today?*\n"
                "- ⚠️ Late arrivals — *Which employees have frequent late arrivals?*\n"
                "- 📋 Tasks — *Who has pending tasks?*\n"
                "- 🗂️ Projects — *Which projects are delayed?*\n"
                "- 📅 Meetings — *What meetings are scheduled this week?*\n"
                "- 🏢 Departments — *Show department-wise attendance*"
            )

    # ── EMPLOYEE QUERIES ────────────────────────────────────────────────────

    if role == 'employee':
        att = ctx.get('attendance', {})
        tasks = ctx.get('tasks', {})
        meetings = ctx.get('meetings', {})

        # Attendance queries
        if any(w in q for w in ['attend', 'present', 'absent', 'days this month', 'how many days']):
            present = att.get('days_present_this_month', 0)
            absent  = att.get('days_absent_this_month', 0)
            working = att.get('working_days_so_far', 0)
            pct     = att.get('attendance_percent', 0)
            last7   = ctx.get('last_7_days', [])
            week_summary = ', '.join(
                f"{'✅' if d['present'] else '❌'} {d['date']}" for d in last7
            )
            return (
                f"**Your Attendance This Month:**\n\n"
                f"- 📅 Present: **{present}** days\n"
                f"- ❌ Absent: **{absent}** days\n"
                f"- 🗓️ Working days so far: **{working}**\n"
                f"- 📊 Attendance rate: **{pct}%**\n\n"
                f"**Last 7 Days:**\n{week_summary}"
            )

        if any(w in q for w in ['check', 'in today', 'checked in', 'status today', 'am i in']):
            status = ctx.get('today_status', 'NOT CHECKED IN')
            checkin = ctx.get('today_checkin')
            if status == 'IN':
                return f"✅ Yes, you are **checked in** today. First check-in at **{checkin}**."
            else:
                return "❌ You have **not checked in** today. Please scan your QR code at the office."

        # Task queries
        if any(w in q for w in ['task', 'pending', 'todo', 'work', 'progress']):
            total   = tasks.get('total', 0)
            pending = tasks.get('pending', 0)
            todo    = tasks.get('todo', 0)
            open_   = tasks.get('open', 0)
            review  = tasks.get('under_review', 0)
            done    = tasks.get('done', 0)
            overdue = tasks.get('overdue', 0)
            next_t  = ctx.get('next_task_deadline')

            resp = (
                f"**Your Tasks:**\n\n"
                f"- 🔵 To Do: **{todo}**\n"
                f"- 🟡 Open: **{open_}**\n"
                f"- 🟠 Under Review: **{review}**\n"
                f"- ✅ Done: **{done}**\n"
                f"- ⚠️ Overdue: **{overdue}**\n\n"
                f"You have **{pending}** pending task{'s' if pending != 1 else ''} out of {total} total."
            )
            if next_t:
                resp += (
                    f"\n\n📌 **Nearest deadline:** \"{next_t['title']}\" "
                    f"({next_t['deadline']}) — in project *{next_t['project']}*"
                )
            return resp

        # Meeting queries
        if any(w in q for w in ['meeting', 'schedule', 'next meet', 'upcoming meet']):
            count = meetings.get('upcoming_count', 0)
            nxt   = meetings.get('next')
            if count == 0:
                return "📅 You have **no upcoming meetings** scheduled. HR will notify you when one is set."
            resp = f"📅 You have **{count}** upcoming meeting{'s' if count != 1 else ''}.\n\n"
            if nxt:
                resp += (
                    f"**Next Meeting:**\n"
                    f"- 📌 Title: **{nxt['title']}**\n"
                    f"- 🕐 Time: **{nxt['time']}**\n"
                    f"- 🔗 Link: {nxt['link']}"
                )
            return resp

        # Project queries
        if any(w in q for w in ['project', 'accuracy', 'summary']):
            projects = ctx.get('projects', [])
            if not projects:
                return "🗂️ You are not assigned to any active projects currently."
            lines = ["**Your Projects:**\n"]
            for p in projects:
                lines.append(
                    f"- **{p['name']}** — {p['done']}/{p['tasks']} tasks done, "
                    f"On-Time Accuracy: **{p['accuracy']}%**"
                )
            return '\n'.join(lines)

        # Notification queries
        if any(w in q for w in ['notification', 'unread', 'alert']):
            count = ctx.get('unread_notifications', 0)
            if count == 0:
                return "🔔 You have **no unread notifications**. All caught up!"
            return f"🔔 You have **{count} unread notification{'s' if count != 1 else ''}**. Check the bell icon in the top bar."

        # Joining / profile
        if any(w in q for w in ['join', 'joining date', 'profile', 'department', 'designation']):
            return (
                f"**Your Profile:**\n\n"
                f"- 🏢 Department: **{ctx.get('department', '—')}**\n"
                f"- 💼 Designation: **{ctx.get('designation', '—')}**\n"
                f"- 🆔 Employee ID: **{ctx.get('employee_id', '—')}**\n"
                f"- 📅 Joining Date: **{ctx.get('joining_date', '—')}**"
            )

    # ── HR / ADMIN QUERIES ──────────────────────────────────────────────────

    else:
        today_att  = ctx.get('today_attendance', {})
        all_tasks  = ctx.get('all_tasks', {})
        all_proj   = ctx.get('all_projects', {})

        # Attendance today
        if any(w in q for w in ['present today', 'attendance today', 'how many employee', 'who is in']):
            present  = today_att.get('present', 0)
            absent   = today_att.get('absent', 0)
            rate     = today_att.get('rate', 0)
            total    = ctx.get('total_employees', 0)
            dept_lines = '\n'.join(
                f"  - {d['dept']}: {d['present']}/{d['total']} present"
                for d in ctx.get('departments', [])
            )
            return (
                f"**Today's Attendance ({ctx.get('today', '')}):**\n\n"
                f"- ✅ Present: **{present}** / {total}\n"
                f"- ❌ Absent: **{absent}**\n"
                f"- 📊 Rate: **{rate}%**\n"
                f"- ⚠️ Late arrivals: **{ctx.get('late_arrivals_today', 0)}**\n\n"
                f"**Department Breakdown:**\n{dept_lines}"
            )

        # Late arrivals
        if any(w in q for w in ['late', 'tardy', 'late arrival']):
            today_late = ctx.get('late_arrivals_today', 0)
            freq_late  = ctx.get('frequent_late_employees', [])
            resp = f"⚠️ **Late arrivals today:** {today_late}\n\n"
            if freq_late:
                resp += "**Frequently late this month (3+ days):**\n"
                for e in freq_late:
                    resp += f"- {e['name']}: **{e['late_days']} late days**\n"
            else:
                resp += "No employees with 3+ late arrivals this month. 🎉"
            return resp

        # Department
        if any(w in q for w in ['department', 'dept', 'team']):
            depts = ctx.get('departments', [])
            if not depts:
                return "No department data found."
            lines = ["**Department-wise Attendance Today:**\n"]
            for d in depts:
                pct = round(d['present'] / max(d['total'], 1) * 100)
                lines.append(f"- **{d['dept']}**: {d['present']}/{d['total']} present ({pct}%)")
            return '\n'.join(lines)

        # Tasks / pending
        if any(w in q for w in ['task', 'pending', 'todo', 'overdue']):
            total   = all_tasks.get('total', 0)
            todo    = all_tasks.get('todo', 0)
            open_   = all_tasks.get('open', 0)
            review  = all_tasks.get('under_review', 0)
            done    = all_tasks.get('done', 0)
            overdue = all_tasks.get('overdue', 0)
            emp_p   = ctx.get('employees_with_pending_tasks', [])

            resp = (
                f"**All Tasks Overview:**\n\n"
                f"- 🔵 To Do: **{todo}**\n"
                f"- 🟡 Open: **{open_}**\n"
                f"- 🟠 Under Review: **{review}**\n"
                f"- ✅ Done: **{done}**\n"
                f"- ⚠️ Overdue: **{overdue}**\n\n"
                f"**Total tasks:** {total}"
            )
            if emp_p:
                resp += "\n\n**Employees with pending tasks:**\n"
                for e in emp_p[:10]:
                    resp += f"- {e['name']}: **{e['pending']} pending**\n"
            return resp

        # Projects / delayed
        if any(w in q for w in ['project', 'delayed', 'behind', 'progress']):
            total   = all_proj.get('total', 0)
            active  = all_proj.get('active', 0)
            delayed = ctx.get('delayed_projects', [])
            resp = (
                f"**Projects:**\n\n"
                f"- 🗂️ Total: **{total}**\n"
                f"- ✅ Active: **{active}**\n"
                f"- ⚠️ Delayed: **{len(delayed)}**"
            )
            if delayed:
                resp += "\n\n**Delayed projects:**\n" + '\n'.join(f"- ❌ {p}" for p in delayed)
            return resp

        # Meetings
        if any(w in q for w in ['meeting', 'schedule', 'upcoming']):
            meetings = ctx.get('upcoming_meetings', [])
            if not meetings:
                return "📅 No upcoming meetings scheduled."
            lines = ["**Upcoming Meetings:**\n"]
            for m in meetings:
                lines.append(f"- **{m['title']}** — {m['time']} ({m['attendees']} attendees)")
            return '\n'.join(lines)

        # Employee count
        if any(w in q for w in ['how many employee', 'total employee', 'staff count', 'headcount']):
            return f"👥 There are **{ctx.get('total_employees', 0)} active employees** in the system."

        # Monthly report
        if any(w in q for w in ['monthly', 'this month', 'month report']):
            return (
                f"**This Month Summary:**\n\n"
                f"- 👥 Active Employees: **{ctx.get('total_employees', 0)}**\n"
                f"- 📅 Attendance Events: **{ctx.get('this_month', {}).get('attendance_events', 0)}**\n"
                f"- ✅ Tasks Done: **{all_tasks.get('done', 0)}**\n"
                f"- ⚠️ Overdue Tasks: **{all_tasks.get('overdue', 0)}**\n"
                f"- ⚠️ Late Arrivals Today: **{ctx.get('late_arrivals_today', 0)}**"
            )

    # ── Fallback ─────────────────────────────────────────────────────────────
    return (
        "I'm not sure how to answer that from your current data. "
        "Try asking about attendance, tasks, meetings, or projects. "
        "Type **help** to see example questions."
    )
