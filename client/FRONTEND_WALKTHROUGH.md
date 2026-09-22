# catch-a-scammer — frontend walkthrough

This document explains every file in the game client **by following one frame
through the code**, then one full player action end to end. If you read it top
to bottom, you'll understand not just what each file is but *when it runs* and
*why it hands off to the next one*.

Nothing here touches the database or the Python API — this is the client only.

- **19 files, ~3,500 lines, C++17 + raylib.**
- The client holds no game data and no answer key. It draws whatever the API
  returns and sends the player's actions back.

---

## The one-paragraph version

`main.cpp` opens a window and runs a loop 60 times a second. Every pass, it
calls `Desktop::Update()` (handle input, move windows, drain queued work) and
`Desktop::Draw()` (paint everything). `Desktop` is the fake operating system:
it owns the seven **apps** and the **Session**. Apps never talk to each other
or to the network directly — they read and write the `Session`, and the
`Session` is what actually calls the API over HTTP. That indirection is the
whole architecture.

```
main.cpp  ──drives──▶  Desktop  ──owns──▶  Apps  (7 windows)
                          │                  │
                          └──owns──▶  Session ◀──all apps read/write this
                                         │
                                         └──uses──▶  net::http  ──▶  API
```

---

## Part 1 — the files, grouped by their job

### The entry point

**`main.cpp`** (109 lines)
The only file with a `main()`. It:

1. Parses command-line flags (`--api`, `--player`, `--fullscreen`).
2. Calls `net::GlobalInit()` to start the networking library.
3. Opens the raylib window (1440×900, resizable, vsync on).
4. Loads fonts.
5. Constructs one `Desktop`, which constructs everything else.
6. Runs **the game loop** until the window closes or the player picks Shut
   Down.
7. Tears fonts, the window, and networking down on the way out.

The loop itself is tiny — this is the heart of the whole program:

```cpp
while (!WindowShouldClose() && !desktop.wantsQuit()) {
    float dt = GetFrameTime();        // seconds since last frame
    desktop.Update(dt);               // input + logic
    BeginDrawing();
        ClearBackground(...);
        desktop.Draw();               // paint
    EndDrawing();
}
```

Everything else in this document is what happens *inside* those two calls.

---

### The networking layer

**`net/http.h` / `http.cpp`** (43 + 112 lines)
A thin wrapper over libcurl. Exposes `Get`, `Post`, `Delete`, and URL
building. Two things here matter for the loop:

- **`net::Async`** — one in-flight request. You call `start()` with a function
  that does the HTTP call; it runs on a background thread. Every frame you ask
  `ready()`, and once it's true you `take()` the result. **This is why the game
  never freezes while waiting on the server** — the request runs off to the
  side and the loop keeps drawing at 60fps.
- `Response::ok()` tells you the call succeeded (2xx status, no transport
  error).

You rarely touch this file directly. The `Session` and the `Finder` use it for
you.

---

### The game state

**`core/session.h` / `session.cpp`** (79 + 189 lines)
**The single most important file to understand.** `Session` is the one object
every app shares. It holds:

- **configuration** — `apiBase`, `playerName`
- **the current case** — `caseId`, `brief` (the JSON briefing), `evidence`
  (what's been pinned), `lastHint`
- **connection status** — `online`, `offlineReason`
- **the toast list** — the little notification popups
- **the open-request queue** — explained below
- **the async operations** — `startNewCase`, `refreshBrief`,
  `refreshEvidence`, `pinEvidence`, `unpinEvidence`, `pingHealth`

Its own `Update(float dt)` runs once per frame (the desktop calls it) and does
two things: expires old toasts, and polls its in-flight requests so that when,
say, `startNewCase` finishes, `caseId` and `brief` update.

**The open-request queue** is the mechanism that lets apps stay independent.
When IntelSearch wants to open the malware database, it can't — it doesn't know
windows exist. So it calls:

```cpp
session.requestOpen("malwaredb", "ExampleStealer");
```

That just pushes an `OpenRequest` onto a list. Next frame, the `Desktop` drains
the list and opens the window. No app ever references another app.

The JSON helpers at the top (`jstr`, `jint`, `jbool`) are safe accessors — the
API is allowed to omit optional fields, so these return a default instead of
crashing.

---

### The look

**`core/theme.h` / `theme.cpp`** (72 + 118 lines)
All colors, fonts, and fixed measurements (title bar height, taskbar height,
padding). Also the *brand* strings — `SLEUTHOS`, version `7.1`. Change those two
strings and the entire OS re-brands, because nothing else hardcodes the name.

`theme.cpp` also owns the three fonts and the text-drawing/measuring helpers
(`Text`, `TextW`, `TextWrapped`) that everything else uses. It's a pure leaf:
it depends on nothing, and nearly everything depends on it.

---

### The widget toolkit

**`ui/widgets.h` / `widgets.cpp`** (65 + 300 lines)
A small **immediate-mode** UI kit. "Immediate mode" means a widget draws itself
*and* handles its own input in a single function call, every frame — there are
no widget objects sitting in memory. `ui::Button(rect, "NEW CASE")` returns
`true` on the frame it's clicked. That's it.

What's in here: `Button`, `TinyButton`, `Checkbox`, `TextField`, `Combo`
(dropdown), `Scroll` (scrolling regions), `Row`, `Badge`, `Panel`, `Spinner`,
and dividers/labels.

Two details that matter for the loop:

- **`SetEnabled` / `Enabled`** — input is globally gated. The desktop enables
  widgets only for the focused window, so clicks never "bleed through" to a
  window behind the one you're using.
- **`DeferPopup` / `FlushPopups`** — an open dropdown must paint *above* the
  rest of its window. Widgets queue that painting here, and the desktop flushes
  it after the window's normal content is drawn.

---

### The app interface

**`apps/app.h`** (36 lines)
The contract every window implements. Seven methods: `Id`, `Title`, `Glyph`,
`Accent`, `DefaultSize`, `OnOpen`, `Draw`. The shell owns exactly one instance
of each app, so its state (search text, scroll position, last result) survives
minimizing and reopening — like a real desktop program.

The two methods that run during play:

- **`OnOpen(session, query)`** — called when the window is opened or raised,
  optionally with a query handed over from another app.
- **`Draw(session, contentRect, active)`** — called every frame the window is
  visible. Draws the window's insides and handles its input.

**`apps/factories.h` / `registry.cpp`** (12 + 17 lines)
`registry.cpp` is literally the list of which apps exist. `MakeApps()` returns
them in order. The desktop icon, taskbar button, start-menu row and `Ctrl+N`
shortcut for each app are all generated from this list — add a line here and a
new app appears everywhere automatically.

---

### The shared record renderers

**`apps/common.h` / `common.cpp`** (71 + 513 lines)
Four of the seven apps (IntelSearch, Web Search, Directory, MalwareDB) are
search-and-display tools that show the same *kinds* of record — a domain, an
IP, a malware family, an actor. Rather than each app re-implementing "draw a
domain card," those renderers live here once: `rec::Domain`, `rec::Ip`,
`rec::Malware`, `rec::Campaign`, `rec::Actor`, `rec::Person`, `rec::Article`.

Two pieces you'll see referenced everywhere:

- **`rec::Finder`** — bundles a search box + one in-flight request + the last
  result document. An app that searches owns a `Finder` and calls `Search`,
  `Fetch`, and `Poll(session)` each frame. This is where the `net::Async`
  polling actually lives for the lookup apps.
- **`rec::Action`** — a renderer never changes the session directly. When you
  click `[VIEW IP]` or `[ADD TO EVIDENCE]` on a card, the renderer fills in an
  `Action` (Pin / OpenApp / FetchUrl / OpenGraph) and returns it. The owning
  app calls `rec::Apply(session, action)`, which turns it into a
  `requestOpen`, a `pinEvidence`, etc. This keeps drawing and state-changing
  cleanly separated.

---

### The seven apps

**`apps/apps_case.cpp`** (466 lines) — **CaseDesk** and **Case Report**.
CaseDesk is the ticket: it shows the briefing, the NEW CASE / difficulty
controls, and the hint button. Case Report is the submission form — pick actor,
campaign, domain, malware, submit, see whether you were right.

**`apps/apps_lookup.cpp`** (199 lines) — **IntelSearch**, **Web Search**,
**Directory**, **MalwareDB**. Four apps, one file, because they're the same
shape: a search box driving a `Finder`, results drawn by the `rec::` renderers.
They differ only in which API path they hit and which record types they expect.

**`apps/apps_graph.cpp`** (498 lines) — **Evidence Map**. The relationship
graph. Pulls the case's discovered nodes and edges and draws them as a
clickable web, with noise edges styled differently. The most self-contained
app.

---

### The shell

**`os/desktop.h` / `desktop.cpp`** (59 + 536 lines)
The fake OS. Owns the `Session` and the seven apps. Owns a `vector<Win>` — one
window record per app (a rectangle plus flags: open, minimized, maximized,
dragging, resizing) — and a separate `vector<int> order_` giving front-to-back
z-order.

This is where `Update` and `Draw` (the two calls from `main`'s loop) actually
do their work. Detailed next.

---

## Part 2 — one frame, start to finish

Here is exactly what happens each of the 60 times per second the loop runs.

### `desktop.Update(dt)`

1. **Boot check.** For the first ~2 seconds the desktop shows a fake boot
   sequence and returns early. After that, normal operation.
2. **`session_.Update(dt)`** — the session expires old toasts and polls its own
   in-flight requests (new case, brief refresh, evidence, health).
3. **Health ping timer** — every 15 seconds it re-checks the API is alive, to
   flip the green/red dot.
4. **Drain the open-request queue** — for each `OpenRequest` the apps pushed
   last frame, open/raise that window. *(This is the indirection paying off.)*
5. **Keyboard shortcuts** — `F1` help, `Esc` closes the top overlay/window,
   `Ctrl+1..7` open apps, `Alt+Tab` cycles windows, `Ctrl+Q` quits.
6. **Start menu / taskbar / desktop icons** — handle clicks: open apps,
   minimize, restore, raise.
7. **Window chrome** — for the focused window: title-bar buttons (close /
   maximize / minimize), title-bar dragging, and the resize grip.

At this point all state for the frame is settled. Nothing has been drawn yet.

### `desktop.Draw()`

Painted back to front, so nearer things cover farther ones:

1. **Wallpaper** — gradient, faint grid, the `SLEUTHOS 7.1` watermark.
2. **Desktop icons** — one per app, generated from the registry.
3. **Windows** — walks `order_` front to back. For each open, non-minimized
   window: shadow, title bar, body, border, title-bar buttons, then the app's
   own `Draw(session, contentRect, active)` **clipped to the content
   rectangle** so it physically cannot paint outside its frame. Input is
   enabled only for the active window here.
4. **Taskbar** — start button, one button per open window, the case code, and
   the online/offline dot.
5. **Start menu**, **toasts**, **help overlay** — the top layers, if visible.

Then `EndDrawing()` shows the frame, and the loop comes back around.

---

## Part 3 — one full player action, end to end

Follow **"the player looks up a domain in IntelSearch and pins it"** through
every file. This is the whole architecture in one trace.

1. **Player types a domain and presses Enter.**
   Inside IntelSearch's `Draw` (`apps_lookup.cpp`), the `ui::TextFieldW` widget
   (`widgets.cpp`) returns `true` on the Enter press.

2. **The app starts a search.**
   IntelSearch calls its `Finder::Search(session, "/api/intel", query)`
   (`common.cpp`). `Finder` builds the URL via the `Session` and kicks off a
   `net::Async` request (`http.cpp`) on a background thread. **The loop keeps
   running at 60fps** — the window shows a spinner, nothing blocks.

3. **The result arrives (a few frames later).**
   Each frame, IntelSearch calls `Finder::Poll(session)`. Once the async
   request is `ready()`, `Poll` takes the JSON response and stores it as the
   Finder's `result`.

4. **The result is drawn.**
   IntelSearch passes `result` to `rec::Envelope` (`common.cpp`), which calls
   `rec::Domain`, `rec::Ip`, etc. to draw each card. These come out styled by
   `theme.cpp` and built from `widgets.cpp` pieces.

5. **Player clicks `[ADD TO EVIDENCE]`.**
   `rec::PinButton` doesn't change anything itself — it fills in a
   `rec::Action{ kind = Pin, entityKind = "domain", entityId = 41, ... }` and
   returns it.

6. **The app applies the action.**
   IntelSearch calls `rec::Apply(session, action)`, which calls
   `session.pinEvidence("domain", 41, label)`.

7. **The session calls the API.**
   `Session::pinEvidence` (`session.cpp`) fires a `net::Post` to
   `/api/cases/{id}/evidence` and, on success, refreshes the evidence list and
   raises a toast: "Added to evidence."

8. **Next frame, the change is visible.**
   `Session::Update` polls the refresh, `evidence` now includes the domain,
   the toast is drawn by the desktop, and if the player clicks `[VIEW IP]` on
   that same card, step 1 begins again for the IP — via a `requestOpen` that
   the desktop drains at the top of the next `Update`.

Notice what never happened: no app touched the network, no app touched another
app, and no renderer touched the session. Every change flowed **app → Session →
network**, and every cross-app open flowed **app → requestOpen → Desktop**.
That discipline is what keeps 3,500 lines across 19 files from turning into a
tangle.

---

## Part 4 — quick reference

| File | Lines | Runs when | One-line job |
|---|---|---|---|
| `main.cpp` | 109 | startup + the loop | window, fonts, the 60fps loop |
| `net/http.*` | 155 | on every API call | libcurl wrapper + async requests |
| `core/session.*` | 268 | every frame | shared game state; the only thing that calls the API |
| `core/theme.*` | 190 | on every draw | colors, fonts, text, brand strings |
| `ui/widgets.*` | 365 | on every draw | buttons, fields, scrolls, combos |
| `apps/app.h` | 36 | — | the interface every window implements |
| `apps/common.*` | 584 | in the 4 lookup apps | shared record cards + Finder + Action |
| `apps/apps_case.cpp` | 466 | those windows open | CaseDesk + Case Report |
| `apps/apps_lookup.cpp` | 199 | those windows open | IntelSearch, WebSearch, Directory, MalwareDB |
| `apps/apps_graph.cpp` | 498 | that window open | Evidence Map |
| `apps/factories.h` + `registry.cpp` | 29 | startup | the list of apps that exist |
| `os/desktop.*` | 595 | every frame | the whole fake OS: windows, taskbar, Update/Draw |

**If you only remember three things:**

1. `main.cpp`'s loop calls `Desktop::Update` then `Desktop::Draw`, 60× a
   second.
2. Apps never talk to the network or to each other — they go through
   **`Session`** (for state/API) and **`requestOpen`** (to open another app).
3. Drawing is immediate-mode: a widget draws and reacts to input in the same
   call, so "handle input" and "paint" are the same line of code.
