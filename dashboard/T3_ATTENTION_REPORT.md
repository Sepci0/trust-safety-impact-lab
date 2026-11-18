# How T3 Code's sidebar runs "inbox zero" for agents

Source: `pingdotgg/t3code` (MIT), read at commit `b8b5affa` (2026-11-17). Main files:
`apps/web/src/components/Sidebar.logic.ts`, `Sidebar.tsx`, `ThreadStatusIndicators.tsx`,
`packages/client-runtime/src/state/threadInbox.ts`, `threadSettled.ts`, and the user doc
`docs/user/thread-sidebar.md`.

## The idea in one line

Every thread is an item in an inbox. Anything waiting on you jumps to the top of the list and gets a colored status pill. You clear the list by answering what it needs or by settling the item. Once you've seen finished work, it drops out of sight.

## 1. Status pills: one per row, the most urgent wins

`resolveThreadStatusPill()` returns **at most one** pill per thread. It checks the cases below in this fixed priority order and stops at the first match:

| # | Pill | Color (Tailwind) | Pulses? | Meaning |
|---|---|---|---|---|
| 1 | **Pending Approval** | amber-500 | no | The agent wants permission to run a tool or action |
| 2 | **Awaiting Input** | indigo-500 | no | The agent asked you a question |
| 3 | **Guest Request** | fuchsia-500 (the "pink" one) | no | Someone else sent a message into your thread |
| 4 | **Working** | sky-500 | yes | The agent is running |
| 5 | **Connecting** | sky-500 | yes | Preparing, queued or starting |
| 6 | **Waiting** | muted gray | no | Blocked on a subagent or background task |
| 7 | **Failed** | red-500 | no | The run failed, and you haven't seen it yet |
| 8 | **Plan Ready** | violet-500 | no | A plan is ready for you to review and accept |
| 9 | **Completed** | emerald-500 | no | Finished, and you haven't seen it yet |
| – | *(none)* | – | – | Idle and seen: the row goes quiet |

Details worth copying:
- **The pill is a dot plus a tiny label** (`h-1.5 w-1.5 rounded-full` dot, `text-3xs` label). The label hides on narrow layouts, and there is always a tooltip.
- **Only live work pulses.** States that are waiting on *you* hold steady, which keeps the pulse from becoming background noise.
- **"Unseen" matters.** Failed and Completed only show if they happened after your last visit (`hasUnseenRunFailure`, `hasUnseenCompletion`). Opening the thread clears them. That is the core zero-inbox move: looking at an item is what dismisses it.
- **Dark mode uses the 300 shade at 90% opacity** of the same hue (`dark:bg-amber-300/90`).

## 2. Sidebar sections

`resolveSidebarThreadSection()` puts every thread into one of five sections, top to bottom:

1. **Pinned**: threads you chose to keep in view.
2. **Active**: the inbox. When the Working shelf is on (the default), it is sorted by **when each thread last came back to you** (`sortInboxThreadsByReturn`: the latest of created, un-settled, run requested, run completed). A thread that just finished, failed or started asking for approval jumps to the top.
3. **Working** (collapsed): threads still running. They stay out of the way until they return, so the Active list holds only things that need you.
4. **Snoozed** (collapsed): hidden until a wake time. A snoozed thread **wakes early** only for an approval, a question or a failure (`threadRaisedHandWhileSnoozed`). Finishing normally does not wake it.
5. **Settled** (collapsed shelf): finished work, sorted by when it settled.

## 3. How items leave the inbox

- **Settle** (manual, from the menu or by dragging onto the Settled header) moves an item onto the shelf. **Un-settle** puts it back at the top.
- **Auto-settle**: threads settle on their own after 7 days of inactivity or when their PR merges. Anything with a pending approval or question is never auto-settled.
- **Undo toast** for 5 seconds after settle, snooze, unpin or archive. `mod+z` triggers it.
- Section changes **animate**, and the animation respects reduced-motion settings.

## 4. Grouping by folder ("Boring sidebar")

With project folders turned on, a **closed folder shows a count and a single dot** for the most urgent state inside it (`resolveSidebarFolderDot`). The order is attention (approval, input, request, limited), then failed, then unread, then working. You can see that a folder needs you without opening it.

## 5. Other attention channels

The window title reports the open thread's state: "Pending approval", "Awaiting input" or "Working". There is also a notification coordinator for background threads.

## What we're copying into the email dashboard

| T3 Code | Our dashboard |
|---|---|
| Project folders | **Email categories** (each shows a count and the most urgent dot) |
| Active inbox sorted by return time | **Needs you** at the top of the sidebar, newest first, across all categories |
| Pending Approval (amber) | The agent wants to act on an email (send, forward, pay): **Approve / Reject** |
| Guest Request (fuchsia) | **Review**: a stranger's email was quarantined as a likely injection |
| Failed (red) | **Blocked**: the injection was stripped or blocked, and you haven't seen it yet |
| Working (sky, pulsing) | **Scanning**: the email arrived and the firewall is still deciding |
| Completed (emerald, unseen) | **Cleared**: allowed automatically, and you haven't seen it yet |
| Settled shelf | **Done**: items you approved or rejected |
| Window title status | `(N) Mail Guard`, where N is the number of items that need you |
