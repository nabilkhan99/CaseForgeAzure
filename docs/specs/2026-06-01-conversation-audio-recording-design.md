# Conversation Audio Recording — Design

**Date:** 2026-06-01
**Component:** CaseForgeAzure / clinical_master (LiveKit voice agent)
**Status:** Implemented (code + unit tests) + Supabase migration/bucket applied —
pending S3 keys, Container App env, Egress-enabled check, and a live smoke test

## Goal

Store the full audio of each Clinical Master consultation (both the trainee/doctor
and the AI patient) for **internal use** (QA, debugging the voice pipeline,
evaluating STT/TTS quality, improving patient realism, auditing feedback).

## Decisions

- **One mixed audio file** per session (both voices combined), not separate tracks.
- **Stored in Supabase Storage** (S3-compatible), keyed by `session_id`, alongside
  existing session data.
- **Recorded via LiveKit Cloud Room Composite Egress** (audio-only) — server-side,
  uploads directly to the bucket. No audio passes through the agent container.

## Chosen approach (Approach A)

LiveKit Cloud's managed Egress records the room and writes a single audio-only
`.ogg` straight to Supabase Storage. The agent makes one fire-and-forget API call
to start it.

Rejected alternatives:
- **B — agent-side capture/upload:** fragile (agent is killed ~10s after session
  close), more code, audio flows through the container.
- **C — per-participant track egress + mix:** unnecessary; we want a single mixed file.

## Architecture & flow

```
session.start()  →  agent calls start_session_recording()
                         │
                         ├─ livekit.api.LiveKitAPI().egress.start_room_composite_egress(
                         │     RoomCompositeEgressRequest(
                         │       room_name=ctx.room.name,
                         │       audio_only=True,
                         │       file_outputs=[EncodedFileOutput(
                         │         file_type=EncodedFileType.OGG,
                         │         filepath="recordings/{session_id}.ogg",
                         │         s3=S3Upload(bucket, region, access_key, secret,
                         │                     endpoint=<supabase s3>, force_path_style=True))]))
                         │
                         ├─ returns egress_id; filepath is deterministic
                         └─ save_recording_path(session_id, path, egress_id)

LiveKit Cloud Egress records both voices (mixed) → uploads .ogg to Supabase Storage
Consultation ends (hang-up / end_consultation tool / timer) → session "close" event
  → on_close → stop_session_recording(egress_id) → egress finalizes & uploads .ogg
  (a job shutdown callback is registered only as a backstop)
```

> **Correction (was wrong in v1 and v2):** v1 assumed egress auto-stops when the
> room empties (it doesn't — the room lingers ~300s with participants). v2 stopped
> it via a job shutdown callback — also too late: shutdown callbacks fire only
> *after* the job shuts down, which itself waits for the room to close
> (`job_proc_lazy_main.py`). v3 stops the egress in the session `on_close` handler,
> which fires promptly on consultation end. See "Root cause" below.

## Components (files)

- **`clinical_master/recording.py`** *(new, ~60 lines)* —
  `async start_session_recording(room_name, session_id) -> tuple[str, str] | None`.
  Builds the egress request, calls the LiveKit API, handles all errors internally
  (returns `None` on any failure). Closes the `LiveKitAPI` client.
- **`clinical_master/agent.py`** — in `entrypoint`, right after `session.start()`:
  call the helper (gated by feature flag), and on success persist the path. Wrapped
  so it can never break the consultation.
- **`clinical_master/db/session_repository.py`** — add
  `save_recording_path(session_id, path, egress_id)`.
- **`clinical_master/config.py`** — add S3 + feature-flag settings.

`livekit.api` ships with `livekit-agents`, so **no new dependency**.

## Data model

`clinical_sessions` — two new nullable columns:
- `recording_path TEXT` — S3 key, e.g. `recordings/<session_id>.ogg`. `NULL` = not
  recorded (set only on successful egress start, so it doubles as the "was it
  recorded?" signal).
- `recording_egress_id TEXT` — for lookup/manual stop if ever needed.

Storage: new **private** bucket `consultation-recordings` (project
`jhpjftxnftuxzzxnknbx`). No public access, no user-facing RLS — internal only;
files read via service-role or short-lived signed URLs generated server-side.
Works for guest sessions too (keyed by `session_id`, not `user_id`).

## Config / secrets

New entries in `clinical_master/.env`, `config.py`, and the deploy workflow secrets:

```
RECORDING_ENABLED=true                 # feature flag — defaults TRUE in code
SUPABASE_S3_ENDPOINT=https://jhpjftxnftuxzzxnknbx.storage.supabase.co/storage/v1/s3
SUPABASE_S3_REGION=<project region>    # Supabase → Storage → S3 Configuration
SUPABASE_S3_ACCESS_KEY_ID=<generated>  # Supabase Storage S3 access key (separate from service role)
SUPABASE_S3_SECRET_ACCESS_KEY=<generated>
RECORDING_BUCKET=consultation-recordings
```

`RECORDING_ENABLED` defaults to **true** in `config.py`. To keep that safe before
the S3 keys exist, `recording.py` has a `_recording_configured()` guard: if any of
the S3 endpoint/region/key/secret/bucket settings are blank it logs a warning and
returns `None` **without** calling the egress API — so shipping with the flag on
never fires a doomed egress.

`S3Upload` uses `force_path_style=True` and the `endpoint` above (required for
Supabase's S3 gateway). `LiveKitAPI()` reuses existing `LIVEKIT_URL/API_KEY/API_SECRET`.

## Error handling & edge cases

- **Best-effort:** any egress failure is logged and swallowed — the consultation
  always proceeds. Failed recording leaves `recording_path` `NULL`.
- **Feature flag:** `RECORDING_ENABLED=false` short-circuits before any API call.
- **Unconfigured skip:** even with the flag on, missing S3 settings cause a logged
  skip (no API call) — see `_recording_configured()`.
- **Explicit stop:** the egress is stopped in the session `on_close` handler — it
  fires promptly on hang-up / end-tool / timer (the same point the transcript saves
  and feedback is triggered), and stopping is what writes the `.ogg`. A job shutdown
  callback is kept only as a backstop (it fires too late on its own — see above).
- **File-ready latency:** the `.ogg` lands in the bucket a few seconds after session
  end. No webhook handler now; `egress_ended` webhook is a future add if duration/size
  metadata or a "ready" flag is wanted.

## Testing

- `tests/test_recording.py` — mock `LiveKitAPI`; assert request built correctly
  (`audio_only=True`, OGG, correct filepath/bucket/endpoint); exceptions yield `None`.
- `save_recording_path` writes the right columns (mocked Supabase client).
- Follows existing pytest patterns in `clinical_master/tests/`.

## Root cause of initial "empty bucket" (debugged 2026-06-01)

Two separate issues, found in order:

1. **Duplicate agent worker.** A stale Azure Container App was still registered to
   the LiveKit project alongside the Render worker. LiveKit load-balanced
   consultations across both; sessions landing on the Azure worker ran pre-recording
   code with no S3 env vars → `recording_path` NULL and no logs in Render. Fixed by
   stopping the Azure Container App and deleting `deploy-clinical-master.yml` so it
   isn't re-deployed. Render is now the sole runtime.
2. **Egress never finalized.** Egress *started* correctly but the room lingered
   (empty_timeout 300s + participants), so it never stopped → never uploaded. The
   first fix (stop via `ctx.add_shutdown_callback`) was insufficient: shutdown
   callbacks run only *after* the job shuts down, which itself waits for the room
   to close (`job_proc_lazy_main.py`) — too late. Final fix: stop the egress in the
   session `on_close` handler, which fires promptly on consultation end (hang-up /
   end-tool / timer), the same point the transcript saves. The shutdown callback
   remains as a backstop. Verified manually: a stopped egress uploads the `.ogg`
   (8.25 MB on the last test), confirming S3 creds/region/endpoint are correct.

## Out of scope (future)

- Retention/deletion policy (recordings contain real trainee voice — PII).
- Trainee-facing playback UI.
- `egress_ended` webhook for ready-state / metadata.

## Callouts

- Egress adds LiveKit Cloud usage billing per recorded minute.
- Recordings contain real trainee voice → private bucket; plan retention later.
