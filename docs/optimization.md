# Library, UI and resource optimization

Implemented in the `feat/library-resource-ui` working branch. Files remain local Markdown; SQLite is a rebuildable index. Existing notes are not automatically moved.

## Everyday workflow

- **Quick capture / Ctrl+N:** create a note in `notes/Inbox/`.
- **New / n:** create a note in the selected folder. Tags support suggestions and can be edited later through **More → Edit tags**.
- **Folders:** expand the tree to load a branch. Select a folder to browse it and optionally its descendants. **New** creates a subfolder; **Manage** renames, moves, or deletes an empty folder. Destinations are relative to `notes/` when moving folders.
- **More → Move to folder:** browse or search destination folders; create a destination from the same dialog. Journals remain in `journal/`.
- **Tags:** click to toggle filters; combine several tags to require all of them. Search and sort work inside the selected scope. **Filter** combines Notes/Journals/All types with comma-separated tags; **Clear** resets both.
- **Pinned:** keep important notes close. Search results retain relevance ranking.
- **Archive:** hide a note from ordinary lists without moving its file. Restore it through **More** in the Archive view.
- **Save:** changes save after one second of inactivity. `Ctrl+S` saves immediately. Save errors preserve the draft and block switching notes or quitting. An external edit offers explicit reload/overwrite choices.
- **Navigation:** `Ctrl+O` toggles folders/tags; `Ctrl+L` toggles the notes list. Layout defaults are recalculated on terminal resize.
- **Editing:** `e` enters Edit, `Ctrl+P`/F2 switches View/Edit, `Ctrl+W` requests Split, Escape returns to View, and `Ctrl+Q` saves and quits. Existing formatting shortcuts remain available.

CLI tables show the last 12 characters of long note IDs to keep titles readable. These fragments work with existing CLI identifier lookup; full IDs remain in Markdown metadata and `note add` output. New IDs use 64 random bits to avoid collisions during rapid capture/import. Plain Markdown files without IDs get distinct path-based identities; an app-initiated move persists that identity first. Duplicate explicit IDs are reported rather than silently replacing an existing index entry.

## Layout and motion

| Terminal width | Default layout |
|---|---|
| 140+ columns | Folders/tags (24), notes (32), workspace |
| 100–139 | Notes (28) and workspace; navigation opens as a drawer |
| Below 100 | Workspace; navigation and notes open as drawers |
| 160+ | Split editing and preview available |

The UI uses a shared Tokyo Night palette with distinct selection, focus, success, warning, and error states. The footer has stable controls instead of recreating reactive bindings on every focus change. All UI text is English; note content and Vietnamese IME support are preserved.

Motion lasts 100–180 ms: hover colors, focus borders, note/mode fades and navigation drawer transitions. Popups use their original centered layout, spacing, button style, and immediate open/close behavior. There are no continuous background animations. Plaintext is hidden immediately when relocking. Disable motion in the existing config file (`~/.config/noted/config.toml` on macOS/Linux, `~/.notes/config.toml` on Windows):

```toml
[ui]
animation = "off" # default: "subtle"
```

`NO_COLOR` remains respected. The preview capture command intentionally unsets it only for that subprocess.

## Resource controls

- Notes pages replace their previous 100 widgets. Tags use 30 entries per page. Folder branches load on demand and release descendants when collapsed.
- Only the active note's content and decrypted body are kept. Session passwords permit reopening without another prompt; relocking clears that note's password. Python does not guarantee secure erasure of freed strings.
- View clears the editor document and undo history; Edit clears Markdown blocks. Only Split keeps both representations. Undo is limited to 20 checkpoints.
- At 256 KiB UTF-8, live preview and syntax highlighting pause automatically. View renders at most the initial 256 KiB. **Render full note** is explicit and may require more resources. Editing/saving/copying retain the complete content.
- Search waits 150 ms; small-note live preview waits 200 ms. Replaced timers are stopped. Saves are synchronous and serialized; there is no background queue holding draft copies.
- Indexing runs in one worker, streams filesystem entries and database records, and commits every 200 changed notes. Repeated sync requests are coalesced, and shutdown cancels the scan between entries. It does not load all note bodies or all filesystem paths together.
- Markdown is authoritative. If disk saving succeeds but indexing fails, retrying Save repairs the index without discarding the persisted draft.

## Runtime evidence

Measurements use disposable notes and Textual's headless driver at 180×45 on macOS 27 arm64, Python 3.11.16, Textual 8.2.8. They measure the Python process, excluding the terminal emulator. The synthetic notes are small Markdown documents; a separate note is 1 MiB. They are not universal RAM limits for arbitrary documents.

See the committed JSON files in [performance/](performance/) for the original and optimized runs. Cold-index and startup times were recorded during other validation work and are informational rather than controlled speed comparisons. The debounce-inclusive search figure adds the configured delay to the measured SQL query time; it is not a measured end-to-end key-to-paint latency.

<!-- RESOURCE_RESULTS_START -->
| 10,000-note workload, subtle motion | Original | Optimized |
|---|---:|---:|
| Ready RSS | 69.67 MiB | 74.22 MiB |
| RSS after 200 open/Edit/View cycles | 243.47 MiB | 92.14 MiB |
| Peak RSS including 1 MiB note | 316.38 MiB | 116.91 MiB |
| Idle CPU over 60 seconds, one core | 2.504% | 0.000% |
| SQL search p95 | 16.29 ms | 28.71 ms |
| SQL p95 + configured debounce | n/a (original has no debounce) | 178.71 ms |
<!-- RESOURCE_RESULTS_END -->

The 600-cycle run retained roughly 300–350 widget objects rather than a growing sequence of removed footer controls. RSS still includes Python/Textual caches and allocator high-water effects; a constant RSS value is not promised. The full-render button can deliberately exceed the default preview budget.

Validation includes safe rename failures, external-file conflicts and snapshot races, encrypted relock/recovery, missing cached files at startup, nested plain Markdown identities, combined filters/paging, autosave under modals, resize with failed disk writes, stable footer controls, and overlapping page refreshes. A PTY smoke check opened the CLI/TUI, edited a disposable note, saved with Ctrl+S, exited with Ctrl+Q, and verified the file contents.

| macOS validation | Result |
|---|---|
| Python 3.10.21 | 102 tests passed |
| Python 3.11.16 | 102 tests passed |
| Python 3.12.14 | 102 tests passed |
| Wheel and source distribution | Built successfully; TUI CSS/palette included |
| PTY open/edit/save/quit | Passed; persisted content checked |
| UI previews | 60×20, 80×24, 100×30, 140×40, 180×45, Split and actions menu inspected |


Windows/Linux runtime and physical IME behavior were not tested on this macOS host. CI retains the existing three-OS Python matrix; it has not been run remotely or published in this task.

## Reproduce

```bash
uv sync --all-extras --dev
uv run note
uv run pytest -q

# macOS/Linux resource profile; never reads your personal notes
uv run python scripts/profile_resources.py \
  --notes 10000 --cycles 200 --idle-seconds 60 --output profile.json

# UI snapshots using temporary example notes
# Omit env -u NO_COLOR if you want monochrome snapshots.
env -u NO_COLOR uv run python scripts/capture_previews.py
```

Previews: [wide](previews/noted-180.svg), [compact](previews/noted-100.svg), [narrow](previews/noted-60.svg), [split](previews/noted-split.svg), [actions](previews/noted-actions.svg). These are generated from the actual widgets, not design mockups.
